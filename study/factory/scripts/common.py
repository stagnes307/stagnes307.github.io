"""Shared filesystem and curriculum helpers for Study Factory scripts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


STUDY_ROOT = Path(__file__).resolve().parents[2]
FACTORY_ROOT = STUDY_ROOT / "factory"
CURRICULA_DIR = STUDY_ROOT / "curricula"
COURSES_DIR = STUDY_ROOT / "courses"
CATALOG_PATH = STUDY_ROOT / "catalog.json"
STATUSES = {
    "pending",
    "ff-running",
    "ff-complete",
    "cc-running",
    "cc-complete",
    "publishing",
    "published",
    "failed",
}
ARTIFACT_FILENAMES = {"ff": "ff.md", "cc": "cc.html"}
ACTIVE_PRODUCERS = {"ailey-bailey-custom-gpt", "openai-codex"}
PROVENANCE_PRODUCERS = ACTIVE_PRODUCERS


def now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def today_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def sha256_file(path: Path) -> str:
    """Return a stable lowercase SHA-256 digest for an artifact file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record_errors(record: Any, path: Path) -> list[str]:
    """Validate one meta v2 provenance record against its on-disk artifact."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["provenance record is missing"]
    producer = record.get("producer")
    if producer not in PROVENANCE_PRODUCERS:
        errors.append(f"invalid producer {producer!r}")
    prompt_profile = record.get("prompt_profile")
    if not isinstance(prompt_profile, str) or not prompt_profile.strip():
        errors.append("prompt_profile must be a non-empty string")
    generated_at = record.get("generated_at")
    if not isinstance(generated_at, str):
        errors.append("generated_at must be an ISO 8601 timestamp")
    else:
        try:
            parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                errors.append("generated_at must include a UTC offset")
        except ValueError:
            errors.append("generated_at must be an ISO 8601 timestamp")
    expected_hash = record.get("sha256")
    if (
        not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdef" for character in expected_hash)
    ):
        errors.append("sha256 must be a lowercase 64-character digest")
    if not path.exists():
        errors.append(f"artifact file is missing: {path.name}")
    elif isinstance(expected_hash, str) and expected_hash != sha256_file(path):
        errors.append(f"sha256 does not match {path.name}")
    return errors


def _markdown_fences_balanced(source: str) -> bool:
    active: tuple[str, int] | None = None
    for line in source.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if not match:
            continue
        marker = match.group(1)
        if active is None:
            active = (marker[0], len(marker))
        elif (
            marker[0] == active[0]
            and len(marker) >= active[1]
            and not match.group(2).strip()
        ):
            active = None
    return active is None


class _CodexCCParser(HTMLParser):
    """Collect structural, security, and accessibility facts from a CC file."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doctype_html = False
        self.html_lang_ko = False
        self.has_csp = False
        self.has_canvas_id = False
        self.has_content_root = False
        self.h1_count = 0
        self.forbidden_tags: set[str] = set()
        self.inline_events: list[str] = []
        self.javascript_urls: list[str] = []
        self.remote_urls: list[str] = []
        self.tables: list[dict[str, int]] = []
        self._table_stack: list[dict[str, int]] = []
        self.svg_errors = 0

    def handle_decl(self, declaration: str) -> None:
        if declaration.strip().lower() == "doctype html":
            self.doctype_html = True

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attributes = {
            name.lower(): value
            for name, value in attrs
        }
        if tag == "html" and (attributes.get("lang") or "").lower() == "ko":
            self.html_lang_ko = True
        if tag == "meta":
            name = (attributes.get("name") or "").lower()
            http_equiv = (attributes.get("http-equiv") or "").lower()
            content = (attributes.get("content") or "").strip()
            if http_equiv == "content-security-policy" and content:
                self.has_csp = True
            if name == "canvas-id" and content:
                self.has_canvas_id = True
        if attributes.get("id") == "ai-content-placeholder":
            self.has_content_root = True
        if tag == "h1":
            self.h1_count += 1
        if tag in {"script", "link", "iframe", "object", "embed"}:
            self.forbidden_tags.add(tag)
        for name, value in attributes.items():
            if name.startswith("on"):
                self.inline_events.append(name)
            if isinstance(value, str):
                normalized = value.lstrip().lower()
                if normalized.startswith("javascript:"):
                    self.javascript_urls.append(name)
                if normalized.startswith(("http://", "https://", "ftp://", "//")):
                    self.remote_urls.append(name)
        if tag == "table":
            table = {"captions": 0, "missing_scope": 0}
            self.tables.append(table)
            self._table_stack.append(table)
        elif tag == "caption" and self._table_stack:
            self._table_stack[-1]["captions"] += 1
        elif tag == "th" and self._table_stack:
            if (attributes.get("scope") or "").lower() not in {
                "col", "row", "colgroup", "rowgroup",
            }:
                self._table_stack[-1]["missing_scope"] += 1
        elif tag == "svg":
            decorative = (attributes.get("aria-hidden") or "").lower() == "true"
            informative = bool(
                (attributes.get("role") or "").strip()
                and (attributes.get("aria-label") or "").strip()
            )
            if not decorative and not informative:
                self.svg_errors += 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "table" and self._table_stack:
            self._table_stack.pop()


