#!/usr/bin/env python3
"""Regenerate paired FF/CC through exact `.ff` -> same-thread `.cc` visual-v2 sessions."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from assemble_ailey_visual_prompt import (
    CC_VISUAL_PROFILE,
    FF_VISUAL_PROFILE,
    assemble_visual_codex_prompt,
)
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
from run_ailey_github_codex import (
    DEFAULT_COURSES,
    UUID_RE,
    CancelledGeneration,
    GenerationError,
    GlobalLimitError,
    LessonJob,
    _codex_commands,
    _next_attempt_dir,
    _recover_artifact_transaction,
    _run_turn,
    _validate_courses,
    _write_status,
    _write_text,
)
from sanitize_ailey_github_cc import staticize_cc_response
from visual_cc_quality import (
    analyze_visual_cc_quality,
    required_visual_v2_svg_count,
    visual_v2_contract_errors,
)


ROOT = Path(__file__).resolve().parents[3]
TRANSACTION_MARKER = ".ailey-live-transaction.json"


def _repository_key() -> str:
    return hashlib.sha256(
        str(ROOT.resolve()).casefold().encode("utf-8")
    ).hexdigest()[:12]


def _canonical_ff_source(source: str) -> str:
    return source.rstrip() + "\n"


def _visual_ff_errors(source: str, job: LessonJob) -> list[str]:
    """Validate the temporary FF context without forcing a giant official-title H1."""
    lesson = job.lesson
    errors = codex_artifact_quality_errors("ff", source, lesson["topics"])
    first = next((line.strip() for line in source.splitlines() if line.strip()), "")
    expected_prefix = f"# {lesson['id']}. "
    if not first.startswith(expected_prefix):
        errors.append(f"first visible line must start with {expected_prefix!r}")
    display_title = first[len(expected_prefix):].strip() if first.startswith(expected_prefix) else ""
    if not 12 <= len(display_title) <= 36:
        errors.append("FF display H1 must use a focused 12-36 character title")
    if lesson["id"] not in source or lesson["title"] not in source:
        errors.append("must include exact lesson identity below the display H1")
    if job.curriculum["title"] not in source:
        errors.append("must include the exact course title below the display H1")
    if "{{" in source or "{%" in source:
        errors.append("must not contain GitHub Pages Liquid delimiters")
    if "<!doctype html" in source.lower():
        errors.append("FF must remain Markdown, not HTML")
    if len(re.findall(r"(?m)^#{2,6}\s+", source)) < 5:
        errors.append("must use at least five structured Markdown subheadings")
    if "**" not in source:
        errors.append("must use Markdown bold emphasis")
    return list(dict.fromkeys(errors))


def _meta_is_visual(job: LessonJob) -> bool:
    folder = lesson_dir(job.course_id, job.lesson)
    meta_path = folder / "meta.json"
    ff_path = folder / "ff.md"
    cc_path = folder / "cc.html"
    if not all(path.is_file() for path in (meta_path, ff_path, cc_path)):
        return False
    try:
        meta = load_json(meta_path)
        from validation import (
            meta_schema_errors,
            visual_ailey_cc_errors,
            visual_ailey_ff_errors,
        )

        if meta_schema_errors(meta):
            return False
        if any(meta.get(key) != value for key, value in (
            ("course_id", job.course_id),
            ("lesson_id", job.lesson["id"]),
            ("title", job.lesson["title"]),
            ("slug", job.lesson["slug"]),
            ("status", "published"),
        )):
            return False
        artifacts = meta["artifacts"]
        ff = artifacts["ff"]
        cc = artifacts["cc"]
        if artifact_record_errors(ff, ff_path) or artifact_record_errors(cc, cc_path):
            return False
        get_prompt_profile(
            ff["prompt_profile"],
            artifact_kind="ff",
            producer=ff["producer"],
        )
        get_prompt_profile(
            cc["prompt_profile"],
            artifact_kind="cc",
            producer=cc["producer"],
        )
        ff_source = ff_path.read_text(encoding="utf-8")
        cc_source = cc_path.read_text(encoding="utf-8")
        return bool(
            ff["producer"] == "openai-codex"
            and ff["prompt_profile"] == FF_VISUAL_PROFILE
            and not visual_ailey_ff_errors(
                ff_source,
                job.curriculum,
                job.lesson,
            )
            and cc["producer"] == "openai-codex"
            and cc["prompt_profile"] == CC_VISUAL_PROFILE
            and not visual_ailey_cc_errors(
                cc_source,
                job.curriculum,
                job.lesson,
                expected_context_ff_sha256=ff["sha256"],
            )
        )
    except (
        KeyError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return False


def _visual_cc_errors(source: str, job: LessonJob) -> list[str]:
    lesson = job.lesson
    return visual_v2_contract_errors(
        source,
        required_svg_count=required_visual_v2_svg_count(lesson),
        expected_official_title=lesson["title"],
        required_visible_values=(
            job.curriculum["title"],
            lesson["id"],
            lesson["title"],
            *lesson["topics"],
        ),
    )


def _record_visual_pair(job: LessonJob, ff_source: str, cc_source: str) -> None:
    """Atomically publish the exact FF and its same-thread visual CC response."""
    folder = lesson_dir(job.course_id, job.lesson)
    folder.mkdir(parents=True, exist_ok=True)
    _recover_artifact_transaction(folder)
    ff_path = folder / "ff.md"
    cc_target = folder / "cc.html"
    meta_path = folder / "meta.json"
    if not ff_path.is_file() or not meta_path.is_file():
        raise GenerationError(
            f"{job.label}: existing published FF/meta is required for paired regeneration"
        )
    meta = load_json(meta_path)
    from validation import meta_schema_errors

    schema_errors = meta_schema_errors(meta)
    if schema_errors:
        raise GenerationError(
            f"{job.label}: invalid existing meta.json: {'; '.join(schema_errors)}"
        )
    if any(meta.get(key) != value for key, value in (
        ("course_id", job.course_id),
        ("lesson_id", job.lesson["id"]),
        ("title", job.lesson["title"]),
        ("slug", job.lesson["slug"]),
        ("status", "published"),
    )):
        raise GenerationError(f"{job.label}: existing published metadata identity mismatch")
    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict) or not isinstance(artifacts.get("ff"), dict):
        raise GenerationError(f"{job.label}: existing FF provenance is missing")
    ff_errors = artifact_record_errors(artifacts["ff"], ff_path)
    if ff_errors:
        raise GenerationError(f"{job.label}: existing FF provenance: {'; '.join(ff_errors)}")
    old_cc = artifacts.get("cc")
    old_cc_errors = artifact_record_errors(old_cc, cc_target)
    if old_cc_errors:
        raise GenerationError(
            f"{job.label}: existing CC provenance: {'; '.join(old_cc_errors)}"
        )
    for kind, record in (("ff", artifacts["ff"]), ("cc", old_cc)):
        get_prompt_profile(
            record["prompt_profile"],
            artifact_kind=kind,
            producer=record["producer"],
        )

    token = uuid.uuid4().hex
    ff_stage = folder / f".ff.md.{token}.stage"
    cc_stage = folder / f".cc.html.{token}.stage"
    meta_stage = folder / f".meta.json.{token}.stage"
    _write_text(ff_stage, _canonical_ff_source(ff_source))
    _write_text(cc_stage, cc_source.rstrip() + "\n")
    meta.pop("provenance", None)
    timestamp = now_kst()
    meta["artifacts"] = {
        "ff": {
            "producer": "openai-codex",
            "prompt_profile": FF_VISUAL_PROFILE,
            "generated_at": timestamp,
            "sha256": sha256_file(ff_stage),
        },
        "cc": {
            "producer": "openai-codex",
            "prompt_profile": CC_VISUAL_PROFILE,
            "generated_at": timestamp,
            "sha256": sha256_file(cc_stage),
        },
    }
    for kind, stage in (("ff", ff_stage), ("cc", cc_stage)):
        record_errors = artifact_record_errors(meta["artifacts"][kind], stage)
        if record_errors:
            raise GenerationError(
                f"{job.label}: {kind.upper()} provenance: {'; '.join(record_errors)}"
            )
    write_json(meta_stage, meta)

    targets = (
        (ff_stage, ff_path),
        (cc_stage, cc_target),
        (meta_stage, meta_path),
    )
    originals = {
        target: target.read_bytes() if target.exists() else None
        for _, target in targets
    }
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
    marker_path = folder / TRANSACTION_MARKER
    journal = {
        "version": 1,
        "course_id": job.course_id,
        "lesson_id": job.lesson["id"],
        "token": token,
        "state": "prepared",
        "entries": entries,
    }
    committed = False
    marker_cleared = False
    try:
        write_json(marker_path, journal)
        for stage, target in targets:
            os.replace(stage, target)
        journal["state"] = "committed"
        write_json(marker_path, journal)
        committed = True
    except Exception as exc:  # noqa: BLE001 - artifact transaction rollback
        rollback_errors: list[str] = []
        for target, original in originals.items():
            try:
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    recovery = folder / f".{target.name}.{token}.recovery.tmp"
                    recovery.write_bytes(original)
                    os.replace(recovery, target)
            except OSError as rollback_error:
                rollback_errors.append(f"{target.name}: {rollback_error}")
        if rollback_errors:
            raise GenerationError(
                f"{job.label}: CC transaction failed ({exc}); rollback failed: "
                + "; ".join(rollback_errors)
            ) from exc
        marker_path.unlink(missing_ok=True)
        marker_cleared = True
        raise
    finally:
        if committed:
            marker_path.unlink(missing_ok=True)
            marker_cleared = True
        if marker_cleared:
            for stage, _ in targets:
                stage.unlink(missing_ok=True)
            for backup in backups:
                backup.unlink(missing_ok=True)


def _prepare_attempt(job: LessonJob, attempt_dir: Path) -> tuple[Path, Path, Path, str]:
    ff_raw = attempt_dir / "ff.raw.md"
    cc_raw = attempt_dir / "cc.raw.txt"
    instructions, exact_user = assemble_visual_codex_prompt(
        job.course_id,
        job.lesson["id"],
    )
    instructions_path = attempt_dir / "model-instructions.md"
    _write_text(instructions_path, instructions.rstrip() + "\n")
    _write_text(attempt_dir / "exact-user-message.txt", exact_user + "\n")
    _write_text(
        attempt_dir / "model-instructions.sha256",
        sha256_file(instructions_path) + "\n",
    )
    return ff_raw, cc_raw, instructions_path, exact_user


def _staticize_and_gate(
    job: LessonJob,
    raw_cc: str,
    attempt_dir: Path,
    *,
    thread_id: str,
    model: str,
    reasoning: str,
) -> tuple[str, dict[str, Any]]:
    ff_context = (attempt_dir / "ff.raw.md").read_text(encoding="utf-8")
    published_ff = _canonical_ff_source(ff_context)
    document = staticize_cc_response(
        raw_cc,
        course_id=job.course_id,
        course_title=job.curriculum["title"],
        lesson_id=job.lesson["id"],
        lesson_title=job.lesson["title"],
        topics=job.lesson["topics"],
        profile=CC_VISUAL_PROFILE,
        context_ff_sha256=hashlib.sha256(
            published_ff.encode("utf-8")
        ).hexdigest(),
        model_instructions_sha256=sha256_file(
            attempt_dir / "model-instructions.md"
        ),
        codex_thread_id=thread_id,
        codex_model=model,
        codex_reasoning=reasoning,
    )
    quality = analyze_visual_cc_quality(document)
    errors = _visual_cc_errors(document, job)
    metrics = quality.metrics
    write_json(attempt_dir / "visual-quality.json", {"errors": errors, "metrics": metrics})
    if errors:
        raise GenerationError("visual CC gate: " + "; ".join(errors))
    _write_text(attempt_dir / "cc.static.html", document)
    return document, metrics


def _run_cc_turn_with_resumable_status(
    job: LessonJob,
    *,
    status_path: Path,
    command: list[str],
    output_path: Path,
    log_dir: Path,
    timeout_seconds: int,
    stop_event: threading.Event,
    thread_id: str,
    ff_usage: dict[str, Any],
    model: str,
    reasoning: str,
    resumed_after_ff: bool = False,
) -> Any:
    """Run `.cc` while preserving a known-good FF after definite interruption."""

    status_values: dict[str, Any] = {
        "course_id": job.course_id,
        "lesson_id": job.lesson["id"],
        "thread_id": thread_id,
        "ff_usage": ff_usage,
        "model": model,
        "reasoning": reasoning,
    }
    if resumed_after_ff:
        status_values["resumed_after_ff"] = True
    _write_status(status_path, phase="cc-running", **status_values)
    try:
        return _run_turn(
            command,
            output_path=output_path,
            log_dir=log_dir,
            timeout_seconds=timeout_seconds,
            stop_event=stop_event,
        )
    except (GlobalLimitError, CancelledGeneration):
        # These paths know the CC turn did not complete: rate-limit errors lack
        # turn.completed, while cancellation terminates the transport.  Keep
        # the validated FF/thread resumable for the next account or batch.
        _write_status(status_path, phase="ff-complete", **status_values)
        raise


def _run_fresh_attempt(
    job: LessonJob,
    *,
    attempt_dir: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    stop_event: threading.Event,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    ff_raw, cc_raw, instructions_path, exact_user = _prepare_attempt(job, attempt_dir)
    status_path = attempt_dir / "status.json"
    _write_status(
        status_path,
        phase="ff-running",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        model=model,
        reasoning=reasoning,
    )
    ff_result = _run_turn(
        _codex_commands(
            codex_executable,
            model=model,
            reasoning=reasoning,
            ff_path=ff_raw,
            cc_path=cc_raw,
            model_instructions_path=instructions_path,
        ),
        output_path=ff_raw,
        log_dir=attempt_dir / "ff-transport",
        timeout_seconds=timeout_seconds,
        stdin_text=exact_user,
        stop_event=stop_event,
    )
    errors = _visual_ff_errors(ff_result.text, job)
    if errors:
        raise GenerationError("FF context gate: " + "; ".join(errors))
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
        raise CancelledGeneration("batch stopped after FF")
    cc_result = _run_cc_turn_with_resumable_status(
        job,
        status_path=status_path,
        command=
        _codex_commands(
            codex_executable,
            model=model,
            reasoning=reasoning,
            ff_path=ff_raw,
            cc_path=cc_raw,
            model_instructions_path=instructions_path,
            thread_id=ff_result.thread_id,
        ),
        output_path=cc_raw,
        log_dir=attempt_dir / "cc-transport",
        timeout_seconds=timeout_seconds,
        stop_event=stop_event,
        thread_id=ff_result.thread_id,
        ff_usage=ff_result.usage,
        model=model,
        reasoning=reasoning,
    )
    if cc_result.thread_id != ff_result.thread_id:
        raise GenerationError("CC resumed a different Codex thread")
    document, metrics = _staticize_and_gate(
        job,
        cc_result.text,
        attempt_dir,
        thread_id=ff_result.thread_id,
        model=model,
        reasoning=reasoning,
    )
    audit = {
        "thread_id": ff_result.thread_id,
        "ff_usage": ff_result.usage,
        "cc_usage": cc_result.usage,
        "visual_metrics": metrics,
    }
    _write_status(
        status_path,
        phase="cc-complete",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        model=model,
        reasoning=reasoning,
        **audit,
    )
    return ff_result.text, document, metrics, audit


def _find_resumable_ff(
    job: LessonJob,
    job_root: Path,
    *,
    model: str,
    reasoning: str,
) -> Path | None:
    current_instructions, current_user = assemble_visual_codex_prompt(
        job.course_id,
        job.lesson["id"],
    )
    expected = current_instructions.rstrip() + "\n"
    expected_digest = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    for attempt_dir in sorted(job_root.glob("attempt-*"), reverse=True):
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
            actual_digest = sha256_file(attempt_dir / "model-instructions.md")
            recorded_digest = (attempt_dir / "model-instructions.sha256").read_text(
                encoding="utf-8"
            ).strip()
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
    ff_source = (attempt_dir / "ff.raw.md").read_text(encoding="utf-8")
    errors = _visual_ff_errors(ff_source, job)
    if errors:
        raise GenerationError("resumable FF context gate: " + "; ".join(errors))
    cc_raw = attempt_dir / "cc.raw.txt"
    cc_result = _run_cc_turn_with_resumable_status(
        job,
        status_path=status_path,
        command=
        _codex_commands(
            codex_executable,
            model=model,
            reasoning=reasoning,
            ff_path=attempt_dir / "ff.raw.md",
            cc_path=cc_raw,
            model_instructions_path=attempt_dir / "model-instructions.md",
            thread_id=thread_id,
        ),
        output_path=cc_raw,
        log_dir=attempt_dir / "cc-resume-transport",
        timeout_seconds=timeout_seconds,
        stop_event=stop_event,
        thread_id=thread_id,
        ff_usage=status.get("ff_usage", {}),
        model=model,
        reasoning=reasoning,
        resumed_after_ff=True,
    )
    if cc_result.thread_id != thread_id:
        raise GenerationError("resumed CC used a different Codex thread")
    document, metrics = _staticize_and_gate(
        job,
        cc_result.text,
        attempt_dir,
        thread_id=thread_id,
        model=model,
        reasoning=reasoning,
    )
    audit = {
        "thread_id": thread_id,
        "ff_usage": status.get("ff_usage", {}),
        "cc_usage": cc_result.usage,
        "visual_metrics": metrics,
        "resumed_after_ff": True,
    }
    _write_status(
        status_path,
        phase="cc-complete",
        course_id=job.course_id,
        lesson_id=job.lesson["id"],
        model=model,
        reasoning=reasoning,
        **audit,
    )
    return ff_source, document, audit


def _process_job_unlocked(
    job: LessonJob,
    *,
    run_root: Path,
    codex_executable: str,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    max_attempts: int,
    regenerate: bool,
    stop_event: threading.Event,
) -> dict[str, Any]:
    if stop_event.is_set():
        return {"label": job.label, "status": "cancelled"}
    folder = lesson_dir(job.course_id, job.lesson)
    if _recover_artifact_transaction(folder):
        print(f"[RECOVERED] {job.label}", flush=True)
    if not regenerate and _meta_is_visual(job):
        return {"label": job.label, "status": "skipped-visual"}
    job_root = run_root / job.course_id / job.lesson["id"]
    resumable = None if regenerate else _find_resumable_ff(
        job,
        job_root,
        model=model,
        reasoning=reasoning,
    )
    if resumable is not None:
        print(f"[RESUME-CC] {job.label} from {resumable.name}", flush=True)
        try:
            ff_source, document, audit = _resume_after_ff(
                job,
                attempt_dir=resumable,
                codex_executable=codex_executable,
                model=model,
                reasoning=reasoning,
                timeout_seconds=timeout_seconds,
                stop_event=stop_event,
            )
            _record_visual_pair(job, ff_source, document)
            _write_status(
                resumable / "status.json",
                phase="published-visual-pair",
                course_id=job.course_id,
                lesson_id=job.lesson["id"],
                **audit,
            )
            print(f"[OK] {job.label} (resumed)", flush=True)
            return {"label": job.label, "status": "ok", **audit}
        except GlobalLimitError:
            stop_event.set()
            raise
        except Exception as exc:  # noqa: BLE001 - retry with a clean context
            _write_text(resumable / "failure.txt", traceback.format_exc())
            print(f"[RESUME-FAILED] {job.label}: {exc}", flush=True)

    last_error = ""
    for attempt_number in range(1, max_attempts + 1):
        if stop_event.is_set():
            return {"label": job.label, "status": "cancelled"}
        attempt_dir = _next_attempt_dir(job_root)
        print(f"[START] {job.label} attempt {attempt_number}/{max_attempts}", flush=True)
        try:
            ff_source, document, _, audit = _run_fresh_attempt(
                job,
                attempt_dir=attempt_dir,
                codex_executable=codex_executable,
                model=model,
                reasoning=reasoning,
                timeout_seconds=timeout_seconds,
                stop_event=stop_event,
            )
            _record_visual_pair(job, ff_source, document)
            _write_status(
                attempt_dir / "status.json",
                phase="published-visual-pair",
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
            return {"label": job.label, "status": "cancelled", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - isolated lesson retry
            last_error = str(exc)
            _write_text(attempt_dir / "failure.txt", traceback.format_exc())
            print(f"[RETRY] {job.label}: {last_error}", flush=True)
            if attempt_number < max_attempts:
                time.sleep(min(20, attempt_number * 4))
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
    regenerate: bool,
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
            regenerate=regenerate,
            stop_event=stop_event,
        )


def _collect_jobs(course_ids: list[str], targets: list[str]) -> list[LessonJob]:
    if targets:
        result: list[LessonJob] = []
        seen: set[tuple[str, str]] = set()
        for value in targets:
            if ":" not in value:
                raise ValueError(f"target must be COURSE:LESSON, got {value!r}")
            course_id, lesson_id = value.split(":", 1)
            if course_id not in DEFAULT_COURSES:
                raise ValueError(f"target course is outside the four-course repair: {course_id}")
            if course_id not in course_ids:
                raise ValueError(
                    f"target course {course_id!r} is not selected by --courses"
                )
            key = (course_id, lesson_id)
            if key in seen:
                continue
            seen.add(key)
            curriculum = load_curriculum(course_id)
            result.append(LessonJob(course_id, curriculum, find_lesson(curriculum, lesson_id)))
        return result
    result = []
    for course_id in course_ids:
        curriculum = load_curriculum(course_id)
        result.extend(
            LessonJob(course_id, curriculum, lesson)
            for lesson in lesson_list(curriculum)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--courses", nargs="+", choices=DEFAULT_COURSES)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    if not 1 <= args.attempts <= 3:
        parser.error("--attempts must be between 1 and 3")
    if args.timeout < 600:
        parser.error("--timeout must be at least 600 seconds")
    get_prompt_profile(FF_VISUAL_PROFILE, artifact_kind="ff", producer="openai-codex")
    get_prompt_profile(CC_VISUAL_PROFILE, artifact_kind="cc", producer="openai-codex")
    course_ids = list(dict.fromkeys(args.courses or DEFAULT_COURSES))
    jobs = _collect_jobs(course_ids, args.target)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be positive")
        jobs = jobs[:args.limit]
    run_root = args.run_root or (
        Path(tempfile.gettempdir())
        / "ailey-github-codex-visual-v2"
        / _repository_key()
    )
    print(
        f"Selected {len(jobs)} visual CC lesson(s), workers={args.workers}, "
        f"model={args.model}, reasoning={args.reasoning}, run_root={run_root}",
        flush=True,
    )
    if args.dry_run:
        for job in jobs:
            state = "visual-pair" if _meta_is_visual(job) else "replace-pair"
            print(f"{job.label}\t{state}")
        return 0
    codex_executable = shutil.which("codex")
    if not codex_executable:
        raise SystemExit("codex executable not found")

    stop_event = threading.Event()
    results: list[dict[str, Any]] = []
    iterator = iter(jobs)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.workers)
    futures: dict[concurrent.futures.Future[dict[str, Any]], LessonJob] = {}

    def fill() -> None:
        while len(futures) < args.workers and not stop_event.is_set():
            try:
                job = next(iterator)
            except StopIteration:
                break
            futures[pool.submit(
                _process_job,
                job,
                run_root=run_root,
                codex_executable=codex_executable,
                model=args.model,
                reasoning=args.reasoning,
                timeout_seconds=args.timeout,
                max_attempts=args.attempts,
                regenerate=args.regenerate,
                stop_event=stop_event,
            )] = job

    try:
        fill()
        while futures:
            done, _ = concurrent.futures.wait(
                futures,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                job = futures.pop(future)
                try:
                    results.append(future.result())
                except concurrent.futures.CancelledError:
                    results.append({
                        "label": job.label,
                        "status": "cancelled",
                        "error": "future cancelled after batch stop",
                    })
                except GlobalLimitError as exc:
                    stop_event.set()
                    results.append({"label": job.label, "status": "global-limit", "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    results.append({"label": job.label, "status": "runner-error", "error": str(exc)})
            if stop_event.is_set():
                for job in iterator:
                    results.append({"label": job.label, "status": "cancelled"})
                for future in futures:
                    future.cancel()
            else:
                fill()
    except KeyboardInterrupt:
        stop_event.set()
        for future in futures:
            future.cancel()
        return 130
    finally:
        pool.shutdown(wait=True, cancel_futures=True)

    summary: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        summary[status] = summary.get(status, 0) + 1
    failed = any(result["status"] not in {"ok", "skipped-visual"} for result in results)
    validated_courses = sorted({job.course_id for job in jobs})
    repository_validation_ok = _validate_courses(validated_courses)
    if not repository_validation_ok:
        failed = True
        summary["repository-validation-failed"] = 1
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(run_root / "last-summary.json", {
        "generated_at": now_kst(),
        "ff_context_profile": FF_VISUAL_PROFILE,
        "cc_profile": CC_VISUAL_PROFILE,
        "model": args.model,
        "reasoning": args.reasoning,
        "summary": summary,
        "results": results,
        "repository_validation_ok": repository_validation_ok,
        "exit_code": 1 if failed else 0,
    })
    print("Summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
