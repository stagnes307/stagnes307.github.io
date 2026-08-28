#!/usr/bin/env python3
"""Publish the four curriculum-grounded public-Ailey certification courses."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import common
from ailey_public_profile import assemble_public_system_prompt
from build_course import build_course, sync_catalog
from build_lesson import build_lesson
from common import (
    course_dir,
    iter_lessons,
    lesson_dir,
    lesson_url,
    load_curriculum,
    new_progress,
    now_kst,
    progress_path,
    sha256_file,
    write_json,
)
from public_ailey_course_content import (
    CC_PROFILE,
    FF_PROFILE,
    atom_fact_catalog_errors,
    atom_fact_occurrences,
    build_lesson_context,
    corpus_content_quality_errors,
    public_ailey_content_quality_errors,
    render_ff,
    sample_audit_metrics,
    teaching_h3_fact_counts,
    teaching_fact_occurrences,
)
from render_ailey_public_cc import render_cc_document
from validation import meta_schema_errors, validate_course


SUPPORTED_COURSES = {
    "quality-management-engineer-written",
    "quality-management-engineer-practical",
    "industrial-safety-engineer-written",
    "industrial-safety-engineer-practical",
}
PRODUCER = "openai-codex"
HIGH_RISK_IDS = {
    "quality-management-engineer-written": """
        1-1-1-1 1-1-2-1 1-1-2-2 1-1-3-1 1-1-4-1 1-1-5-1 1-1-6-1
        1-1-7-1 1-1-8-1 1-1-9-1 1-1-10-1 1-1-11-1 2-1-1-1 2-1-2-1
        2-1-2-2 2-1-3-1 2-2-1-1 2-2-1-2 2-3-1-1 2-3-1-2 3-1-2-1
        3-3-1-1 3-4-1-2 4-1-1-1 4-1-1-2 4-1-2-1 4-1-3-1 4-1-3-2
        4-1-3-3 4-1-4-1 4-1-5-1 4-1-6-1 4-1-7-1 5-1-2-1 5-1-4-1
        5-1-5-1
    """.split(),
    "quality-management-engineer-practical": """
        1-1-2-1 1-1-2-2 1-1-3-1 1-2-1-1 1-2-2-1 1-2-3-1 1-3-1-1
        1-3-2-1 1-3-2-2 1-3-3-1 1-4-1-1 1-4-2-1 1-4-2-2 1-4-3-1
        1-4-3-2 1-5-1-1 1-5-2-1 1-5-3-1 1-7-1-1 1-7-2-1 1-7-2-2
        1-7-3-1 1-7-3-2
    """.split(),
    "industrial-safety-engineer-written": """
        1-1-1-2 2-1-4-2 2-2-2-1 2-2-2-2 2-3-1-1 2-4-2-1 2-4-3-1
        2-6-1-1 2-6-2-1 2-6-2-2 2-6-4-1 2-6-5-2 2-6-6-1 3-2-2-1
        3-2-2-2 4-1-1-1 4-1-1-2 4-2-1-1 4-2-2-1 4-2-2-2 4-2-3-1
        4-3-1-1 4-3-1-2 4-3-2-1 4-3-2-2 4-3-2-3 4-4-1-1 4-4-2-1
        4-4-2-2 4-5-1-1 4-5-1-2 4-5-1-3 4-5-2-1 5-1-1-1 5-1-1-2
        5-1-1-3 5-1-2-1 5-1-3-1 5-2-1-1 5-2-1-2 5-2-2-1 5-2-2-2
        5-2-3-1 5-2-3-2 5-4-1-1 6-1-1-1 6-1-2-1 6-2-1-1 6-2-2-1
        6-3-1-1 6-4-1-1 6-4-2-1 6-5-1-1 6-5-1-2 6-6-1-1 6-6-2-1
        6-6-3-1
    """.split(),
    "industrial-safety-engineer-practical": """
        1-1-2-2 1-3-3-1 1-7-1-1 1-7-1-2 1-7-2-1 1-7-3-1 1-7-3-2
        1-8-1-1 1-8-1-2 1-8-2-1 1-8-2-2 1-8-3-1 1-9-1-1 1-9-1-2
        1-9-2-1 1-9-3-1 1-9-4-1 1-9-4-2 1-10-1-1 1-10-1-2 1-10-2-1
        1-10-2-2 1-10-2-3 1-10-3-1 1-10-3-2 1-11-1-1 1-11-1-2
        1-11-2-1 1-11-2-2 1-12-1-1 1-12-2-1 1-12-2-2 1-12-3-1
        1-12-3-2 1-12-4-1 1-12-4-2 1-13-1-1 1-13-1-2 1-13-2-1
        1-13-2-2 1-13-3-1 1-13-3-2 1-14-1-1 1-14-1-2 1-14-2-1
        1-14-2-2 1-14-3-1 1-14-3-2 1-14-4-1 1-14-4-2 1-15-1-1
        1-15-1-2 1-15-2-1 1-15-2-2 1-15-3-1 1-15-3-2 1-15-3-3
        1-15-4-1 1-15-4-2 1-15-5-1 1-15-5-2 1-15-6-1 1-15-6-2
    """.split(),
}


@dataclass(frozen=True)
class PreparedLesson:
    lesson: dict
    ff_source: str
    cc_source: str
    meta: dict


def source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def lesson_meta(
    course_id: str,
    lesson: dict,
    *,
    timestamp: str,
    ff_sha256: str,
    cc_sha256: str,
) -> dict:
    """Build schema-v2 metadata without out-of-contract top-level fields."""
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
        "artifacts": {
            "ff": {
                "producer": PRODUCER,
                "prompt_profile": FF_PROFILE,
                "generated_at": timestamp,
                "sha256": ff_sha256,
            },
            "cc": {
                "producer": PRODUCER,
                "prompt_profile": CC_PROFILE,
                "generated_at": timestamp,
                "sha256": cc_sha256,
            },
        },
        "published_at": timestamp,
        "status": "published",
    }


def render_course_ffs(curriculum: dict) -> dict[str, str]:
    course_id = curriculum["course_id"]
    return {
        lesson["id"]: render_ff(course_id, curriculum, lesson)
        for lesson in iter_lessons(curriculum)
    }


def audit_rendered_course(
    course_id: str,
    curriculum: dict,
    all_rendered: dict[str, str],
) -> dict[str, object]:
    lessons = {lesson["id"]: lesson for lesson in iter_lessons(curriculum)}
    missing = sorted(set(HIGH_RISK_IDS[course_id]) - lessons.keys())
    if missing:
        raise ValueError(f"{course_id}: high-risk audit ids missing from curriculum: {missing}")
    catalog_errors = atom_fact_catalog_errors(course_id, curriculum)
    if catalog_errors:
        raise ValueError("atom fact catalog failed: " + "; ".join(catalog_errors))
    corpus_errors = corpus_content_quality_errors(course_id, curriculum, all_rendered)
    if corpus_errors:
        raise ValueError("full-curriculum content audit failed: " + "; ".join(corpus_errors))
    representative = {
        f"{course_id}:{lesson_id}": all_rendered[lesson_id]
        for lesson_id in HIGH_RISK_IDS[course_id]
    }
    contexts = {
        f"{course_id}:{lesson_id}": build_lesson_context(
            course_id,
            curriculum,
            lessons[lesson_id],
        )
        for lesson_id in HIGH_RISK_IDS[course_id]
    }
    metrics = sample_audit_metrics(representative, contexts)
    if any(item["duplicate_rate"] > 0.02 for item in metrics["documents"].values()):
        raise ValueError(f"{course_id}: sample exact-sentence repetition exceeds 2 percent")
    if metrics["max_pairwise_common_sentences"] > 3:
        raise ValueError(f"{course_id}: representative lessons share too many exact sentences")
    if metrics["max_pairwise_fact_overlap"] > 0.25:
        raise ValueError(f"{course_id}: representative atom-fact overlap exceeds 25 percent")
    return metrics


def preflight_course(course_id: str, curriculum: dict) -> dict[str, object]:
    return audit_rendered_course(course_id, curriculum, render_course_ffs(curriculum))


def print_audit(course_id: str, metrics: dict[str, object]) -> None:
    print(
        f"{course_id}: sample audit "
        f"max_pairwise_common={metrics['max_pairwise_common_sentences']} "
        f"max_fact_overlap={metrics['max_pairwise_fact_overlap']:.3f}"
    )
    for key, item in metrics["documents"].items():
        print(
            f"  {key}: sentences={item['sentence_count']} "
            f"unique={item['unique_sentence_count']} duplicate_rate={item['duplicate_rate']:.4f} "
            f"semantic_duplicate_rate={item['semantic_duplicate_rate']:.4f} "
            f"repeated_5gram_rate={item['repeated_5gram_rate']:.4f}"
        )


def write_artifact(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"artifact already exists: {path}")
    path.write_text(source, encoding="utf-8", newline="\n")


def atomic_replace_bytes(path: Path, payload: bytes) -> None:
    """Replace one file from a same-directory temporary without truncation."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.rollback-",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def prepare_course(
    course_id: str,
    curriculum: dict,
    *,
    timestamp: str | None = None,
) -> tuple[dict[str, object], list[PreparedLesson]]:
    """Render and validate a complete course without touching the filesystem."""
    all_rendered = render_course_ffs(curriculum)
    metrics = audit_rendered_course(course_id, curriculum, all_rendered)
    generated_at = timestamp or now_kst()
    prepared = []
    for lesson in iter_lessons(curriculum):
        ff_source = all_rendered[lesson["id"]]
        errors = public_ailey_content_quality_errors(
            course_id,
            curriculum,
            lesson,
            ff_source,
        )
        if errors:
            raise ValueError(
                f"{course_id}:{lesson['id']}: content gates failed: "
                + "; ".join(errors)
            )
        cc_source = render_cc_document(
            course_id,
            curriculum,
            lesson,
            ff_source,
        )
        metadata = lesson_meta(
            course_id,
            lesson,
            timestamp=generated_at,
            ff_sha256=source_sha256(ff_source),
            cc_sha256=source_sha256(cc_source),
        )
        metadata_errors = meta_schema_errors(metadata)
        if metadata_errors:
            raise ValueError(
                f"{course_id}:{lesson['id']}: metadata schema failed: "
                + "; ".join(metadata_errors)
            )
        prepared.append(PreparedLesson(
            lesson=lesson,
            ff_source=ff_source,
            cc_source=cc_source,
            meta=metadata,
        ))
    return metrics, prepared


