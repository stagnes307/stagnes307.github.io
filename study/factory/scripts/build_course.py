#!/usr/bin/env python3
"""Generate a course table-of-contents page and synchronize its catalog card."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from common import (
    CATALOG_PATH,
    course_dir,
    iter_lessons,
    lesson_url,
    load_curriculum,
    load_json,
    load_or_create_progress,
    render_template,
    today_kst,
    write_json,
)
from question_bank_common import question_bank_public_data_path


STATUS_ICON = {
    "published": "✓",
    "failed": "!",
    "pending": "○",
    "ff-running": "◐",
    "ff-complete": "◐",
    "cc-running": "◐",
    "cc-complete": "◐",
    "publishing": "◐",
}


def question_bank_cta(course_id: str) -> str:
    if not question_bank_public_data_path(course_id).exists():
        return ""
    return (
        '<section class="question-bank-cta" aria-labelledby="question-bank-heading">'
        '<div><p class="eyebrow">PAST EXAM EVIDENCE</p>'
        '<h2 id="question-bank-heading">기출·출제분석</h2>'
        '<p>관측 기출을 Lesson에 연결하고 자료 coverage와 근거 수준을 함께 확인합니다.</p></div>'
        f'<a href="/study/courses/{html.escape(course_id)}/questions/">분석·문제풀이 열기</a>'
        '</section>'
    )


def build_outline(curriculum: dict, progress: dict) -> str:
    parts: list[str] = []
    for section in curriculum["sections"]:
        parts.append(f'<section class="course-section"><h2>{html.escape(section["id"])}. {html.escape(section["title"])}</h2>')
        for unit in section["units"]:
            parts.append(f'<div class="course-unit"><h3>{html.escape(unit["id"])}. {html.escape(unit["title"])}</h3>')
            for group in unit["lessons"]:
                parts.append(f'<div class="lesson-group"><h4>{html.escape(group["id"])}. {html.escape(group["title"])}</h4><ol>')
                for lesson in group["sublessons"]:
                    state = progress["lessons"][lesson["id"]]
                    status = state["status"]
                    label = f'{lesson["id"]}. {lesson["title"]}'
                    if status == "published":
                        title = f'<a href="{html.escape(lesson_url(curriculum["course_id"], lesson))}">{html.escape(label)}</a>'
                    else:
                        title = f'<span>{html.escape(label)}</span>'
                    parts.append(
                        f'<li class="status-{html.escape(status)}"><b aria-label="{html.escape(status)}">{STATUS_ICON[status]}</b>'
                        f'<div>{title}<small>{html.escape(" · ".join(lesson["topics"]))}</small></div></li>'
                    )
                parts.append("</ol></div>")
            parts.append("</div>")
        parts.append("</section>")
    return "".join(parts)


def sync_catalog(curriculum: dict, progress: dict, completed: int, total: int) -> None:
    catalog = load_json(CATALOG_PATH)
    course_id = curriculum["course_id"]
    course_url = f"/study/courses/{course_id}/"
    first_published = next(
        (lesson for lesson in iter_lessons(curriculum) if progress["lessons"][lesson["id"]]["status"] == "published"),
        None,
    )
    continue_url = lesson_url(course_id, first_published) if completed == total and first_published else course_url
    existing = next((item for item in catalog["items"] if item.get("id") == course_id), None)
    created = existing.get("created") if existing else today_kst()
    entry = {
        "id": course_id,
        "kind": "course",
        "title": curriculum["title"],
        "description": curriculum.get("description", f"{curriculum['title']} 공식 출제기준 기반 학습 과정."),
        "category": "certification",
        "subcategory": course_id,
        "tags": curriculum.get("tags", [curriculum["certification"], curriculum["mode"]]),
        "level": "intermediate",
        "url": course_url,
        "created": created,
        "updated": today_kst(),
        "total_lessons": total,
        "completed_lessons": completed,
        "progress_percent": round(completed * 100 / total) if total else 0,
        "continue_url": continue_url,
    }
    if existing:
        existing.clear()
        existing.update(entry)
    else:
        catalog["items"].append(entry)
    catalog["updated"] = today_kst()
    write_json(CATALOG_PATH, catalog)


def build_course(course_id: str, *, sync_catalog_entry: bool = True) -> Path:
    curriculum = load_curriculum(course_id)
    progress = load_or_create_progress(course_id)
    all_lessons = list(iter_lessons(curriculum))
    completed = sum(progress["lessons"][lesson["id"]]["status"] == "published" for lesson in all_lessons)
    total = len(all_lessons)
    percent = round(completed * 100 / total) if total else 0
    output = course_dir(course_id) / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_template("course.html", {
        "PAGE_TITLE": html.escape(curriculum["title"]),
        "COURSE_TITLE": html.escape(curriculum["title"]),
        "COURSE_DESCRIPTION": html.escape(curriculum.get("description", "공식 출제기준 기반 학습 과정")),
        "COMPLETED": str(completed),
        "TOTAL": str(total),
        "PERCENT": str(percent),
        "QUESTION_BANK_CTA": question_bank_cta(course_id),
        "COURSE_OUTLINE": build_outline(curriculum, progress),
    }), encoding="utf-8", newline="\n")
    if sync_catalog_entry:
        sync_catalog(curriculum, progress, completed, total)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    args = parser.parse_args()
    print(build_course(args.course_id))


if __name__ == "__main__":
    main()
