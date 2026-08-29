#!/usr/bin/env python3
"""Generate Study Factory FF/CC with the pinned GitHub Ailey prompt in Codex.

Every lesson gets a new Codex session.  The first turn embeds the exact `.ff`
message after the pinned prompt and user-authorized live overlay.  The second
turn resumes that exact session with the exact message `.cc`.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ailey_public_profile import AILEY_COMMIT
from assemble_ailey_live_prompt import assemble_live_codex_prompt
from common import (
    artifact_generation_lock,
    artifact_record_errors,
    codex_artifact_quality_errors,
    find_lesson,
    lesson_dir,
    lesson_list,
    load_curriculum,
    load_json,
    now_kst,
    sha256_file,
    write_json,
)
from prompt_profiles import get_prompt_profile
from sanitize_ailey_github_cc import (
    CC_PROFILE,
    FF_PROFILE,
    staticize_cc_response,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COURSES = (
    "quality-management-engineer-written",
    "quality-management-engineer-practical",
    "industrial-safety-engineer-written",
    "industrial-safety-engineer-practical",
)
LIMIT_RE = re.compile(
    r"(?:usage\s+limit|rate\s+limit|too\s+many\s+requests|"
    r"you(?:'|’)ve\s+hit|insufficient\s+quota|capacity)",
    re.IGNORECASE,
)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class GenerationError(RuntimeError):
    pass


class GlobalLimitError(GenerationError):
    pass


class CancelledGeneration(GenerationError):
    pass


@dataclass(frozen=True)
class TurnResult:
    thread_id: str
    text: str
    usage: dict[str, Any]


@dataclass(frozen=True)
class LessonJob:
    course_id: str
    curriculum: dict[str, Any]
    lesson: dict[str, Any]

    @property
    def label(self) -> str:
        return f"{self.course_id}:{self.lesson['id']}"


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(value, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def _next_attempt_dir(job_root: Path) -> Path:
    job_root.mkdir(parents=True, exist_ok=True)
    indexes = []
    for candidate in job_root.glob("attempt-*"):
        try:
            indexes.append(int(candidate.name.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    attempt = job_root / f"attempt-{max(indexes, default=0) + 1:03d}"
    attempt.mkdir(parents=True, exist_ok=False)
    return attempt


def _parse_jsonl(stdout: str) -> tuple[str | None, str | None, bool, dict[str, Any]]:
    thread_id: str | None = None
    agent_text: str | None = None
    completed = False
    usage: dict[str, Any] = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            candidate = event.get("thread_id")
            if isinstance(candidate, str):
                thread_id = candidate
        elif event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                candidate = item.get("text")
                if isinstance(candidate, str):
                    agent_text = candidate
        elif event.get("type") == "turn.completed":
            completed = True
            candidate = event.get("usage")
            if isinstance(candidate, dict):
                usage = candidate
    return thread_id, agent_text, completed, usage


def _run_turn(
    command: list[str],
    *,
    output_path: Path,
    log_dir: Path,
    timeout_seconds: int,
    stdin_text: str | None = None,
    stop_event: threading.Event | None = None,
) -> TurnResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["NO_COLOR"] = "1"
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    stdout = ""
    stderr = ""
    cancelled = False
    timed_out = False
    try:
        try:
            stdout, stderr = process.communicate(input=stdin_text, timeout=1)
        except subprocess.TimeoutExpired:
            while True:
                if stop_event is not None and stop_event.is_set():
                    cancelled = True
                    break
                if time.monotonic() - started >= timeout_seconds:
                    timed_out = True
                    break
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        if cancelled or timed_out:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        raise
    elapsed = time.monotonic() - started
    _write_text(log_dir / "stdout.jsonl", stdout)
    _write_text(log_dir / "stderr.log", stderr)
    _write_text(
        log_dir / "transport.json",
        json.dumps(
            {
                "exit_code": process.returncode,
                "elapsed_seconds": round(elapsed, 3),
                "cancelled": cancelled,
                "timed_out": timed_out,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
    )
    if cancelled:
        raise CancelledGeneration("Codex turn cancelled after batch stop")
    if timed_out:
        _write_text(log_dir / "timeout.txt", f"timeout after {timeout_seconds}s\n")
        raise GenerationError(f"Codex turn timed out after {timeout_seconds}s")
    combined = stdout + "\n" + stderr
    if process.returncode != 0:
        if LIMIT_RE.search(combined):
            raise GlobalLimitError("Codex usage/rate limit reached")
        tail = "\n".join(combined.strip().splitlines()[-8:])
        raise GenerationError(f"Codex exited {process.returncode}: {tail}")
    thread_id, agent_text, completed, usage = _parse_jsonl(stdout)
    if LIMIT_RE.search(combined) and not completed:
        raise GlobalLimitError("Codex usage/rate limit reached")
    if not completed:
        raise GenerationError("Codex JSONL lacks turn.completed")
    if not output_path.is_file():
        raise GenerationError("Codex did not write output-last-message")
    file_text = output_path.read_text(encoding="utf-8")
    if agent_text is None:
        raise GenerationError("Codex JSONL lacks an agent_message")
    if file_text != agent_text:
        raise GenerationError("output-last-message differs from JSONL agent text")
    if thread_id is None or not UUID_RE.fullmatch(thread_id):
        raise GenerationError(f"Codex returned invalid thread id: {thread_id!r}")
    return TurnResult(thread_id=thread_id, text=file_text, usage=usage)


def _ff_errors(source: str, lesson: dict[str, Any]) -> list[str]:
    errors = codex_artifact_quality_errors("ff", source, lesson["topics"])
    expected_first = f"# {lesson['id']}. {lesson['title']}"
    first = next((line.strip() for line in source.splitlines() if line.strip()), "")
    if first != expected_first:
        errors.append(f"first visible line must be exactly {expected_first!r}")
    if lesson["id"] not in source or lesson["title"] not in source:
        errors.append("must include exact lesson identity")
    if "{{" in source or "{%" in source:
        errors.append("must not contain GitHub Pages Liquid delimiters")
    if "<!doctype html" in source.lower():
        errors.append("FF must remain Markdown, not HTML Canvas")
    if len(re.findall(r"(?m)^#{2,6}\s+", source)) < 5:
        errors.append("must use at least five structured Markdown subheadings")
    if "**" not in source:
        errors.append("must use Markdown bold emphasis")
    return list(dict.fromkeys(errors))


def _meta_is_live(job: LessonJob) -> bool:
    folder = lesson_dir(job.course_id, job.lesson)
    meta_path = folder / "meta.json"
    ff_path = folder / "ff.md"
    cc_path = folder / "cc.html"
    if not (meta_path.is_file() and ff_path.is_file() and cc_path.is_file()):
        return False
    try:
        meta = load_json(meta_path)
        cc_source = cc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return False
    required_cc_markers = (
        'name="source-turn" content=".cc-after-.ff-same-context"',
        'name="staticizer-profile" content="ailey-public-live-static-v1"',
        'name="upstream-custom-gpt-invoked" content="false"',
        "adapted by OpenAI Codex",
    )
    if any(marker not in cc_source for marker in required_cc_markers):
        return False
    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    ff = artifacts.get("ff")
    cc = artifacts.get("cc")
    return bool(
        isinstance(ff, dict)
        and isinstance(cc, dict)
        and ff.get("producer") == "openai-codex"
        and cc.get("producer") == "openai-codex"
        and ff.get("prompt_profile") == FF_PROFILE
        and cc.get("prompt_profile") == CC_PROFILE
        and ff.get("sha256") == sha256_file(ff_path)
        and cc.get("sha256") == sha256_file(cc_path)
    )


def _codex_commands(
    codex_executable: str,
    *,
    model: str,
    reasoning: str,
    ff_path: Path,
    cc_path: Path,
    model_instructions_path: Path,
    thread_id: str | None = None,
) -> list[str]:
    common = [
        "--json",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "-m", model,
        "-c", f'model_reasoning_effort="{reasoning}"',
        "-c", "model_instructions_file=" + json.dumps(str(model_instructions_path)),
        "-o", str(cc_path if thread_id else ff_path),
    ]
    if thread_id is None:
        return [
            codex_executable,
            "exec",
            *common,
            "--sandbox", "read-only",
            "--skip-git-repo-check",
            "-C", str(ROOT),
            "-",
        ]
    return [
        codex_executable,
        "exec",
        "resume",
        *common,
        "--skip-git-repo-check",
        thread_id,
        ".cc",
    ]


TRANSACTION_MARKER = ".ailey-live-transaction.json"


def _transaction_child(folder: Path, name: Any) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise GenerationError(f"invalid transaction path {name!r}")
    return folder / name


def _recover_artifact_transaction(folder: Path) -> bool:
    """Recover or finalize one interrupted lesson artifact transaction."""
    marker_path = folder / TRANSACTION_MARKER
    if not marker_path.is_file():
        return False
    marker = load_json(marker_path)
    state = marker.get("state")
    entries = marker.get("entries")
    if state not in {"prepared", "committed"} or not isinstance(entries, list):
        raise GenerationError(f"{marker_path}: invalid transaction journal")
    resolved: list[tuple[Path, Path, Path, bool]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise GenerationError(f"{marker_path}: invalid transaction entry")
        resolved.append((
            _transaction_child(folder, entry.get("target")),
            _transaction_child(folder, entry.get("stage")),
            _transaction_child(folder, entry.get("backup")),
            bool(entry.get("had_original")),
        ))
    recovery_temps: list[Path] = []

    def restore_without_consuming_backup(target: Path, backup: Path) -> None:
        recovery = folder / f".{target.name}.recovery.tmp"
        shutil.copyfile(backup, recovery)
        recovery_temps.append(recovery)
        os.replace(recovery, target)

    rollback_all = state == "prepared" or any(
        not target.exists() for target, _, _, _ in resolved
    )
    if rollback_all:
        missing_backups = [
            target.name
            for target, _, backup, had_original in resolved
            if had_original and not backup.is_file()
        ]
        if missing_backups:
            raise GenerationError(
                f"{marker_path}: missing backups for {missing_backups}"
            )
        for target, _, backup, had_original in resolved:
            if had_original:
                restore_without_consuming_backup(target, backup)
            else:
                target.unlink(missing_ok=True)
    marker_path.unlink(missing_ok=True)
    for _, stage, backup, _ in resolved:
        try:
            stage.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
        except OSError:
            pass
    for recovery in recovery_temps:
        try:
            recovery.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def _record_success(
    job: LessonJob,
    *,
    ff_source: str,
    cc_source: str,
) -> None:
    folder = lesson_dir(job.course_id, job.lesson)
    folder.mkdir(parents=True, exist_ok=True)
    _recover_artifact_transaction(folder)
    ff_target = folder / "ff.md"
    cc_target = folder / "cc.html"
    meta_path = folder / "meta.json"
    meta = load_json(meta_path)
    if meta.get("version") != 2:
        raise GenerationError(f"{job.label}: meta.json must be version 2")
    token = uuid.uuid4().hex
    ff_stage = folder / f".ff.md.{token}.stage"
    cc_stage = folder / f".cc.html.{token}.stage"
    meta_stage = folder / f".meta.json.{token}.stage"
    _write_text(ff_stage, ff_source.rstrip() + "\n")
    _write_text(cc_stage, cc_source.rstrip() + "\n")
    timestamp = now_kst()
    meta.pop("provenance", None)
    meta["artifacts"] = {
        "ff": {
            "producer": "openai-codex",
            "prompt_profile": FF_PROFILE,
            "generated_at": timestamp,
            "sha256": sha256_file(ff_stage),
        },
        "cc": {
            "producer": "openai-codex",
            "prompt_profile": CC_PROFILE,
            "generated_at": timestamp,
            "sha256": sha256_file(cc_stage),
        },
    }
    for kind, path in (("ff", ff_stage), ("cc", cc_stage)):
        errors = artifact_record_errors(meta["artifacts"][kind], path)
        if errors:
            raise GenerationError(f"{job.label}: {kind} provenance: {'; '.join(errors)}")
    write_json(meta_stage, meta)

    targets = ((ff_stage, ff_target), (cc_stage, cc_target), (meta_stage, meta_path))
    originals = {
        target: target.read_bytes() if target.exists() else None
        for _, target in targets
    }
    marker_path = folder / TRANSACTION_MARKER
    entries: list[dict[str, Any]] = []
    backups: list[Path] = []
    for stage, target in targets:
        backup = folder / f".{target.name}.{token}.backup"
        original = originals[target]
        if original is not None:
            backup.write_bytes(original)
        backups.append(backup)
        entries.append({
            "target": target.name,
            "stage": stage.name,
            "backup": backup.name,
            "had_original": original is not None,
        })
    journal = {
        "version": 1,
        "course_id": job.course_id,
        "lesson_id": job.lesson["id"],
        "token": token,
        "state": "prepared",
        "entries": entries,
    }
    cleanup_transaction = False
    try:
        write_json(marker_path, journal)
        for stage, target in targets:
            os.replace(stage, target)
        journal["state"] = "committed"
        write_json(marker_path, journal)
        cleanup_transaction = True
    except Exception as exc:  # noqa: BLE001 - rollback a partially published lesson
        rollback_errors: list[str] = []
        for target, original in originals.items():
            try:
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    rollback = target.with_name(f".{target.name}.{token}.rollback")
                    rollback.write_bytes(original)
                    os.replace(rollback, target)
            except Exception as rollback_exc:  # noqa: BLE001
                rollback_errors.append(f"{target.name}: {rollback_exc}")
        cleanup_transaction = not rollback_errors
        detail = f"; rollback errors: {rollback_errors}" if rollback_errors else ""
        raise GenerationError(f"{job.label}: atomic artifact replace failed: {exc}{detail}") from exc
    finally:
        if cleanup_transaction:
            marker_cleared = False
            try:
                marker_path.unlink(missing_ok=True)
                marker_cleared = True
            except OSError:
                pass
            if marker_cleared:
                for stage, _ in targets:
                    try:
                        stage.unlink(missing_ok=True)
                    except OSError:
                        pass
                for backup in backups:
                    try:
                        backup.unlink(missing_ok=True)
                    except OSError:
                        pass


def _write_status(path: Path, **values: Any) -> None:
    payload = {"updated_at": now_kst(), **values}
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _run_one_attempt(
    job: LessonJob,
    *,
    attempt_dir: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    stop_event: threading.Event,
) -> tuple[str, str, dict[str, Any]]:
    ff_raw = attempt_dir / "ff.raw.md"
    cc_raw = attempt_dir / "cc.raw.txt"
    status_path = attempt_dir / "status.json"
    model_instructions, exact_user = assemble_live_codex_prompt(
        job.course_id,
        job.lesson["id"],
    )
    model_instructions_path = attempt_dir / "model-instructions.md"
    _write_text(model_instructions_path, model_instructions.rstrip() + "\n")
    _write_text(attempt_dir / "exact-user-message.txt", exact_user + "\n")
    _write_text(
        attempt_dir / "model-instructions.sha256",
        sha256_file(model_instructions_path) + "\n",
    )
    _write_status(
        status_path,
        phase="ff-running",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        model=model,
        reasoning=reasoning,
    )
    ff_command = _codex_commands(
        codex_executable,
        model=model,
        reasoning=reasoning,
        ff_path=ff_raw,
        cc_path=cc_raw,
        model_instructions_path=model_instructions_path,
    )
    ff_result = _run_turn(
        ff_command,
        output_path=ff_raw,
        log_dir=attempt_dir / "ff-transport",
        timeout_seconds=timeout_seconds,
        stdin_text=exact_user,
        stop_event=stop_event,
    )
    ff_errors = _ff_errors(ff_result.text, job.lesson)
    if ff_errors:
        raise GenerationError("FF content gate: " + "; ".join(ff_errors))
    _write_status(
        status_path,
        phase="ff-complete",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        thread_id=ff_result.thread_id,
        ff_usage=ff_result.usage,
        model=model,
        reasoning=reasoning,
    )
    if stop_event.is_set():
        raise CancelledGeneration("batch stopped after FF; CC was not started")

    cc_command = _codex_commands(
        codex_executable,
        model=model,
        reasoning=reasoning,
        ff_path=ff_raw,
        cc_path=cc_raw,
        model_instructions_path=model_instructions_path,
        thread_id=ff_result.thread_id,
    )
    _write_status(
        status_path,
        phase="cc-running",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        thread_id=ff_result.thread_id,
        ff_usage=ff_result.usage,
        model=model,
        reasoning=reasoning,
    )
    cc_result = _run_turn(
        cc_command,
        output_path=cc_raw,
        log_dir=attempt_dir / "cc-transport",
        timeout_seconds=timeout_seconds,
        stop_event=stop_event,
    )
    if cc_result.thread_id != ff_result.thread_id:
        raise GenerationError("CC resumed a different Codex thread")
    static_cc = staticize_cc_response(
        cc_result.text,
        course_id=job.course_id,
        course_title=job.curriculum["title"],
        lesson_id=job.lesson["id"],
        lesson_title=job.lesson["title"],
        topics=job.lesson["topics"],
    )
    _write_text(attempt_dir / "cc.static.html", static_cc)
    _write_status(
        status_path,
        phase="cc-complete",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        thread_id=ff_result.thread_id,
        ff_usage=ff_result.usage,
        cc_usage=cc_result.usage,
        model=model,
        reasoning=reasoning,
    )
    return ff_result.text, static_cc, {
        "thread_id": ff_result.thread_id,
        "ff_usage": ff_result.usage,
        "cc_usage": cc_result.usage,
    }


def _find_resumable_ff(
    job: LessonJob,
    job_root: Path,
    *,
    model: str,
    reasoning: str,
) -> Path | None:
    """Find the newest attempt stopped cleanly after a validated FF turn."""
    attempts = sorted(job_root.glob("attempt-*"), reverse=True)
    if not attempts:
        return None
    current_instructions, current_user = assemble_live_codex_prompt(
        job.course_id,
        job.lesson["id"],
    )
    expected_instructions = current_instructions.rstrip() + "\n"
    expected_digest = hashlib.sha256(
        expected_instructions.encode("utf-8")
    ).hexdigest()
    for attempt_dir in attempts:
        required = (
            attempt_dir / "status.json",
            attempt_dir / "ff.raw.md",
            attempt_dir / "model-instructions.md",
            attempt_dir / "model-instructions.sha256",
            attempt_dir / "exact-user-message.txt",
        )
        if not all(path.is_file() for path in required):
            continue
        try:
            status = load_json(attempt_dir / "status.json")
            recorded_digest = (attempt_dir / "model-instructions.sha256").read_text(
                encoding="utf-8"
            ).strip()
            actual_digest = hashlib.sha256(
                (attempt_dir / "model-instructions.md").read_bytes()
            ).hexdigest()
            recorded_user = (attempt_dir / "exact-user-message.txt").read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
        if (
            status.get("phase") == "ff-complete"
            and UUID_RE.fullmatch(str(status.get("thread_id", "")))
            and status.get("model") == model
            and status.get("reasoning") == reasoning
            and recorded_digest == actual_digest == expected_digest
            and recorded_user == current_user + "\n"
        ):
            return attempt_dir
    return None


def _resume_after_ff(
    job: LessonJob,
    *,
    attempt_dir: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    stop_event: threading.Event,
) -> tuple[str, str, dict[str, Any]]:
    status_path = attempt_dir / "status.json"
    status = load_json(status_path)
    thread_id = str(status["thread_id"])
    ff_usage = status.get("ff_usage") if isinstance(status.get("ff_usage"), dict) else {}
    ff_raw = attempt_dir / "ff.raw.md"
    cc_raw = attempt_dir / "cc.raw.txt"
    model_instructions_path = attempt_dir / "model-instructions.md"
    ff_source = ff_raw.read_text(encoding="utf-8")
    ff_errors = _ff_errors(ff_source, job.lesson)
    if ff_errors:
        raise GenerationError("resumable FF content gate: " + "; ".join(ff_errors))
    if stop_event.is_set():
        raise CancelledGeneration("batch stopped before resumed CC")
    _write_status(
        status_path,
        phase="cc-running",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        thread_id=thread_id,
        ff_usage=ff_usage,
        resumed_after_ff=True,
        model=model,
        reasoning=reasoning,
    )
    cc_command = _codex_commands(
        codex_executable,
        model=model,
        reasoning=reasoning,
        ff_path=ff_raw,
        cc_path=cc_raw,
        model_instructions_path=model_instructions_path,
        thread_id=thread_id,
    )
    cc_result = _run_turn(
        cc_command,
        output_path=cc_raw,
        log_dir=attempt_dir / "cc-resume-transport",
        timeout_seconds=timeout_seconds,
        stop_event=stop_event,
    )
    if cc_result.thread_id != thread_id:
        raise GenerationError("resumed CC used a different Codex thread")
    static_cc = staticize_cc_response(
        cc_result.text,
        course_id=job.course_id,
        course_title=job.curriculum["title"],
        lesson_id=job.lesson["id"],
        lesson_title=job.lesson["title"],
        topics=job.lesson["topics"],
    )
    _write_text(attempt_dir / "cc.static.html", static_cc)
    _write_status(
        status_path,
        phase="cc-complete",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        thread_id=thread_id,
        ff_usage=ff_usage,
        cc_usage=cc_result.usage,
        resumed_after_ff=True,
        model=model,
        reasoning=reasoning,
    )
    return ff_source, static_cc, {
        "thread_id": thread_id,
        "ff_usage": ff_usage,
        "cc_usage": cc_result.usage,
        "resumed_after_ff": True,
    }


def _process_job_unlocked(
    job: LessonJob,
    *,
    run_root: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    max_attempts: int,
    regenerate_live: bool,
    stop_event: threading.Event,
) -> dict[str, Any]:
    if stop_event.is_set():
        return {"label": job.label, "status": "cancelled"}
    folder = lesson_dir(job.course_id, job.lesson)
    if _recover_artifact_transaction(folder):
        print(f"[RECOVERED] {job.label} artifact transaction", flush=True)
    if not regenerate_live and _meta_is_live(job):
        return {"label": job.label, "status": "skipped-live"}
    job_root = run_root / job.course_id / job.lesson["id"]
    resumable = _find_resumable_ff(
        job,
        job_root,
        model=model,
        reasoning=reasoning,
    )
    if resumable is not None:
        print(f"[RESUME-CC] {job.label} from {resumable.name}", flush=True)
        try:
            ff_source, cc_source, audit = _resume_after_ff(
                job,
                attempt_dir=resumable,
                codex_executable=codex_executable,
                model=model,
                reasoning=reasoning,
                timeout_seconds=timeout_seconds,
                stop_event=stop_event,
            )
            _record_success(job, ff_source=ff_source, cc_source=cc_source)
            _write_status(
                resumable / "status.json",
                phase="published-artifacts-replaced",
                course_id=job.course_id,
                lesson_id=job.lesson["id"],
                **audit,
            )
            print(f"[OK] {job.label} (resumed CC)", flush=True)
            return {"label": job.label, "status": "ok", **audit}
        except GlobalLimitError:
            stop_event.set()
            _write_text(resumable / "failure.txt", traceback.format_exc())
            print(f"[LIMIT] {job.label} while resuming CC", flush=True)
            raise
        except CancelledGeneration as exc:
            _write_text(resumable / "failure.txt", traceback.format_exc())
            return {"label": job.label, "status": "cancelled", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - fall back to a fresh FF session
            _write_text(resumable / "failure.txt", traceback.format_exc())
            print(f"[RESUME-FAILED] {job.label}: {exc}", flush=True)
    last_error = ""
    for local_attempt in range(1, max_attempts + 1):
        if stop_event.is_set():
            return {"label": job.label, "status": "cancelled"}
        attempt_dir = _next_attempt_dir(job_root)
        print(f"[START] {job.label} attempt {local_attempt}/{max_attempts}", flush=True)
        try:
            ff_source, cc_source, audit = _run_one_attempt(
                job,
                attempt_dir=attempt_dir,
                codex_executable=codex_executable,
                model=model,
                reasoning=reasoning,
                timeout_seconds=timeout_seconds,
                stop_event=stop_event,
            )
            _record_success(job, ff_source=ff_source, cc_source=cc_source)
            _write_status(
                attempt_dir / "status.json",
                phase="published-artifacts-replaced",
                course_id=job.course_id,
                lesson_id=job.lesson["id"],
                **audit,
            )
            print(f"[OK] {job.label}", flush=True)
            return {"label": job.label, "status": "ok", **audit}
        except GlobalLimitError:
            stop_event.set()
            _write_text(attempt_dir / "failure.txt", traceback.format_exc())
            print(f"[LIMIT] {job.label}", flush=True)
            raise
        except CancelledGeneration as exc:
            _write_text(attempt_dir / "failure.txt", traceback.format_exc())
            print(f"[CANCELLED] {job.label}: {exc}", flush=True)
            return {"label": job.label, "status": "cancelled", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - batch isolation boundary
            last_error = str(exc)
            _write_text(attempt_dir / "failure.txt", traceback.format_exc())
            print(f"[RETRY] {job.label}: {last_error}", flush=True)
            if local_attempt < max_attempts:
                time.sleep(min(30, 5 * local_attempt))
    print(f"[FAILED] {job.label}: {last_error}", flush=True)
    return {"label": job.label, "status": "failed", "error": last_error}


def _process_job(
    job: LessonJob,
    *,
    run_root: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    max_attempts: int,
    regenerate_live: bool,
    stop_event: threading.Event,
) -> dict[str, Any]:
    with artifact_generation_lock(job.course_id, job.lesson["id"]):
        return _process_job_unlocked(
            job,
            run_root=run_root,
            codex_executable=codex_executable,
            model=model,
            reasoning=reasoning,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            regenerate_live=regenerate_live,
            stop_event=stop_event,
        )


def _collect_jobs(course_ids: list[str], lesson_id: str | None) -> list[LessonJob]:
    jobs: list[LessonJob] = []
    for course_id in course_ids:
        curriculum = load_curriculum(course_id)
        lessons = lesson_list(curriculum)
        if lesson_id is not None:
            if len(course_ids) != 1:
                raise ValueError("--lesson-id requires exactly one --course")
            lessons = [find_lesson(curriculum, lesson_id)]
        jobs.extend(LessonJob(course_id, curriculum, lesson) for lesson in lessons)
    return jobs


def _validate_courses(course_ids: list[str]) -> bool:
    command = [
        sys.executable,
        str(ROOT / "study" / "factory" / "scripts" / "validate_all.py"),
        *course_ids,
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", check=False)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", action="append", dest="courses")
    parser.add_argument("--lesson-id")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1_200)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--regenerate-live", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    if not 1 <= args.attempts <= 3:
        parser.error("--attempts must be between 1 and 3")
    if args.timeout < 600:
        parser.error("--timeout must be at least 600 seconds")

    get_prompt_profile(FF_PROFILE, artifact_kind="ff", producer="openai-codex")
    get_prompt_profile(CC_PROFILE, artifact_kind="cc", producer="openai-codex")
    if AILEY_COMMIT != "8a36e77d025bb9c258bfeaf8587424783140b185":
        raise SystemExit("unexpected Ailey upstream commit")
    codex_executable = shutil.which("codex")
    if not codex_executable:
        raise SystemExit("codex executable not found")
    course_ids = args.courses or list(DEFAULT_COURSES)
    jobs = _collect_jobs(course_ids, args.lesson_id)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        jobs = jobs[:args.limit]
    run_root = args.run_root or (
        Path(tempfile.gettempdir()) / "ailey-github-codex-live-study-factory"
    )
    print(
        f"Selected {len(jobs)} lesson(s), workers={args.workers}, "
        f"model={args.model}, run_root={run_root}",
        flush=True,
    )
    if args.dry_run:
        for job in jobs:
            state = "live" if _meta_is_live(job) else "replace"
            print(f"{job.label}\t{state}")
        return 0

    stop_event = threading.Event()
    results: list[dict[str, Any]] = []
    global_limit = False
    interrupted = False
    job_iterator = iter(jobs)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.workers)
    futures: dict[concurrent.futures.Future[dict[str, Any]], LessonJob] = {}

    def submit_job(job: LessonJob) -> None:
        future = pool.submit(
                _process_job,
                job,
                run_root=run_root,
                codex_executable=codex_executable,
                model=args.model,
                reasoning=args.reasoning,
                timeout_seconds=args.timeout,
                max_attempts=args.attempts,
                regenerate_live=args.regenerate_live,
                stop_event=stop_event,
            )
        futures[future] = job

    def fill_workers() -> None:
        while len(futures) < args.workers and not stop_event.is_set():
            try:
                submit_job(next(job_iterator))
            except StopIteration:
                break

    def collect_future(
        future: concurrent.futures.Future[dict[str, Any]],
        job: LessonJob,
    ) -> None:
        nonlocal global_limit
        try:
            results.append(future.result())
        except concurrent.futures.CancelledError:
            results.append({
                "label": job.label,
                "status": "cancelled",
                "error": "future cancelled after batch stop",
            })
        except GlobalLimitError as exc:
            global_limit = True
            stop_event.set()
            results.append({
                "label": job.label,
                "status": "global-limit",
                "error": str(exc),
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "label": job.label,
                "status": "runner-error",
                "error": str(exc),
            })

    def mark_unsubmitted(reason: str) -> None:
        for job in job_iterator:
            results.append({
                "label": job.label,
                "status": "cancelled",
                "error": reason,
            })

    try:
        fill_workers()
        while futures:
            done, _ = concurrent.futures.wait(
                futures,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                job = futures.pop(future)
                collect_future(future, job)
            if stop_event.is_set():
                mark_unsubmitted("not started after batch stop")
                for future in futures:
                    future.cancel()
            else:
                fill_workers()
    except KeyboardInterrupt:
        interrupted = True
        stop_event.set()
        mark_unsubmitted("not started after keyboard interrupt")
        for future in futures:
            future.cancel()
        for future in concurrent.futures.as_completed(list(futures)):
            job = futures[future]
            collect_future(future, job)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    summary: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        summary[status] = summary.get(status, 0) + 1
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(run_root / "last-summary.json", {
        "generated_at": now_kst(),
        "upstream_commit": AILEY_COMMIT,
        "model": args.model,
        "reasoning": args.reasoning,
        "courses": course_ids,
        "summary": summary,
        "results": results,
    })
    print("Summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    failed = any(
        result["status"] not in {"ok", "skipped-live"}
        for result in results
    )
    if not failed and not _validate_courses(course_ids):
        failed = True
    if global_limit:
        print("Stopped after a global Codex usage/rate limit.", flush=True)
    if interrupted:
        print("Stopped after keyboard interrupt.", flush=True)
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
