"""Validation gates for catalogs, curricula, progress, and lesson artifacts."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ailey_public_profile import (
    AILEY_CC_PROFILE,
    AILEY_FF_PROFILE,
    raw_upstream_cc_errors,
    vendor_snapshot_errors,
)
from common import (
    CATALOG_PATH,
    STATUSES,
    artifact_record_errors,
    codex_artifact_quality_errors,
    coverage_path,
    curriculum_path,
    find_lesson,
    iter_lessons,
    lesson_dir,
    lesson_url,
    load_json,
    progress_path,
    sha256_file,
)
from prompt_profiles import (
    get_prompt_profile,
    prompt_profile_registry_errors,
)
from public_ailey_course_content import (
    corpus_content_quality_errors,
    public_ailey_content_quality_errors,
)
from render_ailey_public_cc import selected_lesson_sources


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

META_FIELDS = {
    "version", "course_id", "lesson_id", "title", "slug", "section_id",
    "section_title", "unit_id", "unit_title", "lesson_group_id",
    "lesson_group_title", "topics", "artifacts", "published_at", "status",
}
ARTIFACT_FIELDS = {"producer", "prompt_profile", "generated_at", "sha256"}
PRODUCERS = {"ailey-bailey-custom-gpt", "openai-codex"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _rfc3339(value: Any) -> bool:
    if not isinstance(value, str) or "T" not in value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def meta_schema_errors(meta: Any) -> list[str]:
    """Validate the closed ``meta.schema.json`` contract without dependencies."""
    if not isinstance(meta, dict):
        return ["metadata must be an object"]
    errors = []
    missing = META_FIELDS - meta.keys()
    extra = meta.keys() - META_FIELDS
    if missing:
        errors.append(f"metadata missing fields: {sorted(missing)}")
    if extra:
        errors.append(f"metadata has unknown fields: {sorted(extra)}")
    if meta.get("version") != 2:
        errors.append("metadata version must be 2")
    for key, pattern in (
        ("course_id", SLUG), ("lesson_id", LESSON_ID), ("slug", SLUG),
    ):
        value = meta.get(key)
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            errors.append(f"metadata {key} has invalid format")
    for key in (
        "title", "section_id", "section_title", "unit_id", "unit_title",
        "lesson_group_id", "lesson_group_title",
    ):
        if not isinstance(meta.get(key), str) or not meta[key]:
            errors.append(f"metadata {key} must be a non-empty string")
    topics = meta.get("topics")
    if (
        not isinstance(topics, list)
        or not 1 <= len(topics) <= 3
        or any(not isinstance(topic, str) or not topic for topic in topics)
    ):
        errors.append("metadata topics must contain one to three non-empty strings")
    status = meta.get("status")
    if status not in STATUSES:
        errors.append("metadata status is invalid")
    published_at = meta.get("published_at")
    if published_at is not None and not _rfc3339(published_at):
        errors.append("metadata published_at must be an RFC3339 date-time or null")
    artifacts = meta.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("metadata artifacts must be an object")
        artifacts = {}
    else:
        if set(artifacts) != {"ff", "cc"}:
            errors.append("metadata artifacts must contain exactly ff and cc")
    for kind in ("ff", "cc"):
        record = artifacts.get(kind)
        if record is None and status != "published":
            continue
        if not isinstance(record, dict):
            errors.append(f"metadata artifacts.{kind} must be an artifact object")
            continue
        if set(record) != ARTIFACT_FIELDS:
            errors.append(
                f"metadata artifacts.{kind} must contain exactly "
                f"{sorted(ARTIFACT_FIELDS)}"
            )
        if record.get("producer") not in PRODUCERS:
            errors.append(f"metadata artifacts.{kind}.producer is invalid")
        if not isinstance(record.get("prompt_profile"), str) or not record["prompt_profile"]:
            errors.append(f"metadata artifacts.{kind}.prompt_profile is invalid")
        if not _rfc3339(record.get("generated_at")):
            errors.append(f"metadata artifacts.{kind}.generated_at is invalid")
        digest = record.get("sha256")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            errors.append(f"metadata artifacts.{kind}.sha256 is invalid")
    if status == "published" and not _rfc3339(published_at):
        errors.append("published metadata requires published_at")
    return list(dict.fromkeys(errors))


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


def validate_prompt_infrastructure() -> Report:
    """Validate prompt profiles and the pinned public-Ailey source snapshot."""
    report = Report()
    for error in prompt_profile_registry_errors():
        report.error(f"prompt profiles: {error}")
    for error in vendor_snapshot_errors():
        report.error(f"Ailey vendor snapshot: {error}")
    return report


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
                    has_singleton_reason = "singleton_reason" in lesson
                    if has_singleton_reason and (
                        not isinstance(topics, list) or len(topics) != 1
                    ):
                        report.error(
                            f"{label}: singleton_reason requires exactly one topic"
                        )
                    if not isinstance(topics, list) or not topics:
                        report.error(f"{label}: topics must not be empty")
                    elif any(
                        not isinstance(topic, str) or not topic.strip()
                        for topic in topics
                    ):
                        report.error(
                            f"{label}: topics must contain non-empty strings"
                        )
                    elif len(topics) > 3:
                        report.error(f"{label}: {len(topics)} topics exceeds maximum 3")
                    elif len(topics) == 1 and not (
                        isinstance(lesson.get("singleton_reason"), str)
                        and lesson["singleton_reason"].strip()
                    ):
                        report.warn(f"{label}: one-topic atomic lesson; review manually")
                    corrections = lesson.get("topic_corrections")
                    if corrections is not None:
                        if not isinstance(corrections, dict) or not corrections:
                            report.error(
                                f"{label}: topic_corrections must be a non-empty object"
                            )
                        else:
                            for original, corrected in corrections.items():
                                if original not in topics:
                                    report.error(
                                        f"{label}: topic_corrections key is not an "
                                        f"official topic: {original!r}"
                                    )
                                if (
                                    not isinstance(corrected, str)
                                    or not corrected.strip()
                                    or corrected == original
                                ):
                                    report.error(
                                        f"{label}: topic_corrections value for "
                                        f"{original!r} must be a distinct non-empty string"
                                    )
                    duplicate_reason = lesson.get("duplicate_topic_reason")
                    has_duplicate_topics = (
                        isinstance(topics, list)
                        and all(isinstance(topic, str) for topic in topics)
                        and len(topics) != len(set(topics))
                    )
                    if has_duplicate_topics and not (
                        isinstance(duplicate_reason, str)
                        and duplicate_reason.strip()
                    ):
                        report.error(
                            f"{label}: duplicate official topics require "
                            "duplicate_topic_reason"
                        )
                    if duplicate_reason is not None and not has_duplicate_topics:
                        report.error(
                            f"{label}: duplicate_topic_reason requires duplicate topics"
                        )
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
    items = coverage.get("items", [])
    if coverage.get("official_item_count") != len(items):
        report.error(
            f"{course_id}: expected {coverage.get('official_item_count')} official coverage items, "
            f"found {len(items)}"
        )
    lessons = list(iter_lessons(curriculum))
    lesson_ids = {lesson["id"] for lesson in lessons}
    lesson_by_id = {lesson["id"]: lesson for lesson in lessons}
    source_ids = {source["id"] for source in curriculum.get("sources", [])}
    covered_lessons: set[str] = set()
    official_paths: set[str] = set()
    official_atom_mode = coverage.get("coverage_granularity") == "official-atom"
    expected_atoms = Counter(
        (lesson["id"], topic)
        for lesson in lessons
        for topic in lesson.get("topics", [])
    )
    covered_atoms: Counter[tuple[str, str]] = Counter()
    for index, item in enumerate(items):
        label = f"{course_id}.coverage[{index}]"
        required_fields = {
            "official_path",
            "source_refs",
            "lesson_ids",
            "mapping",
        }
        if official_atom_mode:
            required_fields.add("official_atom")
        required_object(report, item, required_fields, label)
        path = item.get("official_path")
        if path in official_paths:
            report.error(f"{label}: duplicate official_path")
        official_paths.add(path)
        refs = set(item.get("source_refs", []))
        if refs - source_ids:
            report.error(f"{label}: unknown source refs {sorted(refs - source_ids)}")
        item_lesson_ids = item.get("lesson_ids", [])
        if isinstance(item_lesson_ids, list) and all(
            isinstance(lesson_id, str) for lesson_id in item_lesson_ids
        ):
            mapped = set(item_lesson_ids)
        else:
            mapped = set()
            report.error(f"{label}: lesson_ids must be an array of strings")
        if not mapped:
            report.error(f"{label}: official item is unmapped")
        if mapped - lesson_ids:
            report.error(f"{label}: unknown lesson ids {sorted(mapped - lesson_ids)}")
        covered_lessons.update(mapped)
        if item.get("mapping") not in {"direct", "split", "supplemental"}:
            report.error(f"{label}: invalid mapping")
        if official_atom_mode:
            atom = item.get("official_atom")
            if not isinstance(atom, str) or not atom.strip():
                report.error(
                    f"{label}: official_atom must be a non-empty string"
                )
            if (
                not isinstance(item_lesson_ids, list)
                or len(item_lesson_ids) != 1
            ):
                report.error(
                    f"{label}: official-atom item must map to exactly one lesson"
                )
            if item.get("mapping") != "direct":
                report.error(
                    f"{label}: official-atom item mapping must be direct"
                )
            if (
                isinstance(atom, str)
                and atom.strip()
                and isinstance(item_lesson_ids, list)
                and len(item_lesson_ids) == 1
                and isinstance(item_lesson_ids[0], str)
            ):
                lesson_id = item_lesson_ids[0]
                lesson = lesson_by_id.get(lesson_id)
                if lesson is not None and atom not in lesson.get("topics", []):
                    report.error(
                        f"{label}: official_atom is not a topic of lesson "
                        f"{lesson_id}"
                    )
                covered_atoms[(lesson_id, atom)] += 1
    nonsupplemental = {lesson["id"] for lesson in iter_lessons(curriculum) if not lesson.get("supplemental")}
    if nonsupplemental - covered_lessons:
        report.error(f"{course_id}: lessons absent from coverage {sorted(nonsupplemental - covered_lessons)}")
    if not official_paths:
        report.error(f"{course_id}: empty coverage matrix")
    if official_atom_mode:
        expected_count = sum(expected_atoms.values())
        if coverage.get("official_item_count") != expected_count:
            report.error(
                f"{course_id}: official_item_count must equal curriculum "
                f"topic atom count {expected_count}, found "
                f"{coverage.get('official_item_count')}"
            )
        if covered_atoms != expected_atoms:
            missing = expected_atoms - covered_atoms
            extra = covered_atoms - expected_atoms

            def describe(counter: Counter[tuple[str, str]]) -> list[str]:
                return [
                    f"{lesson_id}:{atom!r} x{count}"
                    for (lesson_id, atom), count in sorted(counter.items())
                ]

            report.error(
                f"{course_id}: official-atom coverage does not match "
                f"curriculum leaf topics; missing={describe(missing)} "
                f"extra={describe(extra)}"
            )
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
    ff_hashes: dict[str, str] = {}
    public_ailey_ffs: dict[str, str] = {}
    for lesson_id, state in progress.get("lessons", {}).items():
        try:
            lesson = find_lesson(curriculum, lesson_id)
        except KeyError as exc:
            report.error(str(exc))
            continue
        folder = lesson_dir(course_id, lesson)
        ff_path, cc_path = folder / "ff.md", folder / "cc.html"
        meta_path = folder / "meta.json"
        meta: dict[str, Any] | None = None
        if meta_path.exists():
            try:
                meta = load_json(meta_path)
            except Exception as exc:
                report.error(f"{course_id}:{lesson_id}: invalid meta: {exc}")
            else:
                for error in meta_schema_errors(meta):
                    report.error(f"{course_id}:{lesson_id}: {error}")
        if state.get("ff"):
            ff_source = ff_path.read_text(encoding="utf-8") if ff_path.exists() else ""
            if (
                len(ff_source.strip()) < 200
                or (lesson["title"] not in ff_source and lesson_id not in ff_source)
            ):
                report.error(f"{course_id}:{lesson_id}: FF gate failed")
            elif ff_path.exists():
                digest = sha256_file(ff_path)
                if digest in ff_hashes:
                    report.error(
                        f"{course_id}:{lesson_id}: FF duplicates {ff_hashes[digest]} exactly"
                    )
                else:
                    ff_hashes[digest] = lesson_id
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
                if lesson["title"] not in html and lesson_id not in html:
                    report.error(f"{course_id}:{lesson_id}: CC does not identify its lesson")
        provenance_kinds = {
            kind for kind in ("ff", "cc")
            if state.get(kind) or state.get("status") == "published"
        }
        if provenance_kinds:
            if meta is None:
                report.error(f"{course_id}:{lesson_id}: provenance metadata is missing")
            else:
                if meta.get("version") != 2:
                    report.error(f"{course_id}:{lesson_id}: meta must use version 2")
                artifacts = meta.get("artifacts")
                if not isinstance(artifacts, dict):
                    report.error(f"{course_id}:{lesson_id}: meta artifacts must be an object")
                else:
                    for kind in sorted(provenance_kinds):
                        artifact_path = ff_path if kind == "ff" else cc_path
                        record = artifacts.get(kind)
                        for error in artifact_record_errors(record, artifact_path):
                            report.error(
                                f"{course_id}:{lesson_id}: {kind.upper()} {error}"
                            )
                        if isinstance(record, dict):
                            prompt_profile = record.get("prompt_profile")
                            producer = record.get("producer")
                            try:
                                get_prompt_profile(
                                    prompt_profile,
                                    artifact_kind=kind,
                                    producer=producer,
                                )
                            except (
                                KeyError,
                                OSError,
                                UnicodeError,
                                ValueError,
                            ) as exc:
                                report.error(
                                    f"{course_id}:{lesson_id}: {kind.upper()} "
                                    f"prompt profile: {exc}"
                                )
                        if (
                            isinstance(record, dict)
                            and record.get("producer") == "openai-codex"
                        ):
                            try:
                                source = artifact_path.read_text(encoding="utf-8")
                            except (OSError, UnicodeError) as exc:
                                report.error(
                                    f"{course_id}:{lesson_id}: {kind.upper()} "
                                    f"cannot be read as UTF-8: {exc}"
                                )
                            else:
                                prompt_profile = record.get("prompt_profile")
                                if (
                                    kind == "ff"
                                    and prompt_profile == AILEY_FF_PROFILE
                                ):
                                    public_ailey_ffs[lesson_id] = source
                                    quality_errors = (
                                        public_ailey_content_quality_errors(
                                            course_id,
                                            curriculum,
                                            lesson,
                                            source,
                                        )
                                    )
                                elif (
                                    kind == "cc"
                                    and prompt_profile == AILEY_CC_PROFILE
                                ):
                                    try:
                                        official_sources = selected_lesson_sources(
                                            curriculum,
                                            lesson,
                                        )
                                    except ValueError as exc:
                                        quality_errors = [
                                            f"cannot resolve official source "
                                            f"allowlist: {exc}"
                                        ]
                                    else:
                                        quality_errors = raw_upstream_cc_errors(
                                            source,
                                            lesson["topics"],
                                            allowed_urls=[
                                                item["url"]
                                                for item in official_sources
                                            ],
                                        )
                                else:
                                    quality_errors = (
                                        codex_artifact_quality_errors(
                                            kind,
                                            source,
                                            lesson["topics"],
                                        )
                                    )
                                for error in quality_errors:
                                    report.error(
                                        f"{course_id}:{lesson_id}: {kind.upper()} "
                                        f"{prompt_profile} quality gate: {error}"
                                    )
        if state.get("status") == "published":
            for filename in ("index.html", "ff.md", "cc.html", "cc-view.html", "meta.json"):
                if not (folder / filename).exists():
                    report.error(f"{course_id}:{lesson_id}: missing {filename}")
            if meta is not None:
                if (
                    meta.get("course_id") != course_id
                    or meta.get("lesson_id") != lesson_id
                    or meta.get("status") != "published"
                ):
                    report.error(f"{course_id}:{lesson_id}: meta mismatch")
                if not isinstance(meta.get("published_at"), str):
                    report.error(f"{course_id}:{lesson_id}: published_at is required")
            if (folder / "index.html").exists():
                shell = (folder / "index.html").read_text(encoding="utf-8")
                for marker in (
                    "ff-panel",
                    "cc-panel",
                    "cc-view.html",
                    "lesson-viewer.js",
                    ">목차</a>",
                ):
                    if marker not in shell:
                        report.error(f"{course_id}:{lesson_id}: shell missing {marker}")
                if not re.search(r"<iframe\b[^>]*\bsandbox=[\"'][\"']", shell, re.IGNORECASE):
                    report.error(f"{course_id}:{lesson_id}: CC iframe must use an empty sandbox")
            cc_view_path = folder / "cc-view.html"
            if cc_view_path.exists():
                cc_view = cc_view_path.read_text(encoding="utf-8")
                for marker in (
                    'src="./cc.html"',
                    'id="cc-document"',
                    ">돌아가기</a>",
                    ">목차</a>",
                    'aria-label="다음 장"',
                    "cc-page-next",
                    "cc-viewer.js?v=scroll-direction-1",
                ):
                    if marker not in cc_view:
                        report.error(f"{course_id}:{lesson_id}: CC viewer missing {marker}")
                if not re.search(
                    r"<iframe\b[^>]*\bsandbox=[\"']allow-same-origin[\"']",
                    cc_view,
                    re.IGNORECASE,
                ):
                    report.error(
                        f"{course_id}:{lesson_id}: CC viewer iframe must only allow same-origin inspection"
                    )
                if "allow-scripts" in cc_view.lower():
                    report.error(
                        f"{course_id}:{lesson_id}: CC viewer iframe must block scripts"
                    )
            expected_url = lesson_url(course_id, lesson)
            if state.get("url") != expected_url:
                report.error(f"{course_id}:{lesson_id}: URL mismatch")
    if len(public_ailey_ffs) > 1:
        for error in corpus_content_quality_errors(
            course_id,
            curriculum,
            public_ailey_ffs,
            include_lesson_errors=False,
        ):
            report.error(f"{course_id}: public Ailey corpus quality gate: {error}")
    viewer_path = CATALOG_PATH.parent / "assets" / "lesson-viewer.js"
    if not viewer_path.exists():
        report.error("global: missing lesson-viewer.js")
    else:
        viewer = viewer_path.read_text(encoding="utf-8")
        for marker in (
            "ff.md",
            "location.hash",
            "hashchange",
            "cc-frame",
            "location.assign(frame.src)",
        ):
            if marker not in viewer:
                report.error(f"global: lesson viewer missing {marker}")
    cc_viewer_path = CATALOG_PATH.parent / "assets" / "cc-viewer.js"
    if not cc_viewer_path.exists():
        report.error("global: missing cc-viewer.js")
    else:
        cc_viewer = cc_viewer_path.read_text(encoding="utf-8")
        for marker in (
            "frame.contentDocument?.scrollingElement",
            "addEventListener('scroll'",
            "scrollTop < lastScrollTop",
            "scrollTop > lastScrollTop",
            "toolbar-hidden",
            "matchMedia('(max-width: 680px)')",
        ):
            if marker not in cc_viewer:
                report.error(f"global: CC viewer missing {marker}")
    return report


def validate_course(course_id: str) -> Report:
    report = Report()
    report.extend(validate_curriculum(course_id))
    report.extend(validate_coverage(course_id))
    if progress_path(course_id).exists():
        report.extend(validate_progress(course_id))
        report.extend(validate_lessons(course_id))
    return report
