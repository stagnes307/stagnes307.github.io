#!/usr/bin/env python3
"""Safely render a public-Ailey FF Markdown artifact as static CC HTML."""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import tempfile
from pathlib import Path

from ailey_public_profile import (
    AILEY_CC_PROFILE,
    ailey_public_ff_quality_errors,
    public_profile_fingerprint,
    raw_upstream_cc_errors,
)
from common import (
    COURSES_DIR,
    FACTORY_ROOT,
    find_lesson,
    lesson_dir,
    load_curriculum,
)
from prompt_profiles import get_prompt_profile
from render_codex_cc import (
    MarkdownRenderer,
    escape_visible_text,
    render_inline,
    section_class,
)


def render_ailey_template(values: dict[str, str]) -> str:
    template_name = "ailey-public-cc.html"
    template = (FACTORY_ROOT / "templates" / template_name).read_text(
        encoding="utf-8"
    )
    placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
    unknown = placeholders - values.keys()
    missing = values.keys() - placeholders
    if unknown or missing:
        raise ValueError(
            f"{template_name} placeholder mismatch: "
            f"unknown={sorted(unknown)} missing={sorted(missing)}"
        )
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def selected_lesson_sources(
    curriculum: dict,
    lesson: dict,
) -> list[dict]:
    """Resolve the lesson's exact source_refs against its curriculum."""
    source_by_id = {
        source.get("id"): source
        for source in curriculum.get("sources", [])
        if isinstance(source, dict)
    }
    source_refs = lesson.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        raise ValueError(
            f"lesson {lesson['id']} must select at least one official source"
        )
    selected: list[dict] = []
    seen: set[str] = set()
    for source_id in source_refs:
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(
                f"lesson {lesson['id']} has an invalid source_ref"
            )
        if source_id in seen:
            raise ValueError(
                f"lesson {lesson['id']} repeats source_ref {source_id!r}"
            )
        seen.add(source_id)
        source = source_by_id.get(source_id)
        if source is None:
            raise ValueError(
                f"lesson {lesson['id']} references unknown source {source_id!r}"
            )
        for field in ("title", "authority", "url", "retrieved_at"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"source {source_id!r} requires a non-empty {field}"
                )
        selected.append(source)
    return selected


def render_official_sources(sources: list[dict]) -> str:
    """Render visible, inert source metadata with explicit navigation links."""
    items: list[str] = []
    for source in sources:
        effective_from = source.get("effective_from")
        effective_to = source.get("effective_to")
        if effective_from and effective_to:
            effective = f"{effective_from} ~ {effective_to}"
        elif effective_from:
            effective = f"{effective_from}부터"
        elif effective_to:
            effective = f"{effective_to}까지"
        else:
            effective = "별도 명시 없음"
        url = source["url"]
        items.append(
            "<li><article class=\"official-source-item\">"
            f"<h3>{escape_visible_text(source['title'])}</h3>"
            '<dl class="source-metadata">'
            "<div><dt>발행·관리 기관</dt>"
            f"<dd>{escape_visible_text(source['authority'])}</dd></div>"
            "<div><dt>확인일</dt>"
            f"<dd>{escape_visible_text(source['retrieved_at'])}</dd></div>"
            "<div><dt>적용 기간</dt>"
            f"<dd>{escape_visible_text(effective)}</dd></div>"
            "</dl>"
            f'<a class="official-source-link" href="{html.escape(url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">'
            "<span>공식 URL</span>"
            f"<code>{escape_visible_text(url)}</code>"
            "</a>"
            "</article></li>"
        )
    return "".join(items)


def render_cc_document(
    course_id: str,
    curriculum: dict,
    lesson: dict,
    ff_source: str,
) -> str:
    """Validate a literal-profile FF and convert it to deterministic safe HTML."""
    ff_errors = ailey_public_ff_quality_errors(
        ff_source,
        lesson["topics"],
        lesson_id=lesson["id"],
        lesson_title=lesson["title"],
    )
    if ff_errors:
        raise ValueError(
            "FF failed public Ailey quality gates: " + "; ".join(ff_errors)
        )

    markdown_renderer = MarkdownRenderer()
    intro_blocks, sections = markdown_renderer.render(ff_source)
    if len(sections) != 5:
        raise ValueError(
            f"safe renderer requires exactly five FF sections, found {len(sections)}"
        )
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
            f'<section class="lesson-card{section_class(section.title)}" '
            f'id="{section_id}">'
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
        f"ailey-public-{course_id}-{lesson['id']}".lower(),
    ).strip("-")
    official_sources = selected_lesson_sources(curriculum, lesson)
    allowed_urls = [source["url"] for source in official_sources]
    values = {
        "CANVAS_ID": html.escape(
            f"{canvas_base}-{ff_digest}",
            quote=True,
        ),
        "PAGE_TITLE": escape_visible_text(
            f"{lesson['id']}. {lesson['title']} · {curriculum['title']}"
        ),
        "COURSE_TITLE": escape_visible_text(curriculum["title"]),
        "SECTION_LABEL": escape_visible_text(
            f"{lesson['section_id']}. {lesson['section_title']}"
        ),
        "GROUP_LABEL": escape_visible_text(
            f"{lesson['lesson_group_id']}. "
            f"{lesson['lesson_group_title']}"
        ),
        "LESSON_ID": escape_visible_text(lesson["id"]),
        "LESSON_TITLE": escape_visible_text(lesson["title"]),
        "PROFILE_FINGERPRINT": public_profile_fingerprint(),
        "TOPICS": "".join(
            f"<li>{escape_visible_text(topic)}</li>"
            for topic in lesson["topics"]
        ),
        "OFFICIAL_SOURCES": render_official_sources(official_sources),
        "TOC": "".join(toc_html),
        "INTRO": intro,
        "SECTIONS": "".join(section_html),
    }
    document = render_ailey_template(values)
    cc_errors = raw_upstream_cc_errors(
        document,
        lesson["topics"],
        allowed_urls=allowed_urls,
    )
    if cc_errors:
        raise ValueError(
            "rendered CC failed public Ailey safety gates: "
            + "; ".join(cc_errors)
        )
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


