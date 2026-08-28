#!/usr/bin/env python3
"""Render a complete, static, safe CC document from a lesson's FF Markdown."""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from common import (
    FACTORY_ROOT,
    codex_artifact_quality_errors,
    find_lesson,
    lesson_dir,
    load_curriculum,
)


FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
H2_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
LIST_RE = re.compile(r"^(\s*)([-+*]|\d+[.)])\s+(.+?)\s*$")
DETAILS_OPEN_RE = re.compile(r"^\s*<details\b[^>]*>\s*$", re.IGNORECASE)
DETAILS_CLOSE_RE = re.compile(r"^\s*</details>\s*$", re.IGNORECASE)
SUMMARY_RE = re.compile(
    r"^\s*<summary\b[^>]*>(.*?)</summary>\s*$",
    re.IGNORECASE,
)
TABLE_DIVIDER_CELL_RE = re.compile(r"^:?-{3,}:?$")
DANGEROUS_VISIBLE_RE = re.compile(
    r"(?:https?|ftp)://[^\s<>\"']+"
    r"|(?<!:)//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s<>\"']*"
    r"|javascript\s*:"
    r"|@import\b",
    re.IGNORECASE,
)


@dataclass
class Section:
    title: str
    blocks: list[str]


def numeric_entities(value: str) -> str:
    """Show sensitive literal text without leaving an executable token in HTML."""
    return "".join(f"&#{ord(character)};" for character in value)


def escape_visible_text(value: str) -> str:
    """Escape markup and entity-encode URL/script-like text while preserving display."""
    parts: list[str] = []
    position = 0
    for match in DANGEROUS_VISIBLE_RE.finditer(value):
        parts.append(html.escape(value[position:match.start()], quote=True))
        parts.append(numeric_entities(match.group(0)))
        position = match.end()
    parts.append(html.escape(value[position:], quote=True))
    return "".join(parts)


def _find_closing(value: str, token: str, start: int) -> int:
    position = value.find(token, start)
    while position >= 0 and position > 0 and value[position - 1] == "\\":
        position = value.find(token, position + len(token))
    return position


def render_inline(value: str) -> str:
    """Render a deliberately small inline Markdown subset without active links."""
    result: list[str] = []
    plain: list[str] = []

    def flush() -> None:
        if plain:
            result.append(escape_visible_text("".join(plain)))
            plain.clear()

    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            plain.append(value[index + 1])
            index += 2
            continue

        if value[index] == "`":
            run = 1
            while index + run < len(value) and value[index + run] == "`":
                run += 1
            token = "`" * run
            closing = _find_closing(value, token, index + run)
            if closing >= 0:
                flush()
                code = value[index + run:closing].strip(" ")
                result.append(f"<code>{escape_visible_text(code)}</code>")
                index = closing + run
                continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]*)\)", value[index:])
        if image_match:
            flush()
            alt, target = image_match.groups()
            result.append(
                '<span class="blocked-image">'
                f"<span>이미지 설명: {render_inline(alt)}</span>"
                f'<span class="literal-address">원문 주소: {numeric_entities(target)}</span>'
                "</span>"
            )
            index += image_match.end()
            continue

        link_match = re.match(r"\[([^\]]+)\]\(([^)]*)\)", value[index:])
        if link_match:
            flush()
            label, target = link_match.groups()
            result.append(
                '<span class="nonactive-reference">'
                f"<span>{render_inline(label)}</span>"
                f'<span class="literal-address">원문 주소: {numeric_entities(target)}</span>'
                "</span>"
            )
            index += link_match.end()
            continue

        matched_emphasis = False
        for token, tag in (("**", "strong"), ("__", "strong"), ("*", "em"), ("_", "em")):
            if value.startswith(token, index):
                closing = _find_closing(value, token, index + len(token))
                if closing > index + len(token):
                    flush()
                    inner = value[index + len(token):closing]
                    result.append(f"<{tag}>{render_inline(inner)}</{tag}>")
                    index = closing + len(token)
                    matched_emphasis = True
                    break
        if matched_emphasis:
            continue

        plain.append(value[index])
        index += 1

    flush()
    return "".join(result)


