#!/usr/bin/env python3
"""Render a human-reviewable Markdown outline from one curriculum JSON."""

from __future__ import annotations

import argparse

from common import CURRICULA_DIR, load_curriculum


def nullable(value: object) -> str:
    return "확인 불가" if value is None else str(value)


def render(course_id: str) -> str:
    curriculum = load_curriculum(course_id)
    lines = [
        f"# {curriculum['title']}", "",
        f"- 시행기관: {curriculum['authority']}",
        f"- 확인일: {curriculum['verified_at']}",
        f"- 과정 유형: {curriculum['mode']}", "",
        "## 공식 출처", "",
    ]
    for source in curriculum["sources"]:
        lines.extend([
            f"- [{source['title']}]({source['url']})",
            f"  - 기관: {source['authority']}",
            f"  - 적용기간: {nullable(source['effective_from'])} ~ {nullable(source['effective_to'])}",
            f"  - 확인일: {source['retrieved_at']}",
        ])
    lines.extend(["", "## Curriculum", ""])
    for section in curriculum["sections"]:
        lines.extend([f"## {section['id']}. {section['title']}", ""])
        for unit in section["units"]:
            lines.extend([f"### {unit['id']}. {unit['title']}", ""])
            for group in unit["lessons"]:
                lines.append(f"- **{group['id']}. {group['title']}**")
                for lesson in group["sublessons"]:
                    suffix = " _(supplemental)_" if lesson.get("supplemental") else ""
                    lines.append(f"  - {lesson['id']}. {lesson['title']}{suffix}")
                    for topic in lesson["topics"]:
                        lines.append(f"    - {topic}")
                    lines.append(f"    - 공식 근거: {'; '.join(lesson.get('official_basis', []))}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    args = parser.parse_args()
    output = CURRICULA_DIR / f"{args.course_id}.md"
    output.write_text(render(args.course_id), encoding="utf-8", newline="\n")
    print(output)


if __name__ == "__main__":
    main()
