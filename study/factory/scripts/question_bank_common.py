"""Shared helpers for the rights-aware certification question bank."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterator

from common import STUDY_ROOT, course_dir, iter_lessons, load_curriculum, load_json


QUESTION_BANK_ROOT = STUDY_ROOT / "question-bank"
QUESTION_BANK_FILES = {
    "sources": "sources.json",
    "rounds": "rounds.json",
    "groups": "question-groups.json",
    "variants": "question-variants.json",
    "annotations": "annotations.json",
    "analysis_sets": "analysis-sets.json",
    "generated": "generated_questions.json",
}
QUESTION_BANK_COLLECTION_KEYS = {
    "sources": "sources",
    "rounds": "rounds",
    "groups": "groups",
    "variants": "variants",
    "annotations": "annotations",
    "analysis_sets": "analysis_sets",
    "generated": "questions",
}
QUESTION_BANK_RECORD_KEYS = {
    "sources": "source_id",
    "rounds": "round_id",
    "groups": "question_id",
    "variants": "variant_id",
    "annotations": "annotation_id",
    "analysis_sets": "analysis_set_id",
    "generated": "question_id",
}


def question_bank_dir(course_id: str) -> Path:
    return QUESTION_BANK_ROOT / course_id


def question_bank_path(course_id: str, kind: str) -> Path:
    try:
        filename = QUESTION_BANK_FILES[kind]
    except KeyError as exc:
        raise KeyError(f"unknown question-bank file kind: {kind}") from exc
    return question_bank_dir(course_id) / filename


def question_bank_reports_dir(course_id: str) -> Path:
    return question_bank_dir(course_id) / "reports"


def question_bank_build_dir(course_id: str) -> Path:
    return question_bank_dir(course_id) / "build"


def question_bank_web_dir(course_id: str) -> Path:
    return course_dir(course_id) / "questions"


def question_bank_public_data_path(course_id: str) -> Path:
    return question_bank_web_dir(course_id) / "data" / "questions.public.json"


def question_bank_local_data_path(course_id: str) -> Path:
    return question_bank_web_dir(course_id) / "data" / "questions.local.json"


def question_bank_url(course_id: str) -> str:
    return f"/study/courses/{course_id}/questions/"


def _ordered_union(left: list[Any], right: list[Any]) -> list[Any]:
    """Combine scalar lists without changing the canonical order."""
    result = list(left)
    for item in right:
        if item not in result:
            result.append(item)
    return result


def _merge_appearance(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = {**base, **overlay}
    for field_name in ("variant_ids", "topic_codes"):
        if field_name in overlay:
            merged[field_name] = _ordered_union(
                base.get(field_name, []), overlay.get(field_name, [])
            )
    return merged


def _merge_group(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = {**base, **overlay}
    if "appearances" not in overlay:
        return merged
    base_appearances = base.get("appearances", [])
    overlay_appearances = overlay.get("appearances", [])
    if not isinstance(base_appearances, list) or not isinstance(overlay_appearances, list):
        # The validator will report the malformed final record with its normal label.
        return merged
    by_id = {
        item.get("appearance_id"): item
        for item in base_appearances
        if isinstance(item, dict) and item.get("appearance_id")
    }
    result = list(base_appearances)
    positions = {
        item.get("appearance_id"): index
        for index, item in enumerate(result)
        if isinstance(item, dict) and item.get("appearance_id")
    }
    for item in overlay_appearances:
        appearance_id = item.get("appearance_id") if isinstance(item, dict) else None
        if appearance_id in by_id:
            result[positions[appearance_id]] = _merge_appearance(
                by_id[appearance_id], item
            )
        else:
            result.append(item)
    merged["appearances"] = result
    return merged


def merge_question_bank_overlay(
    kind: str,
    base_items: list[Any],
    overlay_items: list[Any],
) -> list[Any]:
    """Key-merge a private partial overlay into one canonical collection."""
    key_name = QUESTION_BANK_RECORD_KEYS[kind]
    result = list(base_items)
    positions = {
        item.get(key_name): index
        for index, item in enumerate(result)
        if isinstance(item, dict) and item.get(key_name)
    }
    for overlay in overlay_items:
        record_id = overlay.get(key_name) if isinstance(overlay, dict) else None
        if record_id not in positions:
            result.append(overlay)
            if record_id:
                positions[record_id] = len(result) - 1
            continue
        base = result[positions[record_id]]
        if not isinstance(base, dict) or not isinstance(overlay, dict):
            result[positions[record_id]] = overlay
            continue
        if kind == "groups":
            merged = _merge_group(base, overlay)
        else:
            merged = {**base, **overlay}
            union_fields = {
                "rounds": ("source_ids",),
                "annotations": ("keywords",),
                "analysis_sets": ("included_appearance_ids",),
                "generated": ("topic_codes", "keywords"),
            }.get(kind, ())
            for field_name in union_fields:
                if field_name in overlay:
                    merged[field_name] = _ordered_union(
                        base.get(field_name, []), overlay.get(field_name, [])
                    )
            if kind in {"annotations", "generated"} and "choice_explanations" in overlay:
                merged["choice_explanations"] = {
                    **base.get("choice_explanations", {}),
                    **overlay.get("choice_explanations", {}),
                }
        result[positions[record_id]] = merged
    return result


def load_question_bank(
    course_id: str,
    *,
    include_private: bool = False,
) -> dict[str, dict[str, Any]]:
    """Load canonical documents and, when requested, ignored private overlays."""
    bundle = {
        kind: load_json(question_bank_path(course_id, kind))
        for kind in QUESTION_BANK_FILES
    }
    if not include_private:
        return bundle
    private_dir = question_bank_dir(course_id) / "private"
    for kind, filename in QUESTION_BANK_FILES.items():
        overlay_path = private_dir / filename
        if not overlay_path.exists():
            continue
        overlay = load_json(overlay_path)
        if overlay.get("schema_version") != 1:
            raise ValueError(f"{overlay_path}: schema_version must be 1")
        if overlay.get("course_id") != course_id:
            raise ValueError(f"{overlay_path}: course_id mismatch")
        collection_key = QUESTION_BANK_COLLECTION_KEYS[kind]
        additions = overlay.get(collection_key)
        if not isinstance(additions, list):
            raise ValueError(f"{overlay_path}: {collection_key} must be an array")
        base_items = bundle[kind].get(collection_key)
        if not isinstance(base_items, list):
            raise ValueError(
                f"{question_bank_path(course_id, kind)}: {collection_key} must be an array"
            )
        bundle[kind] = {
            **bundle[kind],
            collection_key: merge_question_bank_overlay(
                kind, base_items, additions
            ),
        }
    return bundle


def curriculum_topic_map(course_id: str) -> dict[str, dict[str, Any]]:
    return {
        lesson["id"]: lesson
        for lesson in iter_lessons(load_curriculum(course_id))
    }


def flatten_appearances(groups: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for group in groups:
        for appearance in group.get("appearances", []):
            yield {
                **appearance,
                "question_id": group.get("question_id"),
                "origin_type": group.get("origin_type"),
                "duplicate_group": group.get("duplicate_group"),
            }


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_question_text(value: str | None) -> str:
    """Normalize copied formatting without trying to reconstruct missing wording."""
    if not value:
        return ""
    normalized = value.casefold()
    normalized = re.sub(r"^\s*(?:문\s*)?\d+\s*[.)번:]\s*", "", normalized)
    normalized = re.sub(r"[①②③④⑤⑥⑦⑧⑨⑩]", "", normalized)
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", normalized)
    return normalized


def fuzzy_duplicate_pairs(
    variants: list[dict[str, Any]],
    *,
    threshold: float = 0.92,
) -> list[tuple[str, str, float]]:
    """Return unresolved near-duplicates, excluding already-grouped evidence."""
    normalized: list[tuple[dict[str, Any], str]] = []
    for variant in variants:
        candidate = variant.get("question_text") or variant.get("concept_summary")
        value = normalize_question_text(candidate)
        if len(value) >= 8:
            normalized.append((variant, value))
    pairs: list[tuple[str, str, float]] = []
    for left_index, (left_item, left_text) in enumerate(normalized):
        for right_item, right_text in normalized[left_index + 1:]:
            if (
                left_item.get("question_id") == right_item.get("question_id")
                or left_item.get("appearance_id") == right_item.get("appearance_id")
            ):
                continue
            ratio = SequenceMatcher(None, left_text, right_text).ratio()
            if ratio >= threshold:
                pairs.append(
                    (left_item["variant_id"], right_item["variant_id"], ratio)
                )
    return pairs


def question_content_hash(question_text: str | None, choices: list[Any]) -> str | None:
    normalized = normalize_question_text(question_text)
    normalized_choices = [normalize_question_text(str(choice)) for choice in choices]
    if not normalized:
        return None
    return stable_json_hash({"question": normalized, "choices": normalized_choices})