def split_pipe_row(line: str) -> list[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|") and not value.endswith("\\|"):
        value = value[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    code_delimiter = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "`":
            code_delimiter = not code_delimiter
            current.append(character)
        elif character == "|" and not code_delimiter:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    divider = split_pipe_row(lines[index + 1])
    return bool(divider) and all(
        TABLE_DIVIDER_CELL_RE.fullmatch(cell.strip())
        for cell in divider
    )


def table_alignment(cell: str) -> str:
    value = cell.strip()
    if value.startswith(":") and value.endswith(":"):
        return "align-center"
    if value.endswith(":"):
        return "align-right"
    return ""


class MarkdownRenderer:
    """Convert FF Markdown blocks to semantic, inert HTML in original order."""

    def __init__(self) -> None:
        self.table_count = 0

    def render(self, source: str) -> tuple[list[str], list[Section]]:
        lines = source.splitlines()
        intro: list[str] = []
        sections: list[Section] = []
        current: Section | None = None
        index = 0
        while index < len(lines):
            h2_match = H2_RE.match(lines[index])
            if h2_match:
                current = Section(h2_match.group(1), [])
                sections.append(current)
                index += 1
                continue
            block, index = self._render_block(
                lines,
                index,
                current.title if current else "도입",
            )
            if block:
                (current.blocks if current else intro).append(block)
        if not sections:
            sections.append(Section("전체 학습 내용", intro))
            intro = []
        return intro, sections

    def _render_block(
        self,
        lines: list[str],
        index: int,
        context_title: str,
    ) -> tuple[str, int]:
        line = lines[index]
        if not line.strip():
            return "", index + 1

        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            info = fence_match.group(2).strip().split(maxsplit=1)
            language = re.sub(r"[^A-Za-z0-9_+.-]", "", info[0]) if info else "text"
            code_lines: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                closing = FENCE_RE.match(lines[cursor])
                if (
                    closing
                    and closing.group(1)[0] == marker[0]
                    and len(closing.group(1)) >= len(marker)
                    and not closing.group(2).strip()
                ):
                    code = "\n".join(code_lines)
                    label = escape_visible_text(language or "text")
                    return (
                        '<div class="code-block">'
                        f'<p class="code-label">코드 예시 · {label}</p>'
                        f'<pre><code class="language-{label}">{escape_visible_text(code)}</code></pre>'
                        "</div>",
                        cursor + 1,
                    )
                code_lines.append(lines[cursor])
                cursor += 1
            raise ValueError(f"unclosed code fence at FF line {index + 1}")

        if is_table_start(lines, index):
            return self._render_table(lines, index, context_title)

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level, title = len(heading_match.group(1)), heading_match.group(2)
            if level == 1:
                return (
                    '<p class="source-heading"><small>FF 원문 제목</small>'
                    f"<span>{render_inline(title)}</span></p>",
                    index + 1,
                )
            return f"<h3>{render_inline(title)}</h3>", index + 1

        if DETAILS_OPEN_RE.match(line):
            details = self._render_details(lines, index, context_title)
            if details is not None:
                return details

        if re.match(r"^\s*>\s?", line):
            quoted: list[str] = []
            cursor = index
            while cursor < len(lines):
                match = re.match(r"^\s*>\s?(.*)$", lines[cursor])
                if not match:
                    break
                quoted.append(match.group(1))
                cursor += 1
            body = "<br>".join(render_inline(item) for item in quoted)
            return f"<blockquote><p>{body}</p></blockquote>", cursor

        if LIST_RE.match(line):
            return self._render_list(lines, index)

        if re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", line):
            return "<hr>", index + 1

        paragraph: list[str] = [line.strip()]
        cursor = index + 1
        while cursor < len(lines) and not self._starts_new_block(lines, cursor):
            paragraph.append(lines[cursor].strip())
            cursor += 1
        return f"<p>{render_inline(' '.join(paragraph))}</p>", cursor

    def _starts_new_block(self, lines: list[str], index: int) -> bool:
        line = lines[index]
        return bool(
            not line.strip()
            or FENCE_RE.match(line)
            or HEADING_RE.match(line)
            or DETAILS_OPEN_RE.match(line)
            or re.match(r"^\s*>\s?", line)
            or LIST_RE.match(line)
            or re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", line)
            or is_table_start(lines, index)
        )

    def _render_list(self, lines: list[str], index: int) -> tuple[str, int]:
        items: list[tuple[bool, int, int | None, str]] = []
        cursor = index
        while cursor < len(lines):
            match = LIST_RE.match(lines[cursor])
            if match:
                whitespace, marker, text = match.groups()
                ordered = marker[0].isdigit()
                number_match = re.match(r"\d+", marker)
                number = int(number_match.group(0)) if number_match else None
                depth = min(8, len(whitespace.expandtabs(4)) // 2)
                items.append((ordered, depth, number, text))
                cursor += 1
                continue
            if (
                items
                and lines[cursor].strip()
                and len(lines[cursor]) - len(lines[cursor].lstrip()) >= 2
                and not self._starts_new_block(lines, cursor)
            ):
                ordered, depth, number, text = items[-1]
                items[-1] = (
                    ordered,
                    depth,
                    number,
                    text + "\n" + lines[cursor].strip(),
                )
                cursor += 1
                continue
            break

        output: list[str] = []
        group_type: bool | None = None
        for ordered, depth, number, text in items:
            if group_type is None or ordered != group_type:
                if group_type is not None:
                    output.append("</ol>" if group_type else "</ul>")
                tag = "ol" if ordered else "ul"
                start = f' start="{number}"' if ordered and number not in {None, 1} else ""
                output.append(f'<{tag} class="markdown-list"{start}>')
                group_type = ordered
            value = f' value="{number}"' if ordered and number is not None else ""
            body = "<br>".join(render_inline(part) for part in text.splitlines())
            output.append(
                f'<li style="--depth:{depth}"{value}>{body}</li>'
            )
        if group_type is not None:
            output.append("</ol>" if group_type else "</ul>")
        return "".join(output), cursor

    def _render_table(
        self,
        lines: list[str],
        index: int,
        context_title: str,
    ) -> tuple[str, int]:
        headers = split_pipe_row(lines[index])
        dividers = split_pipe_row(lines[index + 1])
        alignments = [
            table_alignment(dividers[column]) if column < len(dividers) else ""
            for column in range(len(headers))
        ]
        rows: list[list[str]] = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].strip() and "|" in lines[cursor]:
            row = split_pipe_row(lines[cursor])
            row.extend([""] * (len(headers) - len(row)))
            rows.append(row[:len(headers)])
            cursor += 1
        self.table_count += 1
        caption = f"{context_title} · 학습 표 {self.table_count}"
        output = [
            '<div class="table-wrap"><table>',
            f"<caption>{render_inline(caption)}</caption>",
            "<thead><tr>",
        ]
        for column, header in enumerate(headers):
            css = f' class="{alignments[column]}"' if alignments[column] else ""
            output.append(
                f'<th scope="col"{css}>{render_inline(header)}</th>'
            )
        output.append("</tr></thead><tbody>")
        for row in rows:
            output.append("<tr>")
            for column, cell in enumerate(row):
                css = f' class="{alignments[column]}"' if alignments[column] else ""
                if column == 0:
                    output.append(
                        f'<th scope="row"{css}>{render_inline(cell)}</th>'
                    )
                else:
                    output.append(f"<td{css}>{render_inline(cell)}</td>")
            output.append("</tr>")
        output.append("</tbody></table></div>")
        return "".join(output), cursor

    def _render_details(
        self,
        lines: list[str],
        index: int,
        context_title: str,
    ) -> tuple[str, int] | None:
        depth = 1
        cursor = index + 1
        inner: list[str] = []
        while cursor < len(lines):
            if DETAILS_OPEN_RE.match(lines[cursor]):
                depth += 1
            elif DETAILS_CLOSE_RE.match(lines[cursor]):
                depth -= 1
                if depth == 0:
                    break
            inner.append(lines[cursor])
            cursor += 1
        if depth:
            return None

        summary = "내용 펼쳐보기"
        content_lines: list[str] = []
        summary_found = False
        for inner_line in inner:
            match = SUMMARY_RE.match(inner_line)
            if match and not summary_found:
                summary = match.group(1)
                summary_found = True
            else:
                content_lines.append(inner_line)
        body = self._render_fragment(content_lines, context_title)
        return (
            '<details class="reveal">'
            f"<summary>{render_inline(summary)}</summary>"
            f'<div class="reveal-content">{body}</div>'
            "</details>",
            cursor + 1,
        )

    def _render_fragment(self, lines: list[str], context_title: str) -> str:
        output: list[str] = []
        index = 0
        while index < len(lines):
            block, index = self._render_block(lines, index, context_title)
            if block:
                output.append(block)
        return "".join(output)


def section_class(title: str) -> str:
    if "확인 문제" in title or "확인문제" in title or "문제" in title:
        return " is-check"
    if "요약" in title or "정리" in title:
        return " is-summary"
    return ""


def render_codex_template(values: dict[str, str]) -> str:
    template = (FACTORY_ROOT / "templates" / "codex-cc.html").read_text(
        encoding="utf-8"
    )
    placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
    unknown = placeholders - values.keys()
    missing = values.keys() - placeholders
    if unknown or missing:
        raise ValueError(
            "codex-cc.html placeholder mismatch: "
            f"unknown={sorted(unknown)} missing={sorted(missing)}"
        )
    for key, value in values.items():
        marker = "{{" + key + "}}"
        template = template.replace(marker, value)
    return template


def render_cc_document(
    course_id: str,
    curriculum: dict,
    lesson: dict,
    ff_source: str,
) -> str:
    renderer = MarkdownRenderer()
    intro_blocks, sections = renderer.render(ff_source)
    intro = (
        '<section class="intro-card" aria-label="FF 도입">'
        + "".join(intro_blocks)
        + "</section>"
        if intro_blocks
        else ""
    )
    section_html: list[str] = []
    toc_html: list[str] = []
    for index, section in enumerate(sections, start=1):
        section_id = f"ff-section-{index}"
        toc_html.append(
            f'<li><a href="#{section_id}"><b>{index:02d}</b>'
            f"<span>{render_inline(section.title)}</span></a></li>"
        )
        section_html.append(
            f'<section class="lesson-card{section_class(section.title)}" id="{section_id}">'
            "<header>"
            f'<span class="section-number" aria-hidden="true">{index:02d}</span>'
            f"<h2>{render_inline(section.title)}</h2>"
            "</header>"
            f'<div class="card-body">{"".join(section.blocks)}</div>'
            "</section>"
        )

    ff_digest = hashlib.sha256(ff_source.encode("utf-8")).hexdigest()[:12]
    canvas_base = re.sub(
        r"[^a-z0-9-]+",
        "-",
        f"codex-{course_id}-{lesson['id']}".lower(),
    ).strip("-")
    canvas_id = f"{canvas_base}-{ff_digest}"
    topics = "".join(
        f"<li>{escape_visible_text(topic)}</li>"
        for topic in lesson["topics"]
    )
    document = render_codex_template({
        "CANVAS_ID": html.escape(canvas_id, quote=True),
        "PAGE_TITLE": escape_visible_text(
            f"{lesson['id']}. {lesson['title']} · {curriculum['title']}"
        ),
        "COURSE_TITLE": escape_visible_text(curriculum["title"]),
        "SECTION_LABEL": escape_visible_text(
            f"{lesson['section_id']}. {lesson['section_title']}"
        ),
        "GROUP_LABEL": escape_visible_text(
            f"{lesson['lesson_group_id']}. {lesson['lesson_group_title']}"
        ),
        "LESSON_ID": escape_visible_text(lesson["id"]),
        "LESSON_TITLE": escape_visible_text(lesson["title"]),
        "TOPICS": topics,
        "TOC": "".join(toc_html),
        "INTRO": intro,
        "SECTIONS": "".join(section_html),
    })
    errors = codex_artifact_quality_errors("cc", document, lesson["topics"])
    if errors:
        raise ValueError("rendered CC failed quality gates: " + "; ".join(errors))
    return document


def _write_output(path: Path, source: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(source)
        return
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(source)
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


def generate_cc(course_id: str, lesson_id: str, force: bool = False) -> Path:
    curriculum = load_curriculum(course_id)
    lesson = find_lesson(curriculum, lesson_id)
    folder = lesson_dir(course_id, lesson)
    ff_path = folder / "ff.md"
    cc_path = folder / "cc.html"
    if cc_path.exists() and not force:
        raise FileExistsError(f"{cc_path} already exists; pass --force to replace it")
    if not ff_path.exists():
        raise FileNotFoundError(f"FF source does not exist: {ff_path}")
    ff_source = ff_path.read_text(encoding="utf-8")
    ff_errors = codex_artifact_quality_errors("ff", ff_source, lesson["topics"])
    if ff_errors:
        raise ValueError("FF failed Codex quality gates: " + "; ".join(ff_errors))
    document = render_cc_document(course_id, curriculum, lesson, ff_source)
    _write_output(cc_path, document, force)
    return cc_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render an inert, standalone CC document from a lesson FF."
    )
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        output = generate_cc(args.course_id, args.lesson_id, args.force)
    except (FileExistsError, FileNotFoundError, KeyError, UnicodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
