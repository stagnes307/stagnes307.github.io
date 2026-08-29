#!/usr/bin/env python3
"""Build the rights-aware question bank, reports, SQLite, and static UI."""

from __future__ import annotations

import argparse
import html
import json
import os
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from build_course import build_course
from build_lesson import build_lesson, question_bank_summary
from common import (
    iter_lessons,
    lesson_dir,
    load_curriculum,
    load_json,
    now_kst,
    render_template,
    write_json,
)
from question_bank_common import (
    flatten_appearances,
    fuzzy_duplicate_pairs,
    load_question_bank,
    question_bank_build_dir,
    question_bank_local_data_path,
    question_bank_public_data_path,
    question_bank_reports_dir,
    question_bank_url,
    question_bank_web_dir,
    stable_json_hash,
)
from question_bank_validation import (
    ANALYSIS_ANSWER_STATUSES,
    validate_public_dataset,
    validate_question_bank_data,
)


EVIDENCE_ROUND_COVERAGE = 0.50
SUFFICIENT_MEDIAN_COVERAGE = 0.75
RECENT_ROUND_COUNT = 3


def _index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {item[key]: item for item in items}


def _variant_is_visible(
    variant: dict[str, Any],
    source_by_id: dict[str, dict[str, Any]],
    *,
    include_private: bool,
) -> bool:
    rights_status = source_by_id.get(variant.get("source_id"), {}).get(
        "rights", {}
    ).get("status")
    return rights_status in {"public_fulltext", "link_only"} or (
        include_private and rights_status == "private_only"
    )


def _visible_registry_sources(
    sources: list[dict[str, Any]],
    *,
    include_private: bool,
) -> list[dict[str, Any]]:
    if include_private:
        return sources
    return [
        source
        for source in sources
        if source.get("rights", {}).get("status") != "private_only"
    ]


def _visible_rounds(
    rounds: list[dict[str, Any]],
    visible_source_ids: set[str],
) -> list[dict[str, Any]]:
    return [
        item
        for item in rounds
        if any(source_id in visible_source_ids for source_id in item.get("source_ids", []))
    ]


def _approved_annotation(
    annotations: list[dict[str, Any]], appearance_id: str
) -> dict[str, Any] | None:
    return next(
        (
            item for item in annotations
            if item.get("appearance_id") == appearance_id
            and item.get("review_status") == "approved"
        ),
        None,
    )


def _answer_resolution(variants: list[dict[str, Any]]) -> tuple[int | None, str]:
    claims = {
        item.get("answer_claim")
        for item in variants
        if isinstance(item.get("answer_claim"), int)
    }
    statuses = {item.get("answer_status") for item in variants}
    if "conflicting" in statuses or len(claims) > 1:
        return None, "conflicting"
    if not claims:
        return None, "unverified"
    answer = next(iter(claims))
    for status in (
        "official_verified",
        "expert_reviewed",
        "multi_source_corroborated",
        "unverified",
    ):
        if status in statuses:
            return answer, status
    return answer, "unverified"


def _select_content_variant(
    variants: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    *,
    include_private: bool,
) -> dict[str, Any] | None:
    allowed_rights = {"public_fulltext"}
    if include_private:
        allowed_rights.add("private_only")
    candidates = [
        item for item in variants
        if item.get("content_mode") == "full"
        and source_by_id.get(item.get("source_id"), {})
        .get("rights", {})
        .get("status") in allowed_rights
        and item.get("review_status") == "approved"
    ]
    priority = {
        "official_verified": 0,
        "expert_reviewed": 1,
        "multi_source_corroborated": 2,
        "unverified": 3,
        "conflicting": 4,
    }
    candidates.sort(
        key=lambda item: (
            priority.get(item.get("answer_status"), 9),
            item.get("variant_id", ""),
        )
    )
    return candidates[0] if candidates else None