def _load_lesson(
    course_id: str,
    lesson_id: str,
) -> tuple[dict, dict]:
    get_prompt_profile(
        AILEY_CC_PROFILE,
        artifact_kind="cc",
        producer="openai-codex",
    )
    curriculum = load_curriculum(course_id)
    return curriculum, find_lesson(curriculum, lesson_id)


def render_file(
    ff_path: Path,
    output_path: Path,
    *,
    course_id: str,
    lesson_id: str,
    force: bool = False,
) -> Path:
    """Render an explicitly named FF path to an explicitly named output path."""
    if ff_path.resolve() == output_path.resolve():
        raise ValueError("--ff and --out must identify different files")
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists; pass --force to replace it"
        )
    if not ff_path.is_file():
        raise FileNotFoundError(f"FF source does not exist: {ff_path}")
    curriculum, lesson = _load_lesson(course_id, lesson_id)
    ff_source = ff_path.read_text(encoding="utf-8")
    document = render_cc_document(
        course_id,
        curriculum,
        lesson,
        ff_source,
    )
    _write_output(output_path, document, force)
    return output_path


def generate_cc(
    course_id: str,
    lesson_id: str,
    force: bool = False,
) -> Path:
    """Generate the lesson's cc.html with the bulk-generator-compatible API."""
    curriculum, lesson = _load_lesson(course_id, lesson_id)
    folder = lesson_dir(course_id, lesson)
    ff_path = folder / "ff.md"
    cc_path = folder / "cc.html"
    if cc_path.exists() and not force:
        raise FileExistsError(f"{cc_path} already exists; pass --force to replace it")
    if not ff_path.is_file():
        raise FileNotFoundError(f"FF source does not exist: {ff_path}")
    ff_source = ff_path.read_text(encoding="utf-8")
    document = render_cc_document(
        course_id,
        curriculum,
        lesson,
        ff_source,
    )
    _write_output(cc_path, document, force)
    return cc_path


def _coalesce_identifier(
    parser: argparse.ArgumentParser,
    positional: str | None,
    named: str | None,
    label: str,
) -> str | None:
    if positional and named and positional != named:
        parser.error(f"positional {label} and --{label.replace('_', '-')} disagree")
    return named or positional


def _infer_standard_identifiers(ff_path: Path) -> tuple[str, str] | None:
    try:
        relative = ff_path.resolve().relative_to(COURSES_DIR.resolve())
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) != 4 or parts[1] != "lessons" or parts[3] != "ff.md":
        return None
    match = re.match(r"^(\d+-\d+-\d+-\d+)-", parts[2])
    if match is None:
        return None
    return parts[0], match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render public-Ailey FF Markdown through the inert Study Factory "
            "CC template. Raw upstream .cc/.ccc output is never accepted."
        )
    )
    parser.add_argument("course_id_positional", nargs="?")
    parser.add_argument("lesson_id_positional", nargs="?")
    parser.add_argument("--course-id")
    parser.add_argument("--lesson-id")
    parser.add_argument("--ff", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    course_id = _coalesce_identifier(
        parser,
        args.course_id_positional,
        args.course_id,
        "course_id",
    )
    lesson_id = _coalesce_identifier(
        parser,
        args.lesson_id_positional,
        args.lesson_id,
        "lesson_id",
    )
    if (args.ff is None) != (args.out is None):
        parser.error("--ff and --out must be used together")
    if args.ff is not None:
        inferred = _infer_standard_identifiers(args.ff)
        if course_id is None and inferred is not None:
            course_id = inferred[0]
        if lesson_id is None and inferred is not None:
            lesson_id = inferred[1]
        if course_id is None or lesson_id is None:
            parser.error(
                "--ff/--out outside the standard course tree also require "
                "--course-id and --lesson-id"
            )
    elif course_id is None or lesson_id is None:
        parser.error("course and lesson are required")

    try:
        if args.ff is not None:
            output = render_file(
                args.ff,
                args.out,
                course_id=course_id,
                lesson_id=lesson_id,
                force=args.force,
            )
        else:
            output = generate_cc(course_id, lesson_id, args.force)
    except (
        FileExistsError,
        FileNotFoundError,
        KeyError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        raise SystemExit(str(exc)) from exc
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