def stage_course(
    course_id: str,
    curriculum: dict,
    prepared: list[PreparedLesson],
    staging_root: Path,
) -> dict:
    """Build every course file below an isolated temporary courses root."""
    previous_courses_dir = common.COURSES_DIR
    common.COURSES_DIR = staging_root
    try:
        progress = new_progress(curriculum)
        for item in prepared:
            lesson = item.lesson
            folder = lesson_dir(course_id, lesson)
            ff_path = folder / "ff.md"
            cc_path = folder / "cc.html"
            write_artifact(ff_path, item.ff_source)
            write_artifact(cc_path, item.cc_source)
            write_json(folder / "meta.json", item.meta)
            if sha256_file(ff_path) != item.meta["artifacts"]["ff"]["sha256"]:
                raise ValueError(f"{course_id}:{lesson['id']}: staged FF hash mismatch")
            if sha256_file(cc_path) != item.meta["artifacts"]["cc"]["sha256"]:
                raise ValueError(f"{course_id}:{lesson['id']}: staged CC hash mismatch")
            progress["lessons"][lesson["id"]].update({
                "status": "published",
                "ff": True,
                "cc": True,
                "url": lesson_url(course_id, lesson),
                "last_error": None,
            })
        progress["updated"] = now_kst()
        write_json(progress_path(course_id), progress)
        for item in prepared:
            build_lesson(course_id, item.lesson["id"])
        build_course(course_id, sync_catalog_entry=False)
        report = validate_course(course_id)
        if report.errors or report.warnings:
            messages = [
                *(f"error: {message}" for message in report.errors),
                *(f"warning: {message}" for message in report.warnings),
            ]
            raise ValueError(
                f"{course_id}: staged course validation failed: "
                + "; ".join(messages)
            )
        return progress
    finally:
        common.COURSES_DIR = previous_courses_dir


