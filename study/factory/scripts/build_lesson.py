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
from question_bank_common import question_bank_public_data_path, question_bank_url


def nav_link(label: str, lesson: dict | None, course_id: str, css: str) -> str:
    if lesson is None:
        return f'<span class="lesson-nav-link disabled {css}">{label}</span>'
    return (
        f'<a class="lesson-nav-link {css}" href="{html.escape(lesson_url(course_id, lesson))}">'
        f'<small>{label}</small><strong>{html.escape(lesson["id"])}. {html.escape(lesson["title"])}</strong></a>'
    )


def cc_nav_link(
    label: str,
    lesson: dict | None,
    course_id: str,
    css: str,
    aria_label: str | None = None,
) -> str:
    aria = f' aria-label="{html.escape(aria_label)}"' if aria_label else ""
    if lesson is None:
        return (
            f'<span class="cc-nav-button disabled {css}" aria-disabled="true"{aria}>'
            f'{html.escape(label)}</span>'
        )
    return (
        f'<a class="cc-nav-button {css}" '
        f'href="{html.escape(lesson_url(course_id, lesson))}cc-view.html"{aria}>'
        f'{html.escape(label)}</a>'
    )


def question_bank_summary(
    course_id: str,
    lesson_id: str,
    *,
    dataset: dict | None = None,
) -> str:
    """Render a compact evidence link without modifying FF/CC artifacts."""
    if dataset is None:
        path = question_bank_public_data_path(course_id)
        if not path.exists():
            return ""
        try:
            dataset = load_json(path)
        except (OSError, ValueError):
            return ""
    topic = next(
        (item for item in dataset.get("topics", []) if item.get("code") == lesson_id),
        None,
    )
    if topic is None:
        return ""
    observed = int(topic.get("observed_questions") or 0)
    rounds = int(topic.get("distinct_rounds") or 0)
    evidence = {
        "limited": "근거 부족",
        "provisional": "잠정",
        "sufficient": "충분",
    }.get(topic.get("evidence_level"), "근거 확인 필요")
    score = topic.get("importance_score")
    importance = f"중요도 {score:.1f}" if isinstance(score, (int, float)) else "중요도 산정 전"
    href = f"{question_bank_url(course_id)}?topic={html.escape(lesson_id)}"
    return (
        '<aside class="lesson-question-evidence" aria-label="관련 기출 근거">'
        '<div><p class="eyebrow">PAST EXAM EVIDENCE</p>'
        f'<h2>관련 관측 기출 {observed}건</h2>'
        f'<p>{rounds}개 회차 · {html.escape(evidence)} · {html.escape(importance)}</p></div>'
        f'<a href="{href}">이 항목의 기출·출제분석 보기</a>'
        '</aside>'
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
    # Provenance is written only by record_artifact.py or migrate_meta_v2.py.
    # Never infer a producer from progress flags or replace an existing record.
    if meta:
        meta_version = meta.get("version", 1)
        artifacts = meta.get("artifacts")
    else:
        meta_version = 2
        artifacts = {"ff": None, "cc": None}
    meta.update({
        "version": meta_version,
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
        "published_at": meta.get("published_at") or (timestamp if state.get("status") == "published" else None),
        "status": state["status"],
    })
    if meta_version == 2:
        meta["artifacts"] = artifacts if isinstance(artifacts, dict) else {"ff": None, "cc": None}
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
        "QUESTION_BANK_SUMMARY": question_bank_summary(course_id, lesson_id),
        "PREVIOUS_LINK": nav_link("이전 Lesson", previous, course_id, "previous"),
        "NEXT_LINK": nav_link("다음 Lesson", following, course_id, "next"),
    })
    output = folder / "index.html"
    output.write_text(shell, encoding="utf-8", newline="\n")

    cc_view = render_template("cc-view.html", {
        "PAGE_TITLE": html.escape(f"{lesson_id}. {lesson['title']} · {curriculum['title']}"),
        "COURSE_URL": f"/study/courses/{course_id}/",
        "LESSON_URL": lesson_url(course_id, lesson),
        "LESSON_ID": html.escape(lesson_id),
        "LESSON_TITLE": html.escape(lesson["title"]),
        "PREVIOUS_CC_LINK": cc_nav_link(
            "←", previous, course_id, "previous", "이전 장"
        ),
        "NEXT_CC_LINK": cc_nav_link(
            "→", following, course_id, "next", "다음 장"
        ),
        "FLOATING_NEXT_CC_LINK": cc_nav_link(
            "→", following, course_id, "next cc-page-next", "다음 장"
        ),
    })
    (folder / "cc-view.html").write_text(cc_view, encoding="utf-8", newline="\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    args = parser.parse_args()
    print(build_lesson(args.course_id, args.lesson_id))


if __name__ == "__main__":
    main()
