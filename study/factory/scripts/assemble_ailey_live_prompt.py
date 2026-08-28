#!/usr/bin/env python3
"""Assemble the pinned GitHub Ailey prompt for a real Codex live session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ailey_public_profile import AILEY_COMMIT, assemble_upstream_prompt
from common import find_lesson, lesson_list, load_curriculum
from prompt_profiles import get_prompt_profile
from sanitize_ailey_github_cc import FF_PROFILE


LIVE_SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "ailey-bailey-github-codex-live-v1.md"
)


def build_exact_ff_message(curriculum: dict[str, Any], lesson: dict[str, Any]) -> str:
    """Build the exact user turn; source metadata is deliberately kept outside it."""
    return "\n".join([
        f".ff {curriculum['title']}",
        f"{lesson['unit_id']}. {lesson['unit_title']}",
        f"{lesson['lesson_group_id']}. {lesson['lesson_group_title']}",
        f"{lesson['id']}. {lesson['title']}",
        *(f"- {topic}" for topic in lesson["topics"]),
    ])


def _selected_sources(
    curriculum: dict[str, Any],
    lesson: dict[str, Any],
) -> list[dict[str, Any]]:
    by_id = {
        source.get("id"): source
        for source in curriculum.get("sources", [])
        if isinstance(source, dict)
    }
    result: list[dict[str, Any]] = []
    for source_id in lesson.get("source_refs", []):
        source = by_id.get(source_id)
        if source is None:
            raise ValueError(f"unknown source {source_id!r} for {lesson['id']}")
        result.append({
            key: source.get(key)
            for key in (
                "id", "title", "authority", "url", "effective_from",
                "effective_to", "retrieved_at", "notes",
            )
            if source.get(key) is not None
        })
    return result


def build_runtime_context(
    curriculum: dict[str, Any],
    lesson: dict[str, Any],
) -> dict[str, Any]:
    lessons = lesson_list(curriculum)
    index = next(
        position for position, candidate in enumerate(lessons)
        if candidate["id"] == lesson["id"]
    )

    def adjacent(position: int) -> dict[str, str] | None:
        if not 0 <= position < len(lessons):
            return None
        candidate = lessons[position]
        return {"id": candidate["id"], "title": candidate["title"]}

    return {
        "prompt_profile": FF_PROFILE,
        "upstream_commit": AILEY_COMMIT,
        "course_id": curriculum["course_id"],
        "course_title": curriculum["title"],
        "curriculum_verified_at": curriculum.get("verified_at"),
        "lesson": {
            "id": lesson["id"],
            "title": lesson["title"],
            "section_id": lesson["section_id"],
            "section_title": lesson["section_title"],
            "unit_id": lesson["unit_id"],
            "unit_title": lesson["unit_title"],
            "lesson_group_id": lesson["lesson_group_id"],
            "lesson_group_title": lesson["lesson_group_title"],
            "topics": lesson["topics"],
            "lesson_type": lesson.get("lesson_type"),
            "supplemental": lesson.get("supplemental", False),
            "official_basis": lesson.get("official_basis", []),
        },
        "previous_lesson": adjacent(index - 1),
        "next_lesson": adjacent(index + 1),
        "sources": _selected_sources(curriculum, lesson),
    }


def assemble_live_codex_prompt(course_id: str, lesson_id: str) -> tuple[str, str]:
    """Return model instructions and the separate exact initial `.ff` user turn."""
    get_prompt_profile(
        FF_PROFILE,
        artifact_kind="ff",
        producer="openai-codex",
    )
    curriculum = load_curriculum(course_id)
    lesson = find_lesson(curriculum, lesson_id)
    upstream = assemble_upstream_prompt().rstrip("\n")
    live_spec = LIVE_SPEC_PATH.read_text(encoding="utf-8").strip()
    exact_user = build_exact_ff_message(curriculum, lesson)
    context = json.dumps(
        build_runtime_context(curriculum, lesson),
        ensure_ascii=False,
        indent=2,
    )
    fingerprint = hashlib.sha256(upstream.encode("utf-8")).hexdigest()
    model_instructions = f"""You are executing one isolated Study Factory generation session.
Do not edit files, call tools, or discuss your process. Return only the assistant
response to each user message.

The pinned GitHub material below is the active Ailey & Bailey behavior
specification. The user-authorized live profile after it is the more specific
runtime contract and overrides only conflicts needed for this Study Factory run.

<<<PINNED_GITHUB_AILEY_PROMPT commit={AILEY_COMMIT} sha256={fingerprint}>>>
{upstream}
<<<END_PINNED_GITHUB_AILEY_PROMPT>>>

<<<USER_AUTHORIZED_LIVE_PROFILE>>>
{live_spec}
<<<END_USER_AUTHORIZED_LIVE_PROFILE>>>

The following JSON is system-side grounding and navigation context. It is not
part of the user's `.ff` message. Do not quote the JSON or print source URLs.
Use it to avoid inventing neighboring lessons and to bound time-sensitive facts.

<<<FACTORY_RUNTIME_CONTEXT>>>
{context}
<<<END_FACTORY_RUNTIME_CONTEXT>>>

This is a specific lesson already selected inside a verified curriculum. Execute
the `.ff` lesson path directly. Generate the complete detailed FF now, including
the exact identity/topics and the confirmation/answer/summary requirements from
the live profile. Do not return a curriculum proposal.
"""
    return model_instructions, exact_user


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    parser.add_argument(
        "--part",
        choices=("all", "user", "context", "upstream", "live-spec"),
        default="all",
    )
    args = parser.parse_args()
    curriculum = load_curriculum(args.course_id)
    lesson = find_lesson(curriculum, args.lesson_id)
    if args.part == "user":
        value = build_exact_ff_message(curriculum, lesson)
    elif args.part == "context":
        value = json.dumps(
            build_runtime_context(curriculum, lesson),
            ensure_ascii=False,
            indent=2,
        )
    elif args.part == "upstream":
        value = assemble_upstream_prompt()
    elif args.part == "live-spec":
        value = LIVE_SPEC_PATH.read_text(encoding="utf-8")
    else:
        value, _ = assemble_live_codex_prompt(args.course_id, args.lesson_id)
    print(value, end="" if value.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
