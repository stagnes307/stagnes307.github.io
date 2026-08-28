#!/usr/bin/env python3
"""Apply a durable lesson state transition, refusing invalid publication."""

from __future__ import annotations

import argparse
import re

from build_course import build_course
from build_lesson import build_lesson
from common import (
    artifact_record_errors,
    STATUSES,
    codex_artifact_quality_errors,
    find_lesson,
    lesson_dir,
    lesson_url,
    load_curriculum,
    load_json,
    load_or_create_progress,
    now_kst,
    progress_path,
    write_json,
)


FF_REQUIRED_STATUSES = {
    "ff-complete", "cc-running", "cc-complete", "publishing", "published",
}
CC_REQUIRED_STATUSES = {"cc-complete", "publishing", "published"}


def gates(course_id: str, lesson: dict) -> tuple[bool, bool, list[str]]:
    folder = lesson_dir(course_id, lesson)
    ff, cc = folder / "ff.md", folder / "cc.html"
    errors: list[str] = []
    ff_source = ff.read_text(encoding="utf-8") if ff.exists() else ""
    ff_ok = (
        len(ff_source.strip()) >= 200
        and (lesson["title"] in ff_source or lesson["id"] in ff_source)
    )
    if not ff_ok:
        errors.append("FF must contain at least 200 non-whitespace characters")
    cc_ok = False
    if cc.exists():
        source = cc.read_text(encoding="utf-8")
        lowered = source.lower()
        cc_ok = (
            len(source.encode("utf-8")) >= 300
            and ("<html" in lowered or "<!doctype html" in lowered)
            and not re.match(r"^\s*```(?:html)?", source, re.IGNORECASE)
            and not re.search(r"```\s*$", source)
            and not re.search(r"<script\b", source, re.IGNORECASE)
            and not re.search(
                r"<(?:script|link|img|iframe|source)\b[^>]*(?:src|href)=[\"']https?://",
                source,
                re.IGNORECASE,
            )
            and not re.search(
                r"id=[\"']ai-content-placeholder[\"'][^>]*(?:display\s*:\s*none|\bhidden\b)",
                source,
                re.IGNORECASE,
            )
            and (lesson["title"] in source or lesson["id"] in source)
        )
    if not cc_ok:
        errors.append(
            "CC must be complete self-contained HTML of at least 300 bytes without "
            "markdown fences, scripts, remote assets, or a hidden content root"
        )
    return ff_ok, cc_ok, errors


def provenance_gates(course_id: str, lesson: dict, kinds: set[str]) -> list[str]:
    """Return publication-blocking provenance errors for requested artifacts."""
    folder = lesson_dir(course_id, lesson)
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        return ["meta.json is required before completing an artifact"]
    try:
        meta = load_json(meta_path)
    except Exception as exc:
        return [f"meta.json is invalid: {exc}"]
    errors: list[str] = []
    if meta.get("version") != 2:
        errors.append("meta.json must be migrated to version 2")
    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict):
        return errors + ["meta.json artifacts must be an object"]
    for kind in sorted(kinds):
        filename = "ff.md" if kind == "ff" else "cc.html"
        path = folder / filename
        record = artifacts.get(kind)
        for error in artifact_record_errors(record, path):
            errors.append(f"{kind.upper()} {error}")
        if isinstance(record, dict) and record.get("producer") == "openai-codex":
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"{kind.upper()} cannot be read as UTF-8: {exc}")
            else:
                for error in codex_artifact_quality_errors(
                    kind, source, lesson["topics"]
                ):
                    errors.append(f"{kind.upper()} Codex quality gate: {error}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    parser.add_argument("status", choices=sorted(STATUSES))
    parser.add_argument("--error")
    args = parser.parse_args()

    curriculum = load_curriculum(args.course_id)
    lesson = find_lesson(curriculum, args.lesson_id)
    progress = load_or_create_progress(args.course_id)
    state = progress["lessons"][args.lesson_id]
    ff_ok, cc_ok, errors = gates(args.course_id, lesson)
    required_kinds: set[str] = set()
    if args.status in FF_REQUIRED_STATUSES:
        if not ff_ok:
            raise SystemExit("; ".join(errors))
        required_kinds.add("ff")
    if args.status in CC_REQUIRED_STATUSES:
        if not cc_ok:
            raise SystemExit("; ".join(errors))
        required_kinds.add("cc")
    provenance_errors = (
        provenance_gates(args.course_id, lesson, required_kinds)
        if required_kinds
        else []
    )
    if provenance_errors:
        raise SystemExit("; ".join(provenance_errors))
    if args.status == "failed" and not args.error:
        raise SystemExit("--error is required for failed status")

    state.update({
        "status": args.status,
        "ff": ff_ok,
        "cc": cc_ok,
        "url": lesson_url(args.course_id, lesson) if args.status == "published" else None,
        "last_error": args.error if args.status == "failed" else None,
    })
    progress["updated"] = now_kst()
    write_json(progress_path(args.course_id), progress)
    build_lesson(args.course_id, args.lesson_id)
    build_course(args.course_id)
    print(f"{args.course_id}:{args.lesson_id} -> {args.status}")


if __name__ == "__main__":
    main()