def publish_course(course_id: str) -> tuple[int, list[str]]:
    if course_id not in SUPPORTED_COURSES:
        raise ValueError(f"unsupported course id: {course_id}")
    assemble_public_system_prompt()
    curriculum = load_curriculum(course_id)
    target = course_dir(course_id)
    if target.exists():
        raise FileExistsError(
            f"bulk generator only creates an absent course tree: {target}"
        )
    metrics, prepared = prepare_course(course_id, curriculum)
    print_audit(course_id, metrics)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=target.parent,
        prefix=".stage-",
        ignore_cleanup_errors=True,
    ) as temporary:
        staging_root = Path(temporary)
        progress = stage_course(
            course_id,
            curriculum,
            prepared,
            staging_root,
        )
        staged_course = staging_root / course_id
        if not staged_course.is_dir():
            raise FileNotFoundError(f"staged course tree is missing: {staged_course}")
        catalog_before = common.CATALOG_PATH.read_bytes()
        try:
            sync_catalog(curriculum, progress, len(prepared), len(prepared))
            os.replace(staged_course, target)
        except Exception as publish_error:
            try:
                atomic_replace_bytes(common.CATALOG_PATH, catalog_before)
            except Exception as rollback_error:
                publish_error.add_note(
                    f"catalog rollback also failed: {rollback_error}"
                )
            raise
    return len(prepared), []


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the four pinned public-Ailey courses")
    parser.add_argument("course_ids", nargs="+", choices=sorted(SUPPORTED_COURSES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    assemble_public_system_prompt()
    if args.dry_run:
        for course_id in args.course_ids:
            curriculum = load_curriculum(course_id)
            print(f"{course_id}: {sum(1 for _ in iter_lessons(curriculum))} lesson(s)")
            print_audit(course_id, preflight_course(course_id, curriculum))
        return 0
    failures = []
    for course_id in args.course_ids:
        completed, current = publish_course(course_id)
        print(f"{course_id}: published {completed} lesson(s)")
        failures.extend(current)
    if failures:
        raise SystemExit("\n".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
