#!/usr/bin/env python3
"""Attach explicit producer provenance and a content hash to one lesson artifact."""

from __future__ import annotations

import argparse

from build_lesson import build_lesson
from common import (
    ACTIVE_PRODUCERS,
    ARTIFACT_FILENAMES,
    artifact_record_errors,
    find_lesson,
    lesson_dir,
    load_curriculum,
    load_json,
    now_kst,
    sha256_file,
    write_json,
)
from prompt_profiles import get_prompt_profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record provenance after ff.md or cc.html has been generated."
    )
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    parser.add_argument("artifact", choices=sorted(ARTIFACT_FILENAMES))
    parser.add_argument("--producer", required=True, choices=sorted(ACTIVE_PRODUCERS))
    parser.add_argument("--prompt-profile", required=True)
    parser.add_argument(
        "--generated-at",
        help="ISO 8601 timestamp with UTC offset; defaults to the current KST time.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace a different existing provenance record explicitly.",
    )
    args = parser.parse_args()

    curriculum = load_curriculum(args.course_id)
    lesson = find_lesson(curriculum, args.lesson_id)
    folder = lesson_dir(args.course_id, lesson)
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        build_lesson(args.course_id, args.lesson_id)
    meta = load_json(meta_path)
    if meta.get("version") != 2:
        raise SystemExit(
            "meta.json is not version 2; run migrate_meta_v2.py before recording provenance"
        )
    if (
        meta.get("course_id") != args.course_id
        or meta.get("lesson_id") != args.lesson_id
    ):
        raise SystemExit("meta.json identifies a different lesson")

    artifact_path = folder / ARTIFACT_FILENAMES[args.artifact]
    if not artifact_path.exists():
        raise SystemExit(f"artifact file does not exist: {artifact_path}")
    prompt_profile = args.prompt_profile.strip()
    if not prompt_profile:
        raise SystemExit("--prompt-profile must not be blank")
    try:
        get_prompt_profile(
            prompt_profile,
            artifact_kind=args.artifact,
            producer=args.producer,
        )
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"invalid prompt profile selection: {exc}") from exc
    digest = sha256_file(artifact_path)
    record = {
        "producer": args.producer,
        "prompt_profile": prompt_profile,
        "generated_at": args.generated_at or now_kst(),
        "sha256": digest,
    }
    errors = artifact_record_errors(record, artifact_path)
    if errors:
        raise SystemExit("; ".join(errors))

    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("meta.json artifacts must be an object")
    existing = artifacts.get(args.artifact)
    if existing:
        same_identity = (
            existing.get("producer") == record["producer"]
            and existing.get("prompt_profile") == record["prompt_profile"]
            and existing.get("sha256") == record["sha256"]
        )
        if same_identity:
            print(
                f"{args.course_id}:{args.lesson_id}:{args.artifact} "
                "provenance already recorded"
            )
            return
        if not args.force:
            raise SystemExit(
                "a different provenance record already exists; use --force to replace it"
            )

    artifacts[args.artifact] = record
    write_json(meta_path, meta)
    print(
        f"{args.course_id}:{args.lesson_id}:{args.artifact} "
        f"{args.producer} {digest}"
    )


if __name__ == "__main__":
    main()
