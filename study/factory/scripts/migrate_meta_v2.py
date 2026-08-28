#!/usr/bin/env python3
"""Plan or apply the one-time lesson provenance migration to meta version 2."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    CURRICULA_DIR,
    iter_lessons,
    lesson_dir,
    load_curriculum,
    load_json,
    now_kst,
    progress_path,
    sha256_file,
    write_json,
)


LEGACY_PROFILE = "ailey-legacy-unknown"


def legacy_generated_at(meta: dict[str, Any], kind: str, path: Path) -> str:
    value = meta.get(f"{kind}_generated_at") or meta.get("published_at")
    if isinstance(value, str) and value:
        return value
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
        timespec="seconds"
    )


def legacy_record(
    meta: dict[str, Any],
    kind: str,
    path: Path,
) -> dict[str, str]:
    return {
        "producer": "ailey-bailey-custom-gpt",
        "prompt_profile": LEGACY_PROFILE,
        "generated_at": legacy_generated_at(meta, kind, path),
        "sha256": sha256_file(path),
    }


def canonical_meta(
    course_id: str,
    lesson: dict[str, Any],
    state: dict[str, Any],
    old_meta: dict[str, Any],
    folder: Path,
) -> tuple[dict[str, Any], int]:
    old_artifacts = old_meta.get("artifacts")
    if not isinstance(old_artifacts, dict):
        old_artifacts = {}
    artifacts: dict[str, Any] = {"ff": None, "cc": None}
    legacy_records = 0
    for kind, filename in (("ff", "ff.md"), ("cc", "cc.html")):
        path = folder / filename
        existing = old_artifacts.get(kind)
        has_legacy_evidence = (
            state.get(kind) is True
            and isinstance(old_meta.get(f"{kind}_generated_at"), str)
            and bool(old_meta.get(f"{kind}_generated_at"))
            and path.exists()
        )
        if isinstance(existing, dict):
            artifacts[kind] = existing
        elif has_legacy_evidence:
            artifacts[kind] = legacy_record(old_meta, kind, path)
            legacy_records += 1
        elif state.get("status") == "published":
            raise ValueError(
                f"{course_id}:{lesson['id']}: cannot prove legacy provenance for "
                f"{filename}"
            )

    published_at = old_meta.get("published_at")
    if state.get("status") == "published" and not isinstance(published_at, str):
        cc_record = artifacts["cc"]
        ff_record = artifacts["ff"]
        published_at = (cc_record or ff_record)["generated_at"]

    return {
        "version": 2,
        "course_id": course_id,
        "lesson_id": lesson["id"],
        "title": lesson["title"],
        "slug": lesson["slug"],
        "section_id": lesson["section_id"],
        "section_title": lesson["section_title"],
        "unit_id": lesson["unit_id"],
        "unit_title": lesson["unit_title"],
        "lesson_group_id": lesson["lesson_group_id"],
        "lesson_group_title": lesson["lesson_group_title"],
        "topics": lesson["topics"],
        "artifacts": artifacts,
        "published_at": published_at,
        "status": state["status"],
    }, legacy_records


def course_ids_from_index() -> list[str]:
    index = load_json(CURRICULA_DIR / "index.json")
    return [entry["id"] for entry in index.get("courses", [])]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run by default. Use --write only after reviewing the exact counts."
        )
    )
    parser.add_argument("course_ids", nargs="*")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply meta/progress changes. FF and CC content is never written.",
    )
    parser.add_argument(
        "--expect-published",
        type=int,
        help="Abort if the selected courses do not contain this many published lessons.",
    )
    args = parser.parse_args()

    course_ids = args.course_ids or course_ids_from_index()
    published_count = 0
    reset_count = 0
    changed_meta_count = 0
    legacy_record_count = 0
    writes: list[tuple[Path, dict[str, Any]]] = []

    for course_id in course_ids:
        curriculum = load_curriculum(course_id)
        progress_file = progress_path(course_id)
        if not progress_file.exists():
            continue
        progress = load_json(progress_file)
        original_progress = load_json(progress_file)
        lessons_by_id = {
            lesson["id"]: lesson for lesson in iter_lessons(curriculum)
        }
        for lesson_id, state in progress.get("lessons", {}).items():
            lesson = lessons_by_id.get(lesson_id)
            if lesson is None:
                raise SystemExit(f"{course_id}:{lesson_id}: lesson is not in curriculum")
            folder = lesson_dir(course_id, lesson)
            meta_path = folder / "meta.json"
            old_meta = load_json(meta_path) if meta_path.exists() else {}
            is_published = state.get("status") == "published"
            if is_published:
                published_count += 1

            # The two interrupted legacy runs never completed FF according to
            # progress. A newly generated untracked file may now share the folder;
            # preserve that file, but do not mislabel it as an Ailey artifact.
            stale_ff_run = (
                state.get("status") == "ff-running"
                and state.get("ff") is False
            )
            if stale_ff_run:
                state.update({
                    "status": "pending",
                    "ff": False,
                    "cc": False,
                    "url": None,
                    "last_error": None,
                })
                reset_count += 1

            if not is_published and not stale_ff_run and not meta_path.exists():
                continue
            new_meta, created_legacy = canonical_meta(
                course_id, lesson, state, old_meta, folder
            )
            legacy_record_count += created_legacy
            if new_meta != old_meta:
                changed_meta_count += 1
                writes.append((meta_path, new_meta))

        if progress != original_progress:
            progress["updated"] = now_kst()
            writes.append((progress_file, progress))

    if args.expect_published is not None and published_count != args.expect_published:
        raise SystemExit(
            f"published lesson count mismatch: expected {args.expect_published}, "
            f"found {published_count}"
        )

    mode = "WRITE" if args.write else "DRY RUN"
    print(
        f"{mode}: courses={len(course_ids)} published={published_count} "
        f"meta_changes={changed_meta_count} legacy_records={legacy_record_count} "
        f"stale_ff_running_resets={reset_count}"
    )
    if args.write:
        for path, value in writes:
            write_json(path, value)
        print(f"wrote {len(writes)} JSON file(s); FF/CC artifacts were not modified")
    else:
        print("no files written; rerun with --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
