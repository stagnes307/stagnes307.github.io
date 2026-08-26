"""Validation gates for catalogs, curricula, progress, and lesson artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import (
    CATALOG_PATH,
    STATUSES,
    coverage_path,
    curriculum_path,
    find_lesson,
    iter_lessons,
    lesson_dir,
    lesson_url,
    load_json,
    progress_path,
)


SECTION_ID = re.compile(r"^[1-9]\d*$")
UNIT_ID = re.compile(r"^([1-9]\d*)-([1-9]\d*)$")
GROUP_ID = re.compile(r"^([1-9]\d*)-([1-9]\d*)-([1-9]\d*)$")
LESSON_ID = re.compile(r"^([1-9]\d*)-([1-9]\d*)-([1-9]\d*)-([1-9]\d*)$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LESSON_TYPES = {
    "concept", "calculation", "comparison", "coding", "data-handling",
    "analysis", "interpretation", "sql", "implementation", "debugging",
    "exam-strategy",
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def required_object(report: Report, obj: dict[str, Any], fields: set[str], label: str) -> None:
    for field_name in sorted(fields - obj.keys()):
        report.error(f"{label}: missing {field_name}")


def validate_catalog() -> Report:
    report = Report()
    try:
        data = load_json(CATALOG_PATH)
    except Exception as exc:
        report.error(f"catalog: {exc}")
        return report
    required_object(report, data, {"version", "updated", "categories", "items"}, "catalog")
    categories = {item.get("id") for item in data.get("categories", [])}
    seen: set[str] = set()
    base_fields = {"id", "title", "description", "category", "subcategory", "tags", "level", "url", "created", "updated"}
    for index, item in enumerate(data.get("items", [])):
        label = f"catalog.items[{index}]"
        required_object(report, item, base_fields, label)
        item_id = item.get("id")
        if item_id in seen:
            report.error(f"{label}: duplicate id {item_id}")
        seen.add(item_id)
        if item.get("category") not in categories:
            report.error(f"{label}: unknown category {item.get('category')}")
        if item.get("kind", "page") not in {"page", "course"}:
            report.error(f"{label}: invalid kind")
        if item.get("kind") == "course":
            required_object(report, item, {"total_lessons", "completed_lessons", "progress_percent", "continue_url"}, label)
            total = item.get("total_lessons", -1)
            complete = item.get("completed_lessons", -1)
            if not isinstance(total, int) or not isinstance(complete, int) or not 0 <= complete <= total:
                report.error(f"{label}: invalid lesson counts")
    return report


def validate_curriculum(course_id: str) -> Report:
    report = Report()
    try:
        data = load_json(curriculum_path(course_id))
    except Exception as exc:
        report.error(f"{course_id}: {exc}")
        return report
    required_object(report, data, {"version", "course_id", "title", "certification", "mode", "authority", "verified_at", "sources", "sections"}, course_id)
    if data.get("course_id") != course_id:
        report.error(f"{course_id}: course_id mismatch")
    source_ids: set[str] = set()
    for index, source in enumerate(data.get("sources", [])):
        required_object(report, source, {"id", "title", "authority", "url", "effective_from", "effective_to", "retrieved_at"}, f"{course_id}.sources[{index}]")
        source_ids.add(source.get("id"))
    seen: set[str] = set()
    for section in data.get("sections", []):
        sid = str(section.get("id", ""))
        if not SECTION_ID.fullmatch(sid):
            report.error(f"{course_id}: invalid section id {sid}")
        for unit in section.get("units", []):
            uid = str(unit.get("id", ""))
            if not UNIT_ID.fullmatch(uid) or not uid.startswith(f"{sid}-"):
                report.error(f"{course_id}: invalid unit id {uid}")
            for group in unit.get("lessons", []):
                gid = str(group.get("id", ""))
                if not GROUP_ID.fullmatch(gid) or not gid.startswith(f"{uid}-"):
                    report.error(f"{course_id}: invalid lesson group id {gid}")
                if not group.get("sublessons"):
                    report.error(f"{course_id}: {gid} has no sublessons")
                for lesson in group.get("sublessons", []):
                    lid = str(lesson.get("id", ""))
                    label = f"{course_id}:{lid}"
                    required_object(report, lesson, {"id", "title", "slug", "topics", "lesson_type", "supplemental", "source_refs", "official_basis"}, label)
                    if not LESSON_ID.fullmatch(lid) or not lid.startswith(f"{gid}-"):
                        report.error(f"{label}: invalid four-part lesson id")
                    if lid in seen:
                        report.error(f"{label}: duplicate id")
                    seen.add(lid)
                    if not SLUG.fullmatch(str(lesson.get("slug", ""))):
                        report.error(f"{label}: invalid slug")
                    topics = lesson.get("topics", [])
                    if not isinstance(topics, list) or not topics:
                        report.error(f"{label}: topics must not be empty")
                    elif len(topics) > 3:
                        report.error(f"{label}: {len(topics)} topics exceeds maximum 3")
                    elif len(topics) == 1:
                        report.warn(f"{label}: one-topic atomic lesson; review manually")
                    if lesson.get("lesson_type") not in LESSON_TYPES:
                        report.error(f"{label}: invalid lesson_type")
                    missing_refs = set(lesson.get("source_refs", [])) - source_ids
                    if missing_refs:
                        report.error(f"{label}: unknown source refs {sorted(missing_refs)}")
                    if not lesson.get("official_basis") and not lesson.get("supplemental"):
                        report.error(f"{label}: official_basis required")
    if not seen:
        report.error(f"{course_id}: no learning lessons")
    markdown_path = curriculum_path(course_id).with_suffix(".md")
    if not markdown_path.exists():
        report.error(f"{course_id}: missing curriculum Markdown")
    else:
        markdown = markdown_path.read_text(encoding="utf-8")
        missing_in_markdown = [lesson_id for lesson_id in sorted(seen) if lesson_id not in markdown]
        if missing_in_markdown:
            report.error(f"{course_id}: lesson ids absent from Markdown {missing_in_markdown}")
    return report


def validate_coverage(course_id: str) -> Report:
    report = Report()
    try:
        curriculum = load_json(curriculum_path(course_id))
        coverage = load_json(coverage_path(course_id))
    except Exception as exc:
        report.error(f"{course_id} coverage: {exc}")
        return report
    required_object(report, coverage, {"version", "course_id", "verified_at", "official_item_count", "items"}, f"{course_id} coverage")
    if coverage.get("course_id") != course_id:
        report.error(f"{course_id}: coverage course_id mismatch")
    if coverage.get("official_item_count") != len(coverage.get("items", [])):
        report.error(
            f"{course_id}: expected {coverage.get('official_item_count')} official coverage items, "
            f"found {len(coverage.get('items', []))}"
        )
    lesson_ids = {lesson["id"] for lesson in iter_lessons(curriculum)}
    source_ids = {source["id"] for source in curriculum.get("sources", [])}
    covered_lessons: set[str] = set()
    official_paths: set[str] = set()
    for index, item in enumerate(coverage.get("items", [])):
        label = f"{course_id}.coverage[{index}]"
        required_object(report, item, {"official_path", "source_refs", "lesson_ids", "mapping"}, label)
        path = item.get("official_path")
        if path in official_paths:
            report.error(f"{label}: duplicate official_path")
        official_paths.add(path)
        refs = set(item.get("source_refs", []))
        if refs - source_ids:
            report.error(f"{label}: unknown source refs {sorted(refs - source_ids)}")
        mapped = set(item.get("lesson_ids", []))
        if not mapped:
            report.error(f"{label}: official item is unmapped")
        if mapped - lesson_ids:
            report.error(f"{label}: unknown lesson ids {sorted(mapped - lesson_ids)}")
        covered_lessons.update(mapped)
        if item.get("mapping") not in {"direct", "split", "supplemental"}:
            report.error(f"{label}: invalid mapping")
    nonsupplemental = {lesson["id"] for lesson in iter_lessons(curriculum) if not lesson.get("supplemental")}
    if nonsupplemental - covered_lessons:
        report.error(f"{course_id}: lessons absent from coverage {sorted(nonsupplemental - covered_lessons)}")
    if not official_paths:
        report.error(f"{course_id}: empty coverage matrix")
    return report


def validate_progress(course_id: str) -> Report:
    report = Report()
    try:
        curriculum = load_json(curriculum_path(course_id))
        progress = load_json(progress_path(course_id))
    except Exception as exc:
        report.error(f"{course_id} progress: {exc}")
        return report
    expected = {lesson["id"] for lesson in iter_lessons(curriculum)}
    actual = set(progress.get("lessons", {}))
    if expected != actual:
        report.error(f"{course_id}: progress ids differ; missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    for lesson_id, state in progress.get("lessons", {}).items():
        label = f"{course_id}:{lesson_id}"
        if state.get("status") not in STATUSES:
            report.error(f"{label}: invalid status")
        if state.get("status") == "published":
            if not state.get("ff") or not state.get("cc") or not state.get("url"):
                report.error(f"{label}: published requires ff, cc, and url")
        if state.get("ff") and state.get("status") == "pending":
            report.error(f"{label}: pending cannot have ff")
    return report


def validate_lessons(course_id: str) -> Report:
    report = Report()
    try:
        curriculum = load_json(curriculum_path(course_id))
        progress = load_json(progress_path(course_id))
    except Exception as exc:
        report.error(f"{course_id} lessons: {exc}")
        return report
    for lesson_id, state in progress.get("lessons", {}).items():
        try:
            lesson = find_lesson(curriculum, lesson_id)
        except KeyError as exc:
            report.error(str(exc))
            continue
        folder = lesson_dir(course_id, lesson)
        ff_path, cc_path = folder / "ff.md", folder / "cc.html"
        if state.get("ff"):
            if not ff_path.exists() or len(ff_path.read_text(encoding="utf-8").strip()) < 200:
                report.error(f"{course_id}:{lesson_id}: FF gate failed")
        if state.get("cc"):
            if not cc_path.exists():
                report.error(f"{course_id}:{lesson_id}: CC missing")
            else:
                html = cc_path.read_text(encoding="utf-8")
                lowered = html.lower()
                if len(html.encode("utf-8")) < 300 or ("<html" not in lowered and "<!doctype html" not in lowered):
                    report.error(f"{course_id}:{lesson_id}: CC structure gate failed")
                if re.match(r"^\s*```(?:html)?", html, re.IGNORECASE) or re.search(r"```\s*$", html):
                    report.error(f"{course_id}:{lesson_id}: CC contains markdown fence")
                if re.search(r"<script\b", html, re.IGNORECASE):
                    report.error(f"{course_id}:{lesson_id}: CC contains executable script")
                if re.search(
                    r"<(?:script|link|img|iframe|source)\b[^>]*(?:src|href)=[\"']https?://",
                    html,
                    re.IGNORECASE,
                ):
                    report.error(f"{course_id}:{lesson_id}: CC contains remote asset")
                if re.search(
                    r"id=[\"']ai-content-placeholder[\"'][^>]*(?:display\s*:\s*none|\bhidden\b)",
                    html,
                    re.IGNORECASE,
                ):
                    report.error(f"{course_id}:{lesson_id}: CC content remains hidden")
                if re.search(r"<html\s+[^>]*lang=[\"']KR[\"']", html):
                    report.error(f"{course_id}:{lesson_id}: CC uses country code KR instead of language code ko")
        if state.get("status") == "published":
            for filename in ("index.html", "ff.md", "cc.html", "meta.json"):
                if not (folder / filename).exists():
                    report.error(f"{course_id}:{lesson_id}: missing {filename}")
            if (folder / "meta.json").exists():
                try:
                    meta = load_json(folder / "meta.json")
                    if meta.get("lesson_id") != lesson_id or meta.get("status") != "published":
                        report.error(f"{course_id}:{lesson_id}: meta mismatch")
                except Exception as exc:
                    report.error(f"{course_id}:{lesson_id}: invalid meta: {exc}")
            if (folder / "index.html").exists():
                shell = (folder / "index.html").read_text(encoding="utf-8")
                for marker in ("ff-panel", "cc-panel", "cc.html", "lesson-viewer.js", "Course 목차"):
                    if marker not in shell:
                        report.error(f"{course_id}:{lesson_id}: shell missing {marker}")
                if not re.search(r"<iframe\b[^>]*\bsandbox=[\"'][\"']", shell, re.IGNORECASE):
                    report.error(f"{course_id}:{lesson_id}: CC iframe must use an empty sandbox")
            expected_url = lesson_url(course_id, lesson)
            if state.get("url") != expected_url:
                report.error(f"{course_id}:{lesson_id}: URL mismatch")
    viewer_path = CATALOG_PATH.parent / "assets" / "lesson-viewer.js"
    if not viewer_path.exists():
        report.error("global: missing lesson-viewer.js")
    else:
        viewer = viewer_path.read_text(encoding="utf-8")
        for marker in ("ff.md", "location.hash", "hashchange", "cc-frame"):
            if marker not in viewer:
                report.error(f"global: lesson viewer missing {marker}")
    return report


def validate_course(course_id: str) -> Report:
    report = Report()
    report.extend(validate_curriculum(course_id))
    report.extend(validate_coverage(course_id))
    if progress_path(course_id).exists():
        report.extend(validate_progress(course_id))
        report.extend(validate_lessons(course_id))
    return report
