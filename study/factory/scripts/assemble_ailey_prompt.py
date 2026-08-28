#!/usr/bin/env python3
"""Assemble the pinned public Ailey system prompt and one FF lesson request."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ailey_public_profile import (
    AILEY_COMMIT,
    AILEY_FF_PROFILE,
    assemble_public_system_prompt,
)
from common import find_lesson, load_curriculum
from prompt_profiles import get_prompt_profile


def _selected_sources(
    curriculum: dict[str, Any],
    lesson: dict[str, Any],
) -> list[dict[str, Any]]:
    source_by_id = {
        source.get("id"): source
        for source in curriculum.get("sources", [])
        if isinstance(source, dict)
    }
    selected: list[dict[str, Any]] = []
    for source_id in lesson.get("source_refs", []):
        source = source_by_id.get(source_id)
        if source is None:
            raise ValueError(
                f"lesson {lesson['id']} references unknown source {source_id!r}"
            )
        selected.append({
            "id": source.get("id"),
            "title": source.get("title"),
            "authority": source.get("authority"),
            "url": source.get("url"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "retrieved_at": source.get("retrieved_at"),
        })
    return selected


def build_lesson_request(
    curriculum: dict[str, Any],
    lesson: dict[str, Any],
) -> str:
    """Build the legacy-compatible .ff request plus authoritative source packet."""
    command_lines = [
        f".ff {curriculum['title']}",
        f"{lesson['unit_id']}. {lesson['unit_title']}",
        f"{lesson['lesson_group_id']}. {lesson['lesson_group_title']}",
        f"{lesson['id']}. {lesson['title']}",
        *(f"- {topic}" for topic in lesson["topics"]),
    ]
    packet = {
        "prompt_profile": AILEY_FF_PROFILE,
        "upstream_commit": AILEY_COMMIT,
        "course_id": curriculum["course_id"],
        "course_title": curriculum["title"],
        "certification": curriculum.get("certification"),
        "mode": curriculum.get("mode"),
        "course_authority": curriculum.get("authority"),
        "curriculum_verified_at": curriculum.get("verified_at"),
        "section": {
            "id": lesson["section_id"],
            "title": lesson["section_title"],
        },
        "unit": {
            "id": lesson["unit_id"],
            "title": lesson["unit_title"],
        },
        "lesson_group": {
            "id": lesson["lesson_group_id"],
            "title": lesson["lesson_group_title"],
        },
        "learning_lesson": {
            "id": lesson["id"],
            "title": lesson["title"],
            "slug": lesson["slug"],
            "topics": lesson["topics"],
            "lesson_type": lesson.get("lesson_type"),
            "supplemental": lesson.get("supplemental"),
            "official_basis": lesson.get("official_basis", []),
            "source_refs": lesson.get("source_refs", []),
        },
        "sources": _selected_sources(curriculum, lesson),
    }
    packet_json = json.dumps(packet, ensure_ascii=False, indent=2)
    return (
        "\n".join(command_lines)
        + "\n\n[STUDY_FACTORY_SOURCE_PACKET]\n"
        + packet_json
        + "\n[/STUDY_FACTORY_SOURCE_PACKET]\n"
    )


def assemble_prompt(
    course_id: str,
    lesson_id: str,
) -> tuple[str, str]:
    """Return (system specification, user request) for one public-Ailey FF."""
    get_prompt_profile(
        AILEY_FF_PROFILE,
        artifact_kind="ff",
        producer="openai-codex",
    )
    curriculum = load_curriculum(course_id)
    lesson = find_lesson(curriculum, lesson_id)
    return (
        assemble_public_system_prompt(),
        build_lesson_request(curriculum, lesson),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble the pinned public Ailey prompt for one Study Factory FF. "
            "This command never emits or executes upstream .cc/.ccc HTML."
        )
    )
    parser.add_argument("course_id_positional", nargs="?")
    parser.add_argument("lesson_id_positional", nargs="?")
    parser.add_argument("--course-id")
    parser.add_argument("--lesson-id")
    parser.add_argument(
        "--part",
        choices=("all", "system", "user"),
        default="all",
        help="print the full two-message bundle or one message only",
    )
    args = parser.parse_args()
    course_id = args.course_id or args.course_id_positional
    lesson_id = args.lesson_id or args.lesson_id_positional
    if (
        args.course_id
        and args.course_id_positional
        and args.course_id != args.course_id_positional
    ):
        parser.error("positional course id and --course-id disagree")
    if (
        args.lesson_id
        and args.lesson_id_positional
        and args.lesson_id != args.lesson_id_positional
    ):
        parser.error("positional lesson id and --lesson-id disagree")
    if not course_id or not lesson_id:
        parser.error("course and lesson are required (positional or named flags)")
    try:
        system_prompt, user_prompt = assemble_prompt(
            course_id,
            lesson_id,
        )
    except (KeyError, OSError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    if args.part == "system":
        print(system_prompt, end="")
    elif args.part == "user":
        print(user_prompt, end="")
    else:
        print("<<<SYSTEM_SPEC>>>")
        print(system_prompt, end="")
        print("<<<END_SYSTEM_SPEC>>>")
        print("<<<USER_MESSAGE>>>")
        print(user_prompt, end="")
        print("<<<END_USER_MESSAGE>>>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
