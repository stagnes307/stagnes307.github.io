#!/usr/bin/env python3
"""Generate a four-part learning lesson viewer and metadata."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from common import (
    find_lesson,
    lesson_dir,
    lesson_list,
    lesson_url,
    load_curriculum,
    load_json,
    load_or_create_progress,
    now_kst,
    render_template,
    write_json,
)


def nav_link(label: str, lesson: dict | None, course_id: str, css: str) -> str:
    if lesson is None:
        return f'<span class="lesson-nav-link disabled {css}">{label}</span>'
    return (
        f'<a class="lesson-nav-link {css}" href="{html.escape(lesson_url(course_id, lesson))}">'
        f'<small>{label}</small><strong>{html.escape(lesson["id"])}. {html.escape(lesson["title"])}</strong></a>'
    )


def build_lesson(course_id: str, lesson_id: str) -> Path:
    curriculum = load_curriculum(course_id)
    progress = load_or_create_progress(course_id)
    lessons = lesson_list(curriculum)
    lesson = find_lesson(curriculum, lesson_id)
    position = next(index for index, item in enumerate(lessons) if item["id"] == lesson_id)
    previous = lessons[position - 1] if position else None
    following = lessons[position + 1] if position + 1 < len(lessons) else None
    folder = lesson_dir(course_id, lesson)
    folder.mkdir(parents=True, exist_ok=True)
    state = progress["lessons"][lesson_id]
    meta_path = folder / "meta.json"
    meta = load_json(meta_path) if meta_path.exists() else {}
    timestamp = now_kst()
    meta.update({
        "version": 1,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "slug": lesson["slug"],
        "section_id": lesson["section_id"],
        "section_title": lesson["section_title"],
        "unit_id": lesson["unit_id"],
        "unit_title": lesson["unit_title"],
        "lesson_group_id": lesson["lesson_group_id"],
        "lesson_group_title": lesson["lesson_group_title"],
        "topics": lesson["topics"],
        "generator": "Ailey & Bailey",
        "ff_generated_at": meta.get("ff_generated_at") or (timestamp if state.get("ff") else None),
        "cc_generated_at": meta.get("cc_generated_at") or (timestamp if state.get("cc") else None),
        "published_at": meta.get("published_at") or (timestamp if state.get("status") == "published" else None),
        "status": state["status"],
    })
    write_json(meta_path, meta)

    topic_chips = "".join(f"<li>{html.escape(topic)}</li>" for topic in lesson["topics"])
    shell = render_template("lesson.html", {
        "PAGE_TITLE": html.escape(f"{lesson_id}. {lesson['title']} · {curriculum['title']}"),
        "COURSE_TITLE": html.escape(curriculum["title"]),
        "COURSE_URL": f"/study/courses/{course_id}/",
        "SECTION_ID": html.escape(lesson["section_id"]),
        "SECTION_TITLE": html.escape(lesson["section_title"]),
        "UNIT_ID": html.escape(lesson["unit_id"]),
        "UNIT_TITLE": html.escape(lesson["unit_title"]),
        "GROUP_ID": html.escape(lesson["lesson_group_id"]),
        "GROUP_TITLE": html.escape(lesson["lesson_group_title"]),
        "LESSON_ID": html.escape(lesson_id),
        "LESSON_TITLE": html.escape(lesson["title"]),
        "TOPIC_CHIPS": topic_chips,
        "PREVIOUS_LINK": nav_link("이전 Lesson", previous, course_id, "previous"),
        "NEXT_LINK": nav_link("다음 Lesson", following, course_id, "next"),
    })
    output = folder / "index.html"
    output.write_text(shell, encoding="utf-8", newline="\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    args = parser.parse_args()
    print(build_lesson(args.course_id, args.lesson_id))


if __name__ == "__main__":
    main()
