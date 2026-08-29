"""Validation rules for source evidence, question variants, and public exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from common import load_json
from question_bank_common import (
    curriculum_topic_map,
    flatten_appearances,
    load_question_bank,
    question_content_hash,
    stable_json_hash,
)
from study_json_schema import json_schema_errors


RIGHTS_STATUSES = {"public_fulltext", "private_only", "link_only", "blocked"}
SOURCE_TYPES = {"official", "cbt", "reconstruction", "blog", "book_sample", "other"}
RELIABILITIES = {"high", "medium", "low"}
ROUND_STATUSES = {"held", "cancelled", "scheduled"}
ROUND_VERIFICATION_STATUSES = {
    "official_confirmed",
    "multi_source_confirmed",
    "source_reported",
    "unverified",
}
ORIGIN_TYPES = {"official_public", "reconstruction", "reported_topic"}
CONTENT_MODES = {"full", "summary", "link_only"}
ANSWER_STATUSES = {
    "official_verified",
    "expert_reviewed",
    "multi_source_corroborated",
    "conflicting",
    "unverified",
}
REVIEW_STATUSES = {"approved", "needs_review"}
SCOPE_STATUSES = {"in_scope", "out_of_scope", "uncertain"}
ANALYSIS_ANSWER_STATUSES = {
    "official_verified",
    "expert_reviewed",
    "multi_source_corroborated",
}
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"


@dataclass
class QuestionBankReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def _required(report: QuestionBankReport, obj: Any, fields: set[str], label: str) -> None:
    if not isinstance(obj, dict):
        report.error(f"{label}: must be an object")
        return
    for field_name in sorted(fields - obj.keys()):
        report.error(f"{label}: missing {field_name}")


def _valid_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


@lru_cache(maxsize=2)
def _load_schema(filename: str) -> dict[str, Any]:
    return load_json(SCHEMAS_DIR / filename)


def _validate_against_schema(
    report: QuestionBankReport,
    value: Any,
    filename: str,
    label: str,
) -> None:
    for error in json_schema_errors(value, _load_schema(filename)):
        report.error(f"{label} schema: {error}")


def _validate_public_canonical_is_self_contained(
    report: QuestionBankReport,
    bundle: dict[str, dict[str, Any]],
) -> None:
    """Prevent tracked documents from resolving rights-sensitive refs via overlays."""
    sources = bundle["sources"].get("sources", [])
    public_source_ids = {
        item.get("source_id")
        for item in sources
        if isinstance(item, dict) and item.get("source_id")
    }
    rounds = bundle["rounds"].get("rounds", [])
    public_round_ids = {
        item.get("round_id")
        for item in rounds
        if isinstance(item, dict) and item.get("round_id")
    }
    variants = bundle["variants"].get("variants", [])
    public_variant_ids = {
        item.get("variant_id")
        for item in variants
        if isinstance(item, dict) and item.get("variant_id")
    }
    for index, item in enumerate(rounds if isinstance(rounds, list) else []):
        if not isinstance(item, dict):
            continue
        for source_id in item.get("source_ids", []):
            if not isinstance(source_id, str) or source_id not in public_source_ids:
                report.error(
                    f"question-bank.public.rounds[{index}]: source_id {source_id} "
                    "must be defined in tracked sources.json"
                )
    for index, item in enumerate(variants if isinstance(variants, list) else []):
        if not isinstance(item, dict):
            continue
        if (
            not isinstance(item.get("source_id"), str)
            or item.get("source_id") not in public_source_ids
        ):
            report.error(
                f"question-bank.public.variants[{index}]: source_id "
                f"{item.get('source_id')} must be defined in tracked sources.json"
            )
    public_question_ids: set[str] = set()
    public_appearance_ids: set[str] = set()
    groups = bundle["groups"].get("groups", [])
    for group_index, group in enumerate(groups if isinstance(groups, list) else []):
        if not isinstance(group, dict):
            continue
        if isinstance(group.get("question_id"), str):
            public_question_ids.add(group["question_id"])
        for appearance_index, appearance in enumerate(group.get("appearances", [])):
            if not isinstance(appearance, dict):
                continue
            if isinstance(appearance.get("appearance_id"), str):
                public_appearance_ids.add(appearance["appearance_id"])
            label = (
                f"question-bank.public.groups[{group_index}]."
                f"appearances[{appearance_index}]"
            )
            if (
                not isinstance(appearance.get("round_id"), str)
                or appearance.get("round_id") not in public_round_ids
            ):
                report.error(
                    f"{label}: round_id {appearance.get('round_id')} must be "
                    "defined in tracked rounds.json"
                )
            for variant_id in appearance.get("variant_ids", []):
                if (
                    not isinstance(variant_id, str)
                    or variant_id not in public_variant_ids
                ):
                    report.error(
                        f"{label}: variant_id {variant_id} must be defined in "
                        "tracked question-variants.json"
                    )
    annotations = bundle["annotations"].get("annotations", [])
    for index, item in enumerate(
        annotations if isinstance(annotations, list) else []
    ):
        if not isinstance(item, dict):
            continue
        if (
            item.get("question_id") not in public_question_ids
            or item.get("appearance_id") not in public_appearance_ids
        ):
            report.error(
                f"question-bank.public.annotations[{index}]: references must be "
                "defined in tracked question-groups.json"
            )
    analysis_sets = bundle["analysis_sets"].get("analysis_sets", [])
    for index, item in enumerate(
        analysis_sets if isinstance(analysis_sets, list) else []
    ):
        if not isinstance(item, dict):
            continue
        for appearance_id in item.get("included_appearance_ids", []):
            if (
                not isinstance(appearance_id, str)
                or appearance_id not in public_appearance_ids
            ):
                report.error(
                    f"question-bank.public.analysis_sets[{index}]: appearance_id "
                    f"{appearance_id} must be defined in tracked question-groups.json"
                )


def _document_header(
    report: QuestionBankReport,
    document: dict[str, Any],
    course_id: str,
    label: str,
) -> None:
    _required(report, document, {"schema_version", "course_id"}, label)
    if document.get("schema_version") != 1:
        report.error(f"{label}: schema_version must be 1")
    if document.get("course_id") != course_id:
        report.error(f"{label}: course_id mismatch")


def validate_question_bank_data(course_id: str) -> QuestionBankReport:
    report = QuestionBankReport()
    try:
        public_bundle = load_question_bank(course_id, include_private=False)
        bundle = load_question_bank(course_id, include_private=True)
        topics = curriculum_topic_map(course_id)
    except Exception as exc:
        report.error(f"{course_id} question bank: {exc}")
        return report

    canonical_schema = "question-bank-canonical.schema.json"
    for kind, document in public_bundle.items():
        _validate_against_schema(
            report,
            document,
            canonical_schema,
            f"question-bank.public.{kind}",
        )
    if bundle != public_bundle:
        for kind, document in bundle.items():
            _validate_against_schema(
                report,
                document,
                canonical_schema,
                f"question-bank.combined.{kind}",
            )
    _validate_public_canonical_is_self_contained(report, public_bundle)

    for index, source in enumerate(public_bundle["sources"].get("sources", [])):
        if (
            isinstance(source, dict)
            and source.get("rights", {}).get("status") == "private_only"
        ):
            report.error(
                f"question-bank.sources[{index}]: private_only sources must live "
                "under the ignored private/ overlay"
            )

    for kind, document in bundle.items():
        _document_header(report, document, course_id, f"question-bank.{kind}")

    sources = bundle["sources"].get("sources", [])
    if not isinstance(sources, list):
        report.error("question-bank.sources: sources must be an array")
        sources = []
    source_by_id: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        label = f"question-bank.sources[{index}]"
        _required(
            report,
            source,
            {
                "source_id", "title", "url", "provider", "source_type",
                "accessed_at", "reliability", "rights", "notes",
            },
            label,
        )
        if not isinstance(source, dict):
            continue
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            report.error(f"{label}: invalid source_id")
        elif source_id in source_by_id:
            report.error(f"{label}: duplicate source_id {source_id}")
        else:
            source_by_id[source_id] = source
        if not _valid_http_url(source.get("url")):
            report.error(f"{label}: url must be an absolute HTTP(S) URL")
        if source.get("source_type") not in SOURCE_TYPES:
            report.error(f"{label}: invalid source_type")
        if source.get("reliability") not in RELIABILITIES:
            report.error(f"{label}: invalid reliability")
        if not _valid_date(source.get("accessed_at")):
            report.error(f"{label}: accessed_at must be YYYY-MM-DD")
        rights = source.get("rights")
        _required(report, rights, {"status", "basis", "terms_url", "notes"}, f"{label}.rights")
        if isinstance(rights, dict):
            if rights.get("status") not in RIGHTS_STATUSES:
                report.error(f"{label}: invalid rights status")
            terms_url = rights.get("terms_url")
            if terms_url is not None and not _valid_http_url(terms_url):
                report.error(f"{label}: terms_url must be null or an absolute HTTP(S) URL")

    rounds = bundle["rounds"].get("rounds", [])
    if not isinstance(rounds, list):
        report.error("question-bank.rounds: rounds must be an array")
        rounds = []
    round_by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(rounds):
        label = f"question-bank.rounds[{index}]"
        _required(
            report,
            item,
            {
                "round_id", "exam_round", "exam_date", "status",
                "expected_questions", "verification_status", "source_ids",
                "curriculum_version_id",
            },
            label,
        )
        if not isinstance(item, dict):
            continue
        round_id = item.get("round_id")
        if not isinstance(round_id, str) or not round_id:
            report.error(f"{label}: invalid round_id")
        elif round_id in round_by_id:
            report.error(f"{label}: duplicate round_id {round_id}")
        else:
            round_by_id[round_id] = item
        if not isinstance(item.get("exam_round"), int) or item.get("exam_round", 0) < 1:
            report.error(f"{label}: exam_round must be a positive integer")
        exam_date = item.get("exam_date")
        if exam_date is not None and not _valid_date(exam_date):
            report.error(f"{label}: exam_date must be null or YYYY-MM-DD")
        if item.get("status") not in ROUND_STATUSES:
            report.error(f"{label}: invalid status")
        if item.get("verification_status") not in ROUND_VERIFICATION_STATUSES:
            report.error(f"{label}: invalid verification_status")
        expected = item.get("expected_questions")
        if expected is not None and (not isinstance(expected, int) or expected < 1):
            report.error(f"{label}: expected_questions must be null or positive")
        refs = item.get("source_ids", [])
        if not isinstance(refs, list) or not refs:
            report.error(f"{label}: source_ids must not be empty")
        else:
            for source_id in refs:
                if not isinstance(source_id, str) or source_id not in source_by_id:
                    report.error(f"{label}: unknown source_id {source_id}")

    variants = bundle["variants"].get("variants", [])
    if not isinstance(variants, list):
        report.error("question-bank.variants: variants must be an array")
        variants = []
    variant_by_id: dict[str, dict[str, Any]] = {}
    for index, variant in enumerate(variants):
        label = f"question-bank.variants[{index}]"
        _required(
            report,
            variant,
            {
                "variant_id", "question_id", "appearance_id", "source_id",
                "content_mode", "question_text", "choices", "answer_claim",
                "answer_status", "concept_summary", "source_locator",
                "content_hash", "review_status",
            },
            label,
        )
        if not isinstance(variant, dict):
            continue
        variant_id = variant.get("variant_id")
        if not isinstance(variant_id, str) or not variant_id:
            report.error(f"{label}: invalid variant_id")
        elif variant_id in variant_by_id:
            report.error(f"{label}: duplicate variant_id {variant_id}")
        else:
            variant_by_id[variant_id] = variant
        source_id = variant.get("source_id")
        source = source_by_id.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            report.error(f"{label}: unknown source_id {source_id}")
        elif source.get("rights", {}).get("status") == "blocked":
            report.error(f"{label}: blocked sources cannot supply question variants")
        mode = variant.get("content_mode")
        if mode not in CONTENT_MODES:
            report.error(f"{label}: invalid content_mode")
        choices = variant.get("choices")
        if not isinstance(choices, list):
            report.error(f"{label}: choices must be an array")
            choices = []
        if mode == "full":
            if not isinstance(variant.get("question_text"), str) or not variant["question_text"].strip():
                report.error(f"{label}: full content requires question_text")
            if len(choices) < 2 or any(not isinstance(choice, str) or not choice.strip() for choice in choices):
                report.error(f"{label}: full content requires at least two non-empty choices")
            rights_status = (source or {}).get("rights", {}).get("status")
            if rights_status not in {"public_fulltext", "private_only"}:
                report.error(f"{label}: full content is forbidden for rights status {rights_status}")
            computed_hash = question_content_hash(variant.get("question_text"), choices)
            if variant.get("content_hash") != computed_hash:
                report.error(f"{label}: content_hash does not match normalized content")
        elif variant.get("question_text") is not None or choices:
            report.error(f"{label}: {mode} content cannot store question_text or choices")
        if variant.get("answer_status") not in ANSWER_STATUSES:
            report.error(f"{label}: invalid answer_status")
        answer = variant.get("answer_claim")
        if answer is not None and (not isinstance(answer, int) or answer < 1):
            report.error(f"{label}: answer_claim must be null or a positive integer")
        if answer is not None and choices and answer > len(choices):
            report.error(f"{label}: answer_claim exceeds choices")
        if variant.get("review_status") not in REVIEW_STATUSES:
            report.error(f"{label}: invalid review_status")
        if not isinstance(variant.get("concept_summary"), str) or not variant["concept_summary"].strip():
            report.error(f"{label}: concept_summary must be a non-empty independent summary")
        if not isinstance(variant.get("source_locator"), str) or not variant["source_locator"].strip():
            report.error(f"{label}: source_locator must be non-empty")

    groups = bundle["groups"].get("groups", [])
    if not isinstance(groups, list):
        report.error("question-bank.groups: groups must be an array")
        groups = []
    seen_question_ids: set[str] = set()
    seen_appearance_ids: set[str] = set()
    appearance_by_id: dict[str, dict[str, Any]] = {}
    referenced_variant_ids: set[str] = set()
    for index, group in enumerate(groups):
        label = f"question-bank.groups[{index}]"
        _required(
            report,
            group,
            {"question_id", "origin_type", "appearances", "duplicate_group"},
            label,
        )
        if not isinstance(group, dict):
            continue
        question_id = group.get("question_id")
        if not isinstance(question_id, str) or not question_id:
            report.error(f"{label}: invalid question_id")
        elif question_id in seen_question_ids:
            report.error(f"{label}: duplicate question_id {question_id}")
        else:
            seen_question_ids.add(question_id)
        if group.get("origin_type") not in ORIGIN_TYPES:
            report.error(f"{label}: invalid origin_type")
        appearances = group.get("appearances", [])
        if not isinstance(appearances, list) or not appearances:
            report.error(f"{label}: appearances must not be empty")
            continue
        for appearance_index, appearance in enumerate(appearances):
            appearance_label = f"{label}.appearances[{appearance_index}]"
            _required(
                report,
                appearance,
                {
                    "appearance_id", "round_id", "question_number", "variant_ids",
                    "primary_topic_code", "topic_codes", "scope_status",
                    "review_status", "analysis_eligible",
                },
                appearance_label,
            )
            if not isinstance(appearance, dict):
                continue
            appearance_id = appearance.get("appearance_id")
            if not isinstance(appearance_id, str) or not appearance_id:
                report.error(f"{appearance_label}: invalid appearance_id")
            elif appearance_id in seen_appearance_ids:
                report.error(f"{appearance_label}: duplicate appearance_id {appearance_id}")
            else:
                seen_appearance_ids.add(appearance_id)
                appearance_by_id[appearance_id] = appearance
            round_id = appearance.get("round_id")
            round_item = round_by_id.get(round_id) if isinstance(round_id, str) else None
            if round_item is None:
                report.error(f"{appearance_label}: unknown round_id {round_id}")
            number = appearance.get("question_number")
            if number is not None and (not isinstance(number, int) or number < 1):
                report.error(f"{appearance_label}: question_number must be null or positive")
            topic_codes = appearance.get("topic_codes")
            primary = appearance.get("primary_topic_code")
            if not isinstance(topic_codes, list) or not topic_codes:
                report.error(f"{appearance_label}: topic_codes must not be empty")
                topic_codes = []
            if primary not in topic_codes:
                report.error(f"{appearance_label}: primary_topic_code must be in topic_codes")
            for topic_code in topic_codes:
                if not isinstance(topic_code, str) or topic_code not in topics:
                    report.error(f"{appearance_label}: unknown topic code {topic_code}")
            variant_ids = appearance.get("variant_ids")
            if not isinstance(variant_ids, list) or not variant_ids:
                report.error(f"{appearance_label}: variant_ids must not be empty")
                variant_ids = []
            for variant_id in variant_ids:
                if not isinstance(variant_id, str):
                    report.error(f"{appearance_label}: invalid variant_id {variant_id!r}")
                    continue
                referenced_variant_ids.add(variant_id)
                variant = variant_by_id.get(variant_id)
                if variant is None:
                    report.error(f"{appearance_label}: unknown variant_id {variant_id}")
                elif (
                    variant.get("question_id") != question_id
                    or variant.get("appearance_id") != appearance_id
                ):
                    report.error(f"{appearance_label}: variant {variant_id} ownership mismatch")
                elif (
                    round_item is not None
                    and variant.get("source_id") not in round_item.get("source_ids", [])
                ):
                    report.error(
                        f"{appearance_label}: variant {variant_id} source is not "
                        "registered for the round"
                    )
            if appearance.get("scope_status") not in SCOPE_STATUSES:
                report.error(f"{appearance_label}: invalid scope_status")
            if appearance.get("review_status") not in REVIEW_STATUSES:
                report.error(f"{appearance_label}: invalid review_status")
            if not isinstance(appearance.get("analysis_eligible"), bool):
                report.error(f"{appearance_label}: analysis_eligible must be boolean")
            if appearance.get("analysis_eligible") and (
                appearance.get("review_status") != "approved"
                or appearance.get("scope_status") != "in_scope"
                or (round_item or {}).get("status") != "held"
                or (round_item or {}).get("verification_status") == "unverified"
            ):
                report.error(
                    f"{appearance_label}: analysis eligibility requires approved, "
                    "in-scope evidence from a verified held round"
                )
    unreferenced = set(variant_by_id) - referenced_variant_ids
    if unreferenced:
        report.error(f"question-bank.variants: unreferenced variants {sorted(unreferenced)}")

    annotations = bundle["annotations"].get("annotations", [])
    if not isinstance(annotations, list):
        report.error("question-bank.annotations: annotations must be an array")
        annotations = []
    seen_annotation_ids: set[str] = set()
    for index, annotation in enumerate(annotations):
        label = f"question-bank.annotations[{index}]"
        _required(
            report,
            annotation,
            {
                "annotation_id", "question_id", "appearance_id", "keywords",
                "concept_summary", "difficulty", "explanation",
                "choice_explanations", "producer", "created_at", "review_status",
            },
            label,
        )
        if not isinstance(annotation, dict):
            continue
        annotation_id = annotation.get("annotation_id")
        if not isinstance(annotation_id, str) or not annotation_id:
            report.error(f"{label}: invalid annotation_id")
        elif annotation_id in seen_annotation_ids:
            report.error(f"{label}: duplicate annotation_id {annotation_id}")
        else:
            seen_annotation_ids.add(annotation_id)
        annotation_question_id = annotation.get("question_id")
        annotation_appearance_id = annotation.get("appearance_id")
        if (
            not isinstance(annotation_question_id, str)
            or annotation_question_id not in seen_question_ids
        ):
            report.error(f"{label}: unknown question_id {annotation.get('question_id')}")
        if (
            not isinstance(annotation_appearance_id, str)
            or annotation_appearance_id not in seen_appearance_ids
        ):
            report.error(f"{label}: unknown appearance_id {annotation.get('appearance_id')}")
        keywords = annotation.get("keywords")
        if not isinstance(keywords, list) or any(not isinstance(item, str) or not item.strip() for item in keywords):
            report.error(f"{label}: keywords must be an array of non-empty strings")
        if annotation.get("review_status") not in REVIEW_STATUSES:
            report.error(f"{label}: invalid review_status")
        if not _valid_timestamp(annotation.get("created_at")):
            report.error(f"{label}: created_at must be an ISO timestamp with offset")

    analysis_sets = bundle["analysis_sets"].get("analysis_sets", [])
    if not isinstance(analysis_sets, list):
        report.error("question-bank.analysis_sets: analysis_sets must be an array")
        analysis_sets = []
    seen_analysis_set_ids: set[str] = set()
    for index, analysis_set in enumerate(analysis_sets):
        label = f"question-bank.analysis_sets[{index}]"
        if not isinstance(analysis_set, dict):
            continue
        analysis_set_id = analysis_set.get("analysis_set_id")
        if not isinstance(analysis_set_id, str) or not analysis_set_id:
            report.error(f"{label}: invalid analysis_set_id")
        elif analysis_set_id in seen_analysis_set_ids:
            report.error(f"{label}: duplicate analysis_set_id {analysis_set_id}")
        else:
            seen_analysis_set_ids.add(analysis_set_id)
        for appearance_id in analysis_set.get("included_appearance_ids", []):
            if not isinstance(appearance_id, str):
                report.error(f"{label}: invalid appearance_id {appearance_id!r}")
                continue
            appearance = appearance_by_id.get(appearance_id)
            if appearance is None:
                report.error(f"{label}: unknown appearance_id {appearance_id}")
                continue
            round_item = round_by_id.get(appearance.get("round_id"), {})
            if (
                not appearance.get("analysis_eligible")
                or appearance.get("review_status") != "approved"
                or appearance.get("scope_status") != "in_scope"
                or round_item.get("status") != "held"
                or round_item.get("verification_status") == "unverified"
            ):
                report.error(
                    f"{label}: appearance_id {appearance_id} is not an eligible, "
                    "reviewed appearance from a verified held round"
                )
    generated = bundle["generated"].get("questions", [])
    if not isinstance(generated, list):
        report.error("question-bank.generated: questions must be an array")
        generated = []
    seen_generated_ids: set[str] = set()
    for index, question in enumerate(generated):
        label = f"question-bank.generated[{index}]"
        if not isinstance(question, dict):
            continue
        if question.get("origin_type") != "generated":
            report.error(f"{label}: origin_type must be generated")
        question_id = question.get("question_id")
        if not isinstance(question_id, str) or not question_id:
            report.error(f"{label}: invalid question_id")
        elif question_id in seen_generated_ids:
            report.error(f"{label}: duplicate generated question_id {question_id}")
        else:
            seen_generated_ids.add(question_id)
        if isinstance(question_id, str) and question_id in seen_question_ids:
            report.error(f"{label}: question_id collides with an observed question")
        choices = question.get("choices", [])
        answer = question.get("answer")
        if (
            isinstance(answer, int)
            and not isinstance(answer, bool)
            and isinstance(choices, list)
            and answer > len(choices)
        ):
            report.error(f"{label}: answer exceeds choices")
        for topic_code in question.get("topic_codes", []):
            if not isinstance(topic_code, str) or topic_code not in topics:
                report.error(f"{label}: unknown topic code {topic_code}")
        if not _valid_timestamp(question.get("created_at")):
            report.error(f"{label}: created_at must be an ISO timestamp with offset")
        choice_explanations = question.get("choice_explanations", {})
        if isinstance(choices, list) and isinstance(choice_explanations, dict):
            for key in choice_explanations:
                if isinstance(key, str) and key.isdigit() and int(key) > len(choices):
                    report.error(f"{label}: choice explanation {key} exceeds choices")

    if not groups:
        report.warn(f"{course_id}: question bank has no observed questions yet")
    if not any(
        variant.get("content_mode") == "full"
        and isinstance(variant.get("source_id"), str)
        and source_by_id.get(variant["source_id"], {}).get("rights", {}).get("status")
        == "public_fulltext"
        for variant in variants
        if isinstance(variant, dict)
    ):
        report.warn(f"{course_id}: no rights-cleared public full-text questions; practice will be empty")
    return report


def validate_public_dataset(course_id: str, dataset: dict[str, Any]) -> QuestionBankReport:
    """Fail closed if a restricted variant leaks into a public browser artifact."""
    report = QuestionBankReport()
    _validate_against_schema(
        report,
        dataset,
        "question-bank-public.schema.json",
        "question-bank.public",
    )
    required = {
        "schema_version", "course_id", "title", "generated_at", "dataset_version",
        "summary", "topics", "questions",
    }
    _required(report, dataset, required, "question-bank.public")
    if dataset.get("schema_version") != 1:
        report.error("question-bank.public: schema_version must be 1")
    if dataset.get("course_id") != course_id:
        report.error("question-bank.public: course_id mismatch")
    generated_at = dataset.get("generated_at")
    if not isinstance(generated_at, str):
        report.error("question-bank.public: generated_at must be an ISO timestamp")
    else:
        try:
            datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            report.error("question-bank.public: generated_at must be an ISO timestamp")
    dataset_version = dataset.get("dataset_version")
    if (
        not isinstance(dataset_version, str)
        or len(dataset_version) != 64
        or any(character not in "0123456789abcdef" for character in dataset_version)
    ):
        report.error("question-bank.public: dataset_version must be a SHA-256 digest")
    else:
        version_input = {
            key: value
            for key, value in dataset.items()
            if key not in {"dataset_version", "generated_at"}
        }
        if dataset_version != stable_json_hash(version_input):
            report.error("question-bank.public: dataset_version does not match content")
    if not isinstance(dataset.get("topics"), list):
        report.error("question-bank.public: topics must be an array")
    questions = dataset.get("questions")
    if not isinstance(questions, list):
        report.error("question-bank.public: questions must be an array")
        questions = []
    privacy = dataset.get("privacy")
    if not isinstance(privacy, dict):
        report.error("question-bank.public: privacy metadata is required")
    elif (
        privacy.get("scope") != "public"
        or privacy.get("contains_private_content") is not False
    ):
        report.error("question-bank.public: privacy metadata must declare a public, non-private export")
    for index, question in enumerate(questions):
        label = f"question-bank.public.questions[{index}]"
        if not isinstance(question, dict):
            report.error(f"{label}: must be an object")
            continue
        mode = question.get("content_mode")
        if mode != "full" and (
            question.get("question_text") is not None or question.get("choices")
        ):
            report.error(f"{label}: restricted content leaked into public dataset")
        if mode == "full" and question.get("rights_status") != "public_fulltext":
            report.error(f"{label}: full text lacks public_fulltext rights")
        if question.get("rights_status") in {"private_only", "blocked"}:
            report.error(f"{label}: restricted rights status leaked into public dataset")
        for source_index, source in enumerate(question.get("source_links", [])):
            if not isinstance(source, dict):
                report.error(f"{label}.source_links[{source_index}]: must be an object")
            elif source.get("rights_status") in {"private_only", "blocked"}:
                report.error(
                    f"{label}.source_links[{source_index}]: restricted source leaked"
                )
        if question.get("practice_eligible") and (
            mode != "full"
            or question.get("accepted_answer") is None
            or question.get("answer_status") not in ANALYSIS_ANSWER_STATUSES
        ):
            report.error(f"{label}: invalid practice eligibility")
    return report