def _source_links(
    variants: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    *,
    include_private: bool,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for variant in variants:
        source = source_by_id.get(variant.get("source_id"), {})
        rights_status = source.get("rights", {}).get("status")
        if rights_status not in {"public_fulltext", "link_only"} and not (
            include_private and rights_status == "private_only"
        ):
            continue
        source_id = source.get("source_id")
        url = source.get("url")
        key = (str(source_id), str(variant.get("source_locator")))
        if not source_id or not url or key in seen:
            continue
        seen.add(key)
        links.append({
            "source_id": source_id,
            "title": source.get("title"),
            "provider": source.get("provider"),
            "url": url,
            "locator": variant.get("source_locator"),
            "reliability": source.get("reliability"),
            "rights_status": rights_status,
        })
    return links


def _round_coverage(
    appearances: list[dict[str, Any]],
    round_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    counts = Counter(
        item["round_id"]
        for item in appearances
        if item.get("analysis_eligible")
        and item.get("review_status") == "approved"
        and item.get("scope_status") == "in_scope"
    )
    result: dict[str, dict[str, Any]] = {}
    for round_id, round_item in round_by_id.items():
        expected = round_item.get("expected_questions")
        observed = counts.get(round_id, 0)
        coverage = observed / expected if isinstance(expected, int) and expected else None
        eligible = bool(
            round_item.get("status") == "held"
            and coverage is not None
            and coverage >= EVIDENCE_ROUND_COVERAGE
        )
        result[round_id] = {
            "round_id": round_id,
            "exam_round": round_item.get("exam_round"),
            "exam_date": round_item.get("exam_date"),
            "status": round_item.get("status"),
            "expected_questions": expected,
            "observed_questions": observed,
            "coverage": round(coverage, 4) if coverage is not None else None,
            "eligible_for_frequency": eligible,
        }
    return result


def _importance_label(score: float | None) -> tuple[int | None, str]:
    if score is None:
        return None, "근거 부족"
    if score >= 80:
        return 5, "매우 중요"
    if score >= 65:
        return 4, "중요"
    if score >= 50:
        return 3, "보통"
    if score >= 35:
        return 2, "낮음"
    return 1, "관측 낮음"


def analyze_topics(
    course_id: str,
    bundle: dict[str, dict[str, Any]],
    *,
    include_private: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    curriculum = load_curriculum(course_id)
    lessons = list(iter_lessons(curriculum))
    groups = bundle["groups"].get("groups", [])
    appearances = list(flatten_appearances(groups))
    all_rounds = bundle["rounds"].get("rounds", [])
    variants = bundle["variants"].get("variants", [])
    variant_by_id = _index_by(variants, "variant_id")
    sources = bundle["sources"].get("sources", [])
    source_by_id = _index_by(sources, "source_id")
    visible_sources = _visible_registry_sources(
        sources,
        include_private=include_private,
    )
    visible_source_ids = {item["source_id"] for item in visible_sources}
    rounds = _visible_rounds(all_rounds, visible_source_ids)
    round_by_id = _index_by(rounds, "round_id")
    visible_variant_ids = {
        variant["variant_id"]
        for variant in variants
        if _variant_is_visible(
            variant,
            source_by_id,
            include_private=include_private,
        )
    }
    appearances = [
        item
        for item in appearances
        if any(
            variant_id in visible_variant_ids
            for variant_id in item.get("variant_ids", [])
        )
    ]
    coverage_by_round = _round_coverage(appearances, round_by_id)

    approved = [
        item for item in appearances
        if item.get("analysis_eligible")
        and item.get("review_status") == "approved"
        and item.get("scope_status") == "in_scope"
        and round_by_id.get(item.get("round_id"), {}).get("status") == "held"
    ]
    eligible_round_ids = [
        round_id for round_id, item in coverage_by_round.items()
        if item["eligible_for_frequency"]
    ]
    eligible_round_ids.sort(
        key=lambda round_id: (
            round_by_id[round_id].get("exam_date") or "",
            round_by_id[round_id].get("exam_round") or 0,
        )
    )
    recent_round_ids = eligible_round_ids[-RECENT_ROUND_COUNT:]
    score_appearances = [
        item for item in approved if item.get("round_id") in eligible_round_ids
    ]
    count_by_topic = Counter(item.get("primary_topic_code") for item in score_appearances)
    max_topic_count = max(count_by_topic.values(), default=0)
    median_coverage = statistics.median(
        coverage_by_round[round_id]["coverage"] for round_id in eligible_round_ids
    ) if eligible_round_ids else 0.0
    if len(eligible_round_ids) < 3:
        overall_evidence = "limited"
    elif len(eligible_round_ids) >= 5 and median_coverage >= SUFFICIENT_MEDIAN_COVERAGE:
        overall_evidence = "sufficient"
    else:
        overall_evidence = "provisional"

    topic_rows: list[dict[str, Any]] = []
    for lesson in lessons:
        code = lesson["id"]
        all_for_topic = [item for item in approved if item.get("primary_topic_code") == code]
        scored_for_topic = [item for item in score_appearances if item.get("primary_topic_code") == code]
        rounds_with_topic = {item["round_id"] for item in scored_for_topic}
        recent_with_topic = rounds_with_topic & set(recent_round_ids)
        round_rate = len(rounds_with_topic) / len(eligible_round_ids) if eligible_round_ids else 0.0
        recent_rate = len(recent_with_topic) / len(recent_round_ids) if recent_round_ids else 0.0
        volume_norm = len(scored_for_topic) / max_topic_count if max_topic_count else 0.0
        score = None
        if overall_evidence != "limited":
            score = round(50 * round_rate + 30 * recent_rate + 20 * volume_norm, 1)
        stars, importance_label = _importance_label(score)
        source_ids = {
            variant_by_id[variant_id].get("source_id")
            for item in all_for_topic
            for variant_id in item.get("variant_ids", [])
            if variant_id in visible_variant_ids
        }
        public_question_count = sum(
            any(
                variant_by_id.get(variant_id, {}).get("content_mode") == "full"
                and source_by_id.get(
                    variant_by_id.get(variant_id, {}).get("source_id"), {}
                ).get("rights", {}).get("status") == "public_fulltext"
                for variant_id in item.get("variant_ids", [])
            )
            for item in all_for_topic
        )
        topic_rows.append({
            "code": code,
            "title": lesson["title"],
            "section_id": lesson["section_id"],
            "section_title": lesson["section_title"],
            "unit_id": lesson["unit_id"],
            "unit_title": lesson["unit_title"],
            "topics": lesson.get("topics", []),
            "observed_questions": len(all_for_topic),
            "distinct_rounds": len({item["round_id"] for item in all_for_topic}),
            "source_count": len(source_ids),
            "public_question_count": public_question_count,
            "eligible_question_count": len(scored_for_topic),
            "round_rate": round(round_rate, 4),
            "recent_round_rate": round(recent_rate, 4),
            "volume_normalized": round(volume_norm, 4),
            "evidence_level": overall_evidence,
            "importance_score": score,
            "stars": stars,
            "importance_label": importance_label,
        })

    topic_rows.sort(
        key=lambda item: (
            item["importance_score"] is None,
            -(item["importance_score"] or 0),
            -item["observed_questions"],
            item["code"],
        )
    )
    summary = {
        "observed_appearances": len(appearances),
        "analysis_eligible_appearances": len(approved),
        "frequency_included_appearances": len(score_appearances),
        "eligible_rounds": len(eligible_round_ids),
        "eligible_round_ids": eligible_round_ids,
        "recent_round_ids": recent_round_ids,
        "median_round_coverage": round(median_coverage, 4),
        "evidence_level": overall_evidence,
        "coverage_threshold": EVIDENCE_ROUND_COVERAGE,
        "sufficient_median_coverage": SUFFICIENT_MEDIAN_COVERAGE,
        "importance_formula": (
            "50×round_rate + 30×recent_3_round_rate + 20×normalized_volume"
        ),
    }
    coverage_rows = sorted(
        coverage_by_round.values(),
        key=lambda item: (item.get("exam_round") or 0),
    )
    return topic_rows, coverage_rows, summary


def build_browser_dataset(
    course_id: str,
    bundle: dict[str, dict[str, Any]],
    *,
    include_private: bool = False,
) -> dict[str, Any]:
    curriculum = load_curriculum(course_id)
    topic_rows, coverage_rows, analysis_summary = analyze_topics(
        course_id,
        bundle,
        include_private=include_private,
    )
    all_sources = bundle["sources"].get("sources", [])
    source_by_id = _index_by(all_sources, "source_id")
    sources = _visible_registry_sources(
        all_sources,
        include_private=include_private,
    )
    visible_source_ids = {item["source_id"] for item in sources}
    rounds = _visible_rounds(
        bundle["rounds"].get("rounds", []),
        visible_source_ids,
    )
    round_by_id = _index_by(rounds, "round_id")
    variants = bundle["variants"].get("variants", [])
    variant_by_id = _index_by(variants, "variant_id")
    annotations = bundle["annotations"].get("annotations", [])
    questions: list[dict[str, Any]] = []

    for appearance in flatten_appearances(bundle["groups"].get("groups", [])):
        if appearance.get("review_status") != "approved":
            continue
        all_appearance_variants = [
            variant_by_id[variant_id]
            for variant_id in appearance.get("variant_ids", [])
            if variant_id in variant_by_id
        ]
        appearance_variants = [
            variant
            for variant in all_appearance_variants
            if _variant_is_visible(
                variant,
                source_by_id,
                include_private=include_private,
            )
        ]
        if not appearance_variants:
            continue
        selected = _select_content_variant(
            appearance_variants,
            source_by_id,
            include_private=include_private,
        )
        annotation = _approved_annotation(annotations, appearance["appearance_id"])
        accepted_answer, answer_status = _answer_resolution(appearance_variants)
        source_links = _source_links(
            appearance_variants,
            source_by_id,
            include_private=include_private,
        )
        round_item = round_by_id.get(appearance.get("round_id"), {})
        concept_summary = (
            (annotation or {}).get("concept_summary")
            or next(
                (
                    variant.get("concept_summary")
                    for variant in appearance_variants
                    if variant.get("concept_summary")
                ),
                "",
            )
        )
        rights_status = (
            source_by_id.get(selected.get("source_id"), {}).get("rights", {}).get("status")
            if selected else "link_only"
        )
        practice_eligible = bool(
            selected
            and accepted_answer is not None
            and answer_status in ANALYSIS_ANSWER_STATUSES
            and (annotation is None or annotation.get("review_status") == "approved")
        )
        questions.append({
            "question_id": appearance["question_id"],
            "appearance_id": appearance["appearance_id"],
            "exam_round": round_item.get("exam_round"),
            "exam_year": int(round_item["exam_date"][:4]) if round_item.get("exam_date") else None,
            "exam_date": round_item.get("exam_date"),
            "question_number": appearance.get("question_number"),
            "origin_type": appearance.get("origin_type"),
            "content_mode": "full" if selected else "link_only",
            "rights_status": rights_status,
            "question_text": selected.get("question_text") if selected else None,
            "choices": selected.get("choices", []) if selected else [],
            "accepted_answer": accepted_answer if selected else None,
            "answer_status": answer_status,
            "primary_topic_code": appearance.get("primary_topic_code"),
            "topic_codes": appearance.get("topic_codes", []),
            "keywords": (annotation or {}).get("keywords", []),
            "concept_summary": concept_summary,
            "difficulty": (annotation or {}).get("difficulty"),
            "explanation": (
                (annotation or {}).get("explanation")
                if practice_eligible else None
            ),
            "choice_explanations": (
                (annotation or {}).get("choice_explanations", {})
                if practice_eligible else {}
            ),
            "source_links": source_links,
            "scope_status": appearance.get("scope_status"),
            "analysis_eligible": appearance.get("analysis_eligible"),
            "practice_eligible": practice_eligible,
            "content_hash": selected.get("content_hash") if selected else None,
        })

    questions.sort(
        key=lambda item: (
            item.get("exam_round") or 0,
            item.get("question_number") or 999,
            item["appearance_id"],
        )
    )
    summary = {
        **analysis_summary,
        "source_count": len(sources),
        "held_round_count": sum(item.get("status") == "held" for item in rounds),
        "published_records": len(questions),
        "public_fulltext_questions": sum(
            item["content_mode"] == "full" and item["rights_status"] == "public_fulltext"
            for item in questions
        ),
        "practice_questions": sum(item["practice_eligible"] for item in questions),
    }
    referenced_source_ids = sorted({
        link["source_id"]
        for item in questions
        for link in item.get("source_links", [])
    })
    base = {
        "schema_version": 1,
        "course_id": course_id,
        "title": f"{curriculum['title']} 기출·출제분석",
        "target_curriculum": {
            "version_id": curriculum.get("curriculum_version_id"),
            "effective_from": curriculum.get("effective_from"),
            "effective_to": curriculum.get("effective_to"),
            # Hash the parsed document so dataset versions stay identical across
            # Windows (CRLF) and Linux (LF) checkouts.
            "sha256": stable_json_hash(curriculum),
        },
        "summary": summary,
        "coverage": coverage_rows,
        "topics": topic_rows,
        "questions": questions,
        "filters": {
            "rounds": [
                {
                    "round_id": item["round_id"],
                    "exam_round": item["exam_round"],
                    "exam_date": item.get("exam_date"),
                    "status": item["status"],
                }
                for item in rounds
            ],
            "answer_statuses": sorted({item["answer_status"] for item in questions}),
            "content_modes": sorted({item["content_mode"] for item in questions}),
            "sources": [
                {
                    "source_id": source_id,
                    "title": source_by_id[source_id].get("title") or source_id,
                    "provider": source_by_id[source_id].get("provider") or "",
                }
                for source_id in referenced_source_ids
                if source_id in source_by_id
            ],
        },
        "privacy": {
            "scope": "local" if include_private else "public",
            "contains_private_content": include_private and any(
                item.get("rights", {}).get("status") == "private_only"
                for item in all_sources
            ),
        },
    }
    version = stable_json_hash(base)
    return {**base, "dataset_version": version}


def _preserved_generated_at(path: Path, version: str) -> str:
    if path.exists():
        try:
            previous = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            previous = {}
        if previous.get("dataset_version") == version and isinstance(previous.get("generated_at"), str):
            return previous["generated_at"]
    return now_kst()


def _with_generated_at(dataset: dict[str, Any], path: Path) -> dict[str, Any]:
    return {
        **dataset,
        "generated_at": _preserved_generated_at(path, dataset["dataset_version"]),
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def build_reports(
    course_id: str,
    bundle: dict[str, dict[str, Any]],
    dataset: dict[str, Any],
) -> dict[str, str]:
    groups = bundle["groups"].get("groups", [])
    variants = bundle["variants"].get("variants", [])
    sources = bundle["sources"].get("sources", [])
    appearances = list(flatten_appearances(groups))
    report_header = (
        f"> dataset `{dataset['dataset_version'][:12]}` · 생성 {dataset['generated_at']} · "
        "관측 자료이며 공식 출제확률이 아닙니다.\n\n"
    )

    coverage_rows = [
        [
            item["exam_round"],
            item.get("exam_date") or "미상",
            item["observed_questions"],
            item.get("expected_questions") or "미상",
            f"{item['coverage'] * 100:.1f}%" if item.get("coverage") is not None else "미상",
            "포함" if item["eligible_for_frequency"] else "제외",
        ]
        for item in dataset.get("coverage", [])
        if item.get("status") == "held"
    ]
    coverage = (
        "# 기출 Coverage\n\n" + report_header
        + f"- 등록 출처: {len(sources)}\n"
        + f"- 문제군: {len(groups)}\n"
        + f"- 관측 appearance: {len(appearances)}\n"
        + f"- 검토 승인 분석 후보: {dataset['summary']['analysis_eligible_appearances']}\n"
        + f"- 빈도·중요도 포함 appearance: {dataset['summary']['frequency_included_appearances']}\n"
        + f"- 빈도 분모 적격 회차: {dataset['summary']['eligible_rounds']}\n\n"
        + _markdown_table(
            ["회차", "시험일", "관측", "예상", "coverage", "빈도 분모"],
            coverage_rows,
        )
        + "\n"
    )

    topic_rows = [
        [
            item["code"], item["title"], item["observed_questions"],
            item["distinct_rounds"],
            item["importance_score"] if item["importance_score"] is not None else "근거 부족",
            item["evidence_level"],
        ]
        for item in dataset.get("topics", [])
        if item["observed_questions"] or item["importance_score"] is not None
    ]
    frequency = (
        "# 세부항목별 관측 빈도\n\n" + report_header
        + f"계산식: `{dataset['summary']['importance_formula']}`\n\n"
        + _markdown_table(
            ["코드", "항목", "관측 문항", "출제 회차", "중요도", "근거"],
            topic_rows,
        )
        + "\n"
    )

    unresolved_rows: list[list[Any]] = []
    for appearance in appearances:
        reasons = []
        if appearance.get("review_status") != "approved":
            reasons.append("분류 검토")
        if appearance.get("scope_status") == "uncertain":
            reasons.append("현행범위 검토")
        if not appearance.get("analysis_eligible"):
            reasons.append("분석 제외")
        if reasons:
            unresolved_rows.append([
                appearance.get("appearance_id"),
                appearance.get("round_id"),
                ", ".join(reasons),
            ])
    unresolved = (
        "# 검토 필요 항목\n\n" + report_header
        + (_markdown_table(["appearance", "회차", "사유"], unresolved_rows)
           if unresolved_rows else "검토 필요 항목이 없습니다.")
        + "\n"
    )

    duplicate_rows = [
        [left_id, right_id, f"{ratio:.3f}", "검토 필요"]
        for left_id, right_id, ratio in fuzzy_duplicate_pairs(variants)
    ]
    duplicates = (
        "# 중복 후보\n\n" + report_header
        + "정확 일치는 동일 문항 후보가 되며, 유사 일치는 자동 병합하지 않습니다.\n\n"
        + (_markdown_table(["variant A", "variant B", "유사도", "처리"], duplicate_rows)
           if duplicate_rows else "발견된 유사 후보가 없습니다.")
        + "\n"
    )

    conflict_rows: list[list[Any]] = []
    variants_by_appearance: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for variant in variants:
        variants_by_appearance[variant["appearance_id"]].append(variant)
    for appearance_id, items in variants_by_appearance.items():
        answer, status = _answer_resolution(items)
        if status in {"conflicting", "unverified"}:
            claims = sorted({str(item.get("answer_claim")) for item in items})
            conflict_rows.append([appearance_id, status, ", ".join(claims), answer or "-"])
    answer_conflicts = (
        "# 정답 검증 상태\n\n" + report_header
        + (_markdown_table(["appearance", "상태", "출처 주장", "채택 답"], conflict_rows)
           if conflict_rows else "정답 충돌 또는 미검증 항목이 없습니다.")
        + "\n"
    )

    rights_rows = [
        [
            item["source_id"], item["provider"], item["source_type"],
            item["reliability"], item["rights"]["status"], item["url"],
        ]
        for item in sources
    ]
    rights = (
        "# 출처 및 이용범위\n\n" + report_header
        + _markdown_table(
            ["ID", "제공자", "유형", "신뢰도", "저장 범위", "URL"],
            rights_rows,
        )
        + "\n\n`link_only`와 `private_only` 원문은 공개 데이터에 포함하지 않습니다.\n"
    )
    eligible_round_ids = set(dataset["summary"].get("eligible_round_ids", []))
    analysis_candidates = [
        item["appearance_id"]
        for item in appearances
        if item.get("analysis_eligible")
        and item.get("review_status") == "approved"
        and item.get("scope_status") == "in_scope"
    ]
    analysis_set = json.dumps(
        {
            "schema_version": 1,
            "course_id": course_id,
            "analysis_set_id": f"frequency-{dataset['dataset_version'][:16]}",
            "dataset_version": dataset["dataset_version"],
            "generated_at": dataset["generated_at"],
            "curriculum": dataset["target_curriculum"],
            "inclusion": {
                "appearance_review_status": "approved",
                "scope_status": "in_scope",
                "round_status": "held",
                "round_coverage_minimum": EVIDENCE_ROUND_COVERAGE,
                "secondary_topics_affect_score": False,
            },
            "candidate_appearance_ids": sorted(analysis_candidates),
            "included_appearance_ids": sorted(
                item["appearance_id"]
                for item in appearances
                if item["appearance_id"] in analysis_candidates
                and item.get("round_id") in eligible_round_ids
            ),
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    return {
        "coverage.md": coverage,
        "frequency.md": frequency,
        "unresolved.md": unresolved,
        "duplicates.md": duplicates,
        "answer-conflicts.md": answer_conflicts,
        "rights.md": rights,
        "analysis-set.json": analysis_set,
    }


def write_sqlite(
    course_id: str,
    bundle: dict[str, dict[str, Any]],
    dataset: dict[str, Any],
) -> Path:
    output = question_bank_build_dir(course_id) / "questions.sqlite"
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".sqlite.tmp")
    if temp.exists():
        temp.unlink()
    connection = sqlite3.connect(temp)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE sources (
                source_id TEXT PRIMARY KEY, title TEXT NOT NULL, provider TEXT NOT NULL,
                url TEXT NOT NULL, source_type TEXT NOT NULL, reliability TEXT NOT NULL,
                rights_status TEXT NOT NULL, accessed_at TEXT NOT NULL
            );
            CREATE TABLE rounds (
                round_id TEXT PRIMARY KEY, exam_round INTEGER NOT NULL, exam_date TEXT,
                status TEXT NOT NULL, expected_questions INTEGER, verification_status TEXT NOT NULL
            );
            CREATE TABLE question_groups (
                question_id TEXT PRIMARY KEY, origin_type TEXT NOT NULL, duplicate_group TEXT
            );
            CREATE TABLE appearances (
                appearance_id TEXT PRIMARY KEY, question_id TEXT NOT NULL,
                round_id TEXT NOT NULL, question_number INTEGER, primary_topic_code TEXT NOT NULL,
                scope_status TEXT NOT NULL, review_status TEXT NOT NULL,
                analysis_eligible INTEGER NOT NULL,
                FOREIGN KEY(question_id) REFERENCES question_groups(question_id),
                FOREIGN KEY(round_id) REFERENCES rounds(round_id)
            );
            CREATE TABLE topic_mappings (
                appearance_id TEXT NOT NULL, topic_code TEXT NOT NULL, is_primary INTEGER NOT NULL,
                PRIMARY KEY(appearance_id, topic_code),
                FOREIGN KEY(appearance_id) REFERENCES appearances(appearance_id)
            );
            CREATE TABLE variants (
                variant_id TEXT PRIMARY KEY, question_id TEXT NOT NULL, appearance_id TEXT NOT NULL,
                source_id TEXT NOT NULL, content_mode TEXT NOT NULL, question_text TEXT,
                choices_json TEXT NOT NULL, answer_claim INTEGER, answer_status TEXT NOT NULL,
                concept_summary TEXT NOT NULL, source_locator TEXT NOT NULL,
                content_hash TEXT, review_status TEXT NOT NULL,
                FOREIGN KEY(question_id) REFERENCES question_groups(question_id),
                FOREIGN KEY(appearance_id) REFERENCES appearances(appearance_id),
                FOREIGN KEY(source_id) REFERENCES sources(source_id)
            );
            CREATE TABLE annotations (
                annotation_id TEXT PRIMARY KEY, question_id TEXT NOT NULL,
                appearance_id TEXT NOT NULL, keywords_json TEXT NOT NULL,
                concept_summary TEXT NOT NULL, difficulty TEXT, explanation TEXT,
                choice_explanations_json TEXT NOT NULL, producer TEXT NOT NULL,
                created_at TEXT NOT NULL, review_status TEXT NOT NULL,
                FOREIGN KEY(question_id) REFERENCES question_groups(question_id),
                FOREIGN KEY(appearance_id) REFERENCES appearances(appearance_id)
            );
            CREATE INDEX appearances_topic_idx ON appearances(primary_topic_code);
            CREATE INDEX appearances_round_idx ON appearances(round_id);
            CREATE INDEX variants_source_idx ON variants(source_id);
            """
        )
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("course_id", course_id),
                ("dataset_version", dataset["dataset_version"]),
                ("generated_at", dataset["generated_at"]),
            ],
        )
        connection.executemany(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["source_id"], item["title"], item["provider"], item["url"],
                    item["source_type"], item["reliability"], item["rights"]["status"],
                    item["accessed_at"],
                )
                for item in bundle["sources"].get("sources", [])
            ],
        )
        connection.executemany(
            "INSERT INTO rounds VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    item["round_id"], item["exam_round"], item.get("exam_date"),
                    item["status"], item.get("expected_questions"), item["verification_status"],
                )
                for item in bundle["rounds"].get("rounds", [])
            ],
        )
        groups = bundle["groups"].get("groups", [])
        connection.executemany(
            "INSERT INTO question_groups VALUES (?, ?, ?)",
            [
                (item["question_id"], item["origin_type"], item.get("duplicate_group"))
                for item in groups
            ],
        )
        appearances = list(flatten_appearances(groups))
        connection.executemany(
            "INSERT INTO appearances VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["appearance_id"], item["question_id"], item["round_id"],
                    item.get("question_number"), item["primary_topic_code"],
                    item["scope_status"], item["review_status"],
                    int(item["analysis_eligible"]),
                )
                for item in appearances
            ],
        )
        connection.executemany(
            "INSERT INTO topic_mappings VALUES (?, ?, ?)",
            [
                (item["appearance_id"], topic_code, int(topic_code == item["primary_topic_code"]))
                for item in appearances
                for topic_code in item.get("topic_codes", [])
            ],
        )
        connection.executemany(
            "INSERT INTO variants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["variant_id"], item["question_id"], item["appearance_id"],
                    item["source_id"], item["content_mode"], item.get("question_text"),
                    json.dumps(item.get("choices", []), ensure_ascii=False),
                    item.get("answer_claim"), item["answer_status"], item["concept_summary"],
                    item["source_locator"], item.get("content_hash"), item["review_status"],
                )
                for item in bundle["variants"].get("variants", [])
            ],
        )
        connection.executemany(
            "INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["annotation_id"], item["question_id"], item["appearance_id"],
                    json.dumps(item.get("keywords", []), ensure_ascii=False),
                    item["concept_summary"], item.get("difficulty"), item.get("explanation"),
                    json.dumps(item.get("choice_explanations", {}), ensure_ascii=False),
                    item["producer"], item["created_at"], item["review_status"],
                )
                for item in bundle["annotations"].get("annotations", [])
            ],
        )
        connection.commit()
    finally:
        connection.close()
    os.replace(temp, output)
    return output


def render_question_bank_page(course_id: str) -> Path:
    curriculum = load_curriculum(course_id)
    output = question_bank_web_dir(course_id) / "index.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_question_bank_page_html(course_id), encoding="utf-8", newline="\n")
    return output


def _question_bank_page_html(course_id: str) -> str:
    curriculum = load_curriculum(course_id)
    return render_template(
        "question-bank.html",
        {
            "PAGE_TITLE": html.escape(f"{curriculum['title']} 기출·출제분석"),
            "COURSE_TITLE": html.escape(curriculum["title"]),
            "COURSE_URL": f"/study/courses/{course_id}/",
        },
    )


def _write_outputs(
    course_id: str,
    bundle: dict[str, dict[str, Any]],
    *,
    integrate_lessons: bool,
) -> dict[str, Path]:
    public_path = question_bank_public_data_path(course_id)
    public = _with_generated_at(
        build_browser_dataset(course_id, bundle, include_private=False),
        public_path,
    )
    public_validation = validate_public_dataset(course_id, public)
    if public_validation.errors:
        raise ValueError("; ".join(public_validation.errors))
    write_json(public_path, public)

    local_bundle = load_question_bank(course_id, include_private=True)
    local = build_browser_dataset(course_id, local_bundle, include_private=True)
    local_path = question_bank_local_data_path(course_id)
    if local["privacy"]["contains_private_content"]:
        local = _with_generated_at(local, local_path)
        write_json(local_path, local)
        sqlite_dataset = local
    else:
        if local_path.exists():
            local_path.unlink()
        sqlite_dataset = public

    reports = build_reports(course_id, bundle, public)
    reports_dir = question_bank_reports_dir(course_id)
    reports_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in reports.items():
        (reports_dir / filename).write_text(content, encoding="utf-8", newline="\n")
    sqlite_path = write_sqlite(course_id, local_bundle, sqlite_dataset)
    page_path = render_question_bank_page(course_id)

    if integrate_lessons:
        build_course(course_id, sync_catalog_entry=False)
        for lesson in iter_lessons(load_curriculum(course_id)):
            build_lesson(course_id, lesson["id"])
    return {
        "public_json": public_path,
        "sqlite": sqlite_path,
        "page": page_path,
        "reports": reports_dir,
    }


def _check_outputs(course_id: str, bundle: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    path = question_bank_public_data_path(course_id)
    if not path.exists():
        return [f"missing generated public dataset: {path}"]
    try:
        current = load_json(path)
    except Exception as exc:
        return [f"cannot read public dataset: {exc}"]
    expected = build_browser_dataset(course_id, bundle, include_private=False)
    current_without_timestamp = {
        key: value for key, value in current.items() if key != "generated_at"
    }
    if current_without_timestamp != expected:
        errors.append("public dataset is stale; run build_question_bank.py")
    public_report = validate_public_dataset(course_id, current)
    errors.extend(public_report.errors)
    report_dataset = {
        **expected,
        "generated_at": current.get("generated_at", "invalid-generated-at"),
    }
    expected_reports = build_reports(course_id, bundle, report_dataset)
    for filename, expected_content in expected_reports.items():
        report_path = question_bank_reports_dir(course_id) / filename
        if not report_path.exists():
            errors.append(f"missing generated report: {filename}")
        elif report_path.read_text(encoding="utf-8") != expected_content:
            errors.append(f"generated report is stale: {filename}")
    for path in (
        question_bank_web_dir(course_id) / "index.html",
        Path(__file__).resolve().parents[1] / "templates" / "question-bank.html",
        Path(__file__).resolve().parents[2] / "assets" / "question-bank.js",
        Path(__file__).resolve().parents[2] / "assets" / "question-bank.css",
    ):
        if not path.exists():
            errors.append(f"missing question-bank web artifact: {path}")
    page_path = question_bank_web_dir(course_id) / "index.html"
    if (
        page_path.exists()
        and page_path.read_text(encoding="utf-8") != _question_bank_page_html(course_id)
    ):
        errors.append("generated question-bank page is stale")
    course_page = question_bank_web_dir(course_id).parent / "index.html"
    if not course_page.exists():
        errors.append(f"missing generated course page: {course_page}")
    else:
        course_source = course_page.read_text(encoding="utf-8")
        if (
            'class="question-bank-cta"' not in course_source
            or question_bank_url(course_id) not in course_source
        ):
            errors.append("course page is missing the question-bank entry point")
    curriculum = load_curriculum(course_id)
    for lesson in iter_lessons(curriculum):
        lesson_page = lesson_dir(course_id, lesson) / "index.html"
        if not lesson_page.exists():
            errors.append(f"missing generated lesson page: {lesson['id']}")
            continue
        lesson_source = lesson_page.read_text(encoding="utf-8")
        expected_summary = question_bank_summary(
            course_id,
            lesson["id"],
            dataset=expected,
        )
        if (
            'class="lesson-question-evidence"' not in lesson_source
            or f"?topic={lesson['id']}" not in lesson_source
            or not expected_summary
            or expected_summary not in lesson_source
        ):
            errors.append(
                f"lesson page is missing question-bank evidence: {lesson['id']}"
            )
    local_path = question_bank_local_data_path(course_id)
    local_bundle = load_question_bank(course_id, include_private=True)
    expected_local = build_browser_dataset(
        course_id,
        local_bundle,
        include_private=True,
    )
    if expected_local["privacy"]["contains_private_content"]:
        if not local_path.exists():
            errors.append("missing generated local dataset for private overlay")
        else:
            try:
                current_local = load_json(local_path)
            except Exception as exc:
                errors.append(f"cannot read local dataset: {exc}")
            else:
                comparable_local = {
                    key: value
                    for key, value in current_local.items()
                    if key != "generated_at"
                }
                if comparable_local != expected_local:
                    errors.append("local dataset is stale; run build_question_bank.py")
                local_version_input = {
                    key: value
                    for key, value in current_local.items()
                    if key not in {"dataset_version", "generated_at"}
                }
                if current_local.get("dataset_version") != stable_json_hash(
                    local_version_input
                ):
                    errors.append("local dataset version does not match content")
    elif local_path.exists():
        errors.append("stale local dataset exists without a private overlay")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "course_id",
        nargs="?",
        default="big-data-analysis-engineer-written",
    )
    parser.add_argument("--check", action="store_true", help="validate generated outputs without writing")
    parser.add_argument(
        "--skip-lesson-integration",
        action="store_true",
        help="do not rebuild course and lesson shells",
    )
    args = parser.parse_args()

    report = validate_question_bank_data(args.course_id)
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    if report.errors:
        return 1
    bundle = load_question_bank(args.course_id)
    if args.check:
        errors = _check_outputs(args.course_id, bundle)
        for error in errors:
            print(f"ERROR: {error}")
        if not errors:
            print(f"Question bank is current: {args.course_id}")
        return 1 if errors else 0

    try:
        outputs = _write_outputs(
            args.course_id,
            bundle,
            integrate_lessons=not args.skip_lesson_integration,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: build failed: {exc}")
        return 1
    for name, path in outputs.items():
        print(f"{name}: {path}")
    print(f"url: {question_bank_url(args.course_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