def codex_artifact_quality_errors(
    kind: str,
    source: str,
    topics: list[str],
) -> list[str]:
    """Apply detailed content gates only to artifacts produced by OpenAI Codex."""
    errors: list[str] = []
    missing_topics = [topic for topic in topics if topic not in source]
    if kind == "ff":
        if len(source) < 4_000:
            errors.append("must contain at least 4,000 characters including whitespace")
        if missing_topics:
            errors.append(f"must include every curriculum topic exactly: {missing_topics}")
        if not _markdown_fences_balanced(source):
            errors.append("contains an unbalanced Markdown fence")
        if "확인 문제" not in source:
            errors.append("must include 확인 문제")
        if "정답" not in source and "해설" not in source:
            errors.append("must include 정답 or 해설")
        if "요약" not in source:
            errors.append("must include a 요약")
        return errors

    if kind != "cc":
        return [f"unknown artifact kind {kind!r}"]
    if len(source.encode("utf-8")) < 8 * 1024:
        errors.append("must contain at least 8 KiB of UTF-8 HTML")
    if missing_topics:
        errors.append(f"must include every curriculum topic exactly: {missing_topics}")
    if re.search(r"(?:https?|ftp)://|(?<!:)//[A-Za-z0-9.-]+\.[A-Za-z]{2,}", source, re.IGNORECASE):
        errors.append("contains a remote URL")
    if re.search(r"@import\b", source, re.IGNORECASE):
        errors.append("contains a CSS @import")
    if re.search(r"javascript\s*:", source, re.IGNORECASE):
        errors.append("contains a javascript: URL")

    parser = _CodexCCParser()
    parser.feed(source)
    parser.close()
    if not parser.doctype_html:
        errors.append("must declare <!doctype html>")
    if not parser.html_lang_ko:
        errors.append("must set html lang=\"ko\"")
    if not parser.has_csp:
        errors.append("must include a Content-Security-Policy meta tag")
    if not parser.has_canvas_id:
        errors.append("must include a non-empty canvas-id meta tag")
    if not parser.has_content_root:
        errors.append("must include id=\"ai-content-placeholder\"")
    if parser.h1_count != 1:
        errors.append(f"must contain exactly one h1 (found {parser.h1_count})")
    if parser.forbidden_tags:
        errors.append(f"contains forbidden tags: {sorted(parser.forbidden_tags)}")
    if parser.inline_events:
        errors.append(f"contains inline event attributes: {sorted(set(parser.inline_events))}")
    if parser.javascript_urls:
        errors.append("contains a javascript: attribute URL")
    if parser.remote_urls and not any("remote URL" in error for error in errors):
        errors.append("contains a remote attribute URL")
    for index, table in enumerate(parser.tables, start=1):
        if table["captions"] < 1:
            errors.append(f"table {index} is missing caption")
        if table["missing_scope"]:
            errors.append(
                f"table {index} has {table['missing_scope']} th element(s) without valid scope"
            )
    if parser.svg_errors:
        errors.append(
            f"{parser.svg_errors} SVG element(s) lack role+aria-label or aria-hidden"
        )
    return errors


def curriculum_path(course_id: str) -> Path:
    return CURRICULA_DIR / f"{course_id}.json"


def coverage_path(course_id: str) -> Path:
    return CURRICULA_DIR / "coverage" / f"{course_id}.json"


def course_dir(course_id: str) -> Path:
    return COURSES_DIR / course_id


def progress_path(course_id: str) -> Path:
    return course_dir(course_id) / "progress.json"


def lesson_url(course_id: str, lesson: dict[str, Any]) -> str:
    return f"/study/courses/{course_id}/lessons/{lesson['id']}-{lesson['slug']}/"


def lesson_dir(course_id: str, lesson: dict[str, Any]) -> Path:
    return course_dir(course_id) / "lessons" / f"{lesson['id']}-{lesson['slug']}"


def iter_lessons(curriculum: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield flattened, contextualized four-part learning lessons in display order."""
    for section in curriculum.get("sections", []):
        for unit in section.get("units", []):
            for group in unit.get("lessons", []):
                for lesson in group.get("sublessons", []):
                    yield {
                        **lesson,
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "unit_id": unit["id"],
                        "unit_title": unit["title"],
                        "lesson_group_id": group["id"],
                        "lesson_group_title": group["title"],
                    }


def lesson_list(curriculum: dict[str, Any]) -> list[dict[str, Any]]:
    return list(iter_lessons(curriculum))


def find_lesson(curriculum: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    for lesson in iter_lessons(curriculum):
        if lesson["id"] == lesson_id:
            return lesson
    raise KeyError(f"unknown lesson id: {lesson_id}")


def new_progress(curriculum: dict[str, Any]) -> dict[str, Any]:
    course_id = curriculum["course_id"]
    return {
        "version": 1,
        "course_id": course_id,
        "updated": now_kst(),
        "lessons": {
            lesson["id"]: {
                "status": "pending",
                "ff": False,
                "cc": False,
                "url": None,
                "last_error": None,
            }
            for lesson in iter_lessons(curriculum)
        },
    }


def load_curriculum(course_id: str) -> dict[str, Any]:
    return load_json(curriculum_path(course_id))


def load_or_create_progress(course_id: str) -> dict[str, Any]:
    path = progress_path(course_id)
    curriculum = load_curriculum(course_id)
    if not path.exists():
        progress = new_progress(curriculum)
        write_json(path, progress)
        return progress

    progress = load_json(path)
    changed = False
    for lesson in iter_lessons(curriculum):
        if lesson["id"] not in progress.setdefault("lessons", {}):
            progress["lessons"][lesson["id"]] = {
                "status": "pending",
                "ff": False,
                "cc": False,
                "url": None,
                "last_error": None,
            }
            changed = True
    if changed:
        progress["updated"] = now_kst()
        write_json(path, progress)
    return progress


def render_template(name: str, values: dict[str, str]) -> str:
    text = (FACTORY_ROOT / "templates" / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = [part.split("}}", 1)[0] for part in text.split("{{")[1:] if "}}" in part]
    if unresolved:
        raise ValueError(f"unresolved template values in {name}: {', '.join(unresolved)}")
    return text
