from __future__ import annotations

import copy
import json
import math
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import question_bank_validation as validation  # noqa: E402
from build_question_bank import (  # noqa: E402
    _answer_resolution,
    analyze_topics,
    build_browser_dataset,
    build_generated_dataset,
    validate_ephemeral_sqlite_build,
    validate_sqlite_artifact,
    write_sqlite,
)
from question_bank_common import (  # noqa: E402
    DATASET_HASH_VERSION,
    QUESTION_CONTENT_HASH_VERSION,
    fuzzy_duplicate_pairs,
    merge_question_bank_overlay,
    question_content_hash,
    question_bank_local_data_path,
    question_bank_web_dir,
    stable_json_hash,
)
from study_json_schema import json_schema_errors  # noqa: E402


COURSE_ID = "big-data-analysis-engineer-written"
TOPIC_CODE = "1-1-1-1"


def _source(rights_status: str = "link_only") -> dict:
    return {
        "source_id": "source-1",
        "title": "Test evidence",
        "url": "https://example.test/evidence",
        "provider": "Fixture provider",
        "source_type": "reconstruction",
        "accessed_at": "2026-08-29",
        "reliability": "medium",
        "rights": {
            "status": rights_status,
            "basis": "Test-only rights assertion.",
            "terms_url": None,
            "notes": "No external content is copied by this fixture.",
        },
        "notes": "In-memory test fixture.",
    }


def _round(index: int, *, expected_questions: int = 1) -> dict:
    return {
        "round_id": f"round-{index}",
        "exam_round": index,
        "exam_date": f"202{index}-04-01",
        "status": "held",
        "expected_questions": expected_questions,
        "verification_status": "multi_source_confirmed",
        "source_ids": ["source-1"],
        "curriculum_version_id": "test-curriculum",
    }


def _variant(
    index: int,
    *,
    content_mode: str = "link_only",
    answer_status: str = "unverified",
) -> dict:
    question_text = "Which test choice is correct?" if content_mode == "full" else None
    choices = ["First", "Second"] if content_mode == "full" else []
    return {
        "variant_id": f"variant-{index}",
        "question_id": f"question-{index}",
        "appearance_id": f"appearance-{index}",
        "source_id": "source-1",
        "content_mode": content_mode,
        "question_text": question_text,
        "choices": choices,
        "answer_claim": 1 if content_mode == "full" else None,
        "answer_status": answer_status,
        "concept_summary": "A independently written summary of the observed topic.",
        "source_locator": f"fixture item {index}",
        "content_hash": question_content_hash(question_text, choices),
        "content_hash_version": (
            QUESTION_CONTENT_HASH_VERSION if content_mode == "full" else None
        ),
        "review_status": "approved",
    }


def _group(index: int, *, analysis_eligible: bool = True) -> dict:
    return {
        "question_id": f"question-{index}",
        "origin_type": "reconstruction",
        "appearances": [
            {
                "appearance_id": f"appearance-{index}",
                "round_id": f"round-{index}",
                "question_number": index,
                "variant_ids": [f"variant-{index}"],
                "primary_topic_code": TOPIC_CODE,
                "topic_codes": [TOPIC_CODE],
                "scope_status": "in_scope",
                "review_status": "approved",
                "analysis_eligible": analysis_eligible,
            }
        ],
        "duplicate_group": None,
    }


def _annotation(index: int) -> dict:
    return {
        "annotation_id": f"annotation-{index}",
        "question_id": f"question-{index}",
        "appearance_id": f"appearance-{index}",
        "keywords": ["fixture"],
        "concept_summary": "A reviewed, independent topic summary.",
        "difficulty": None,
        "explanation": None,
        "choice_explanations": {},
        "producer": "test-suite",
        "created_at": "2026-08-29T00:00:00+09:00",
        "review_status": "approved",
    }


def _bundle(
    round_count: int = 1,
    *,
    rights_status: str = "link_only",
    content_mode: str = "link_only",
    answer_status: str = "unverified",
    expected_questions: int = 1,
) -> dict[str, dict]:
    indexes = range(1, round_count + 1)
    return {
        "sources": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "sources": [_source(rights_status)],
        },
        "rounds": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "rounds": [
                _round(index, expected_questions=expected_questions)
                for index in indexes
            ],
        },
        "groups": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "groups": [_group(index) for index in indexes],
        },
        "variants": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "variants": [
                _variant(
                    index,
                    content_mode=content_mode,
                    answer_status=answer_status,
                )
                for index in indexes
            ],
        },
        "annotations": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "annotations": [_annotation(index) for index in indexes],
        },
        "analysis_sets": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "active_analysis_set_id": "analysis-fixture-active",
            "analysis_sets": [
                {
                    "analysis_set_id": "analysis-fixture-active",
                    "title": "Active fixture selection",
                    "created_at": "2026-08-29T00:00:00+09:00",
                    "curriculum_version_id": "test-curriculum",
                    "inclusion": {"reviewed": True},
                    "included_appearance_ids": [
                        f"appearance-{index}" for index in indexes
                    ],
                    "notes": "Test selection.",
                }
            ],
        },
        "generated": {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "questions": [],
        },
    }


def _validate_bundle(bundle: dict[str, dict]) -> validation.QuestionBankReport:
    topics = {TOPIC_CODE: {"id": TOPIC_CODE, "title": "Fixture topic"}}
    with (
        patch.object(validation, "load_question_bank", return_value=bundle),
        patch.object(validation, "curriculum_topic_map", return_value=topics),
    ):
        return validation.validate_question_bank_data(COURSE_ID)


class QuestionBankValidationTests(unittest.TestCase):
    def test_valid_link_only_bundle_passes_with_practice_warning(self) -> None:
        report = _validate_bundle(_bundle())

        self.assertEqual(report.errors, [])
        self.assertTrue(
            any("no rights-cleared public full-text" in item for item in report.warnings)
        )

    def test_cross_document_reference_errors_are_reported(self) -> None:
        bundle = _bundle()
        bundle["groups"]["groups"][0]["appearances"][0]["variant_ids"] = [
            "missing-variant"
        ]

        report = _validate_bundle(bundle)

        self.assertTrue(any("unknown variant_id" in item for item in report.errors))
        self.assertTrue(any("unreferenced variants" in item for item in report.errors))

    def test_link_only_source_cannot_store_full_question_content(self) -> None:
        bundle = _bundle(content_mode="full")

        report = _validate_bundle(bundle)

        self.assertTrue(
            any(
                "full content is forbidden for rights status link_only" in item
                for item in report.errors
            )
        )

    def test_valid_analysis_set_and_generated_question_pass(self) -> None:
        bundle = _bundle()
        bundle["analysis_sets"]["analysis_sets"] = [
            {
                "analysis_set_id": "analysis-fixture",
                "title": "Reviewed fixture",
                "created_at": "2026-08-29T00:00:00+09:00",
                "curriculum_version_id": "test-curriculum",
                "inclusion": {"reviewed": True},
                "included_appearance_ids": ["appearance-1"],
                "notes": "Test selection.",
            }
        ]
        bundle["analysis_sets"]["active_analysis_set_id"] = "analysis-fixture"
        bundle["generated"]["questions"] = [
            {
                "question_id": "generated-fixture",
                "origin_type": "generated",
                "question_text": "Which choice is correct?",
                "choices": ["First", "Second"],
                "answer": 1,
                "topic_codes": [TOPIC_CODE],
                "keywords": ["fixture"],
                "explanation": "The first choice is correct in this fixture.",
                "choice_explanations": {"1": "Correct.", "2": "Incorrect."},
                "producer": "test-suite",
                "created_at": "2026-08-29T00:00:00+09:00",
                "review_status": "approved",
            }
        ]

        report = _validate_bundle(bundle)

        self.assertEqual(report.errors, [])

    def test_analysis_set_requires_known_eligible_appearance(self) -> None:
        bundle = _bundle()
        bundle["analysis_sets"]["analysis_sets"] = [
            {
                "analysis_set_id": "analysis-fixture",
                "title": "Reviewed fixture",
                "created_at": "2026-08-29T00:00:00+09:00",
                "curriculum_version_id": "test-curriculum",
                "inclusion": {},
                "included_appearance_ids": ["missing-appearance"],
                "notes": "Test selection.",
                "unexpected": True,
            }
        ]
        bundle["analysis_sets"]["active_analysis_set_id"] = "analysis-fixture"

        report = _validate_bundle(bundle)

        self.assertTrue(any("unknown appearance_id" in item for item in report.errors))
        self.assertTrue(any("additional property" in item for item in report.errors))

    def test_generated_question_bounds_and_references_are_checked(self) -> None:
        bundle = _bundle()
        bundle["generated"]["questions"] = [
            {
                "question_id": "question-1",
                "origin_type": "generated",
                "question_text": "Broken fixture?",
                "choices": ["Only one"],
                "answer": 2,
                "topic_codes": ["9-9-9-9"],
                "keywords": ["fixture"],
                "explanation": "Deliberately malformed.",
                "choice_explanations": {"2": "Out of range."},
                "producer": "test-suite",
                "created_at": "not-a-timestamp",
                "review_status": "approved",
            }
        ]

        report = _validate_bundle(bundle)

        self.assertTrue(any("collides" in item for item in report.errors))
        self.assertTrue(any("answer exceeds choices" in item for item in report.errors))
        self.assertTrue(any("unknown topic code" in item for item in report.errors))
        self.assertTrue(any("ISO timestamp" in item for item in report.errors))

    def test_annotation_must_match_appearance_owner_and_be_uniquely_approved(self) -> None:
        bundle = _bundle(2)
        bundle["annotations"]["annotations"][0]["appearance_id"] = "appearance-2"
        duplicate = copy.deepcopy(bundle["annotations"]["annotations"][1])
        duplicate["annotation_id"] = "annotation-2-duplicate"
        bundle["annotations"]["annotations"].append(duplicate)

        report = _validate_bundle(bundle)

        self.assertTrue(any("does not own appearance_id" in item for item in report.errors))
        self.assertTrue(any("multiple approved annotations" in item for item in report.errors))

    def test_round_and_question_number_duplicates_and_bounds_are_rejected(self) -> None:
        bundle = _bundle(2)
        bundle["rounds"]["rounds"][1]["exam_round"] = 1
        second_appearance = bundle["groups"]["groups"][1]["appearances"][0]
        second_appearance["round_id"] = "round-1"
        second_appearance["question_number"] = 1
        bundle["rounds"]["rounds"][0]["expected_questions"] = 1

        report = _validate_bundle(bundle)

        self.assertTrue(any("duplicate exam_round" in item for item in report.errors))
        self.assertTrue(any("duplicate question_number" in item for item in report.errors))

        second_appearance["question_number"] = 2
        report = _validate_bundle(bundle)
        self.assertTrue(any("exceeds expected_questions" in item for item in report.errors))


class QuestionBankOverlayTests(unittest.TestCase):
    def test_partial_overlay_can_enrich_existing_round_and_appearance(self) -> None:
        round_items = merge_question_bank_overlay(
            "rounds",
            [_round(1)],
            [{"round_id": "round-1", "source_ids": ["source-private"]}],
        )
        group_items = merge_question_bank_overlay(
            "groups",
            [_group(1)],
            [
                {
                    "question_id": "question-1",
                    "appearances": [
                        {
                            "appearance_id": "appearance-1",
                            "variant_ids": ["variant-private"],
                        }
                    ],
                }
            ],
        )

        self.assertEqual(
            round_items[0]["source_ids"], ["source-1", "source-private"]
        )
        appearance = group_items[0]["appearances"][0]
        self.assertEqual(
            appearance["variant_ids"], ["variant-1", "variant-private"]
        )
        self.assertEqual(appearance["primary_topic_code"], TOPIC_CODE)

    def test_overlay_repeated_values_are_not_duplicated(self) -> None:
        result = merge_question_bank_overlay(
            "rounds",
            [_round(1)],
            [{"round_id": "round-1", "source_ids": ["source-1"]}],
        )

        self.assertEqual(result[0]["source_ids"], ["source-1"])


class QuestionBankDuplicateTests(unittest.TestCase):
    def test_integrity_hash_preserves_symbols_and_normalizes_only_nfc(self) -> None:
        self.assertNotEqual(
            question_content_hash("P(X < 0)?", ["A", "B"]),
            question_content_hash("P(X > 0)?", ["A", "B"]),
        )
        self.assertNotEqual(
            question_content_hash("value = -1", ["A", "B"]),
            question_content_hash("value = 1", ["A", "B"]),
        )
        self.assertEqual(
            question_content_hash("caf\u00e9", ["A", "B"]),
            question_content_hash("cafe\u0301", ["A", "B"]),
        )

    def test_dataset_hash_canonicalizes_integral_floats_and_rejects_nan(self) -> None:
        self.assertEqual(stable_json_hash({"value": 1.0}), stable_json_hash({"value": 1}))
        with self.assertRaises(ValueError):
            stable_json_hash({"value": math.nan})

    def test_same_appearance_variants_are_not_unresolved_duplicates(self) -> None:
        first = _variant(1)
        second = copy.deepcopy(first)
        second["variant_id"] = "variant-1-corroborating"

        self.assertEqual(fuzzy_duplicate_pairs([first, second]), [])

    def test_similar_variants_in_different_groups_are_candidates(self) -> None:
        first = _variant(1)
        second = _variant(2)
        second["concept_summary"] = first["concept_summary"]

        pairs = fuzzy_duplicate_pairs([first, second])

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][:2], ("variant-1", "variant-2"))


class QuestionBankRightsTests(unittest.TestCase):
    def test_answer_resolution_binds_status_and_claim_to_selected_content(self) -> None:
        selected = _variant(
            1,
            content_mode="full",
            answer_status="expert_reviewed",
        )
        selected["answer_claim"] = 1
        status_only = copy.deepcopy(selected)
        status_only["variant_id"] = "variant-status-only"
        status_only["answer_claim"] = None
        status_only["answer_status"] = "official_verified"
        status_only["review_status"] = "needs_review"
        different_content = copy.deepcopy(selected)
        different_content["variant_id"] = "variant-different-content"
        different_content["question_text"] = "A different question?"
        different_content["answer_claim"] = 2
        different_content["content_hash"] = question_content_hash(
            different_content["question_text"], different_content["choices"]
        )

        self.assertEqual(
            _answer_resolution(
                [selected, status_only, different_content], selected=selected
            ),
            (1, "expert_reviewed"),
        )

    def test_verified_answer_provenance_is_enforced(self) -> None:
        official = _bundle(
            rights_status="public_fulltext",
            content_mode="full",
            answer_status="official_verified",
        )
        report = _validate_bundle(official)
        self.assertTrue(
            any("official source" in item for item in report.errors)
        )

        corroborated = _bundle(
            rights_status="public_fulltext",
            content_mode="full",
            answer_status="multi_source_corroborated",
        )
        report = _validate_bundle(corroborated)
        self.assertTrue(
            any("two independent providers" in item for item in report.errors)
        )

    def test_private_local_artifact_is_outside_static_web_root(self) -> None:
        local_path = question_bank_local_data_path(COURSE_ID).resolve()
        web_root = question_bank_web_dir(COURSE_ID).resolve()
        self.assertFalse(local_path.is_relative_to(web_root))
        self.assertIn("build", local_path.parts)

    def test_public_validator_fails_closed_on_private_full_text(self) -> None:
        dataset = {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "title": "Fixture",
            "generated_at": "2026-08-29T00:00:00+09:00",
            "dataset_version": "fixture-version",
            "summary": {},
            "topics": [],
            "questions": [
                {
                    "content_mode": "full",
                    "rights_status": "private_only",
                    "question_text": "This must not be public.",
                    "choices": ["A", "B"],
                    "accepted_answer": 1,
                    "answer_status": "expert_reviewed",
                    "practice_eligible": True,
                }
            ],
        }

        report = validation.validate_public_dataset(COURSE_ID, dataset)

        self.assertTrue(
            any("full text lacks public_fulltext rights" in item for item in report.errors)
        )

    def test_public_validator_rejects_private_source_metadata(self) -> None:
        dataset = {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "title": "Fixture",
            "generated_at": "2026-08-29T00:00:00+09:00",
            "dataset_version": "a" * 64,
            "summary": {},
            "topics": [],
            "privacy": {"scope": "public", "contains_private_content": False},
            "questions": [
                {
                    "content_mode": "link_only",
                    "rights_status": "link_only",
                    "question_text": None,
                    "choices": [],
                    "accepted_answer": None,
                    "answer_status": "unverified",
                    "practice_eligible": False,
                    "source_links": [{"rights_status": "private_only"}],
                }
            ],
        }

        report = validation.validate_public_dataset(COURSE_ID, dataset)

        self.assertTrue(
            any("restricted source leaked" in item for item in report.errors)
        )

    def test_tracked_canonical_cannot_resolve_variant_via_private_overlay(self) -> None:
        public = _bundle(content_mode="full", answer_status="expert_reviewed")
        public["variants"]["variants"][0]["source_id"] = "source-private"
        public["rounds"]["rounds"][0]["source_ids"].append("source-private")
        combined = copy.deepcopy(public)
        private_source = _source("private_only")
        private_source["source_id"] = "source-private"
        combined["sources"]["sources"].append(private_source)
        topics = {TOPIC_CODE: {"id": TOPIC_CODE, "title": "Fixture topic"}}

        def load_bundle(_course_id: str, *, include_private: bool = False) -> dict:
            return combined if include_private else public

        with (
            patch.object(validation, "load_question_bank", side_effect=load_bundle),
            patch.object(validation, "curriculum_topic_map", return_value=topics),
        ):
            report = validation.validate_question_bank_data(COURSE_ID)

        self.assertTrue(
            any("must be defined in tracked sources.json" in item for item in report.errors)
        )

    def test_public_dataset_version_is_bound_to_complete_content(self) -> None:
        dataset = build_browser_dataset(COURSE_ID, _bundle())
        dataset["generated_at"] = "2026-08-29T00:00:00+09:00"
        self.assertFalse(
            any(
                "dataset_version does not match content" in item
                for item in validation.validate_public_dataset(COURSE_ID, dataset).errors
            )
        )

        dataset["questions"][0]["concept_summary"] = "Tampered summary."
        report = validation.validate_public_dataset(COURSE_ID, dataset)

        self.assertTrue(
            any("dataset_version does not match content" in item for item in report.errors)
        )

    def test_public_dataset_schema_requires_all_top_level_sections(self) -> None:
        dataset = {
            "schema_version": 1,
            "course_id": COURSE_ID,
            "title": "Incomplete fixture",
            "generated_at": "2026-08-29T00:00:00+09:00",
            "dataset_version": "a" * 64,
            "summary": {},
            "topics": [],
            "questions": [],
            "privacy": {"scope": "public", "contains_private_content": False},
        }

        report = validation.validate_public_dataset(COURSE_ID, dataset)

        self.assertTrue(
            any("missing required property target_curriculum" in item for item in report.errors)
        )
        self.assertTrue(
            any("missing required property coverage" in item for item in report.errors)
        )
        self.assertTrue(
            any("missing required property filters" in item for item in report.errors)
        )

    def test_public_export_redacts_private_variant_but_local_export_keeps_it(self) -> None:
        bundle = _bundle(
            rights_status="private_only",
            content_mode="full",
            answer_status="expert_reviewed",
        )
        private_source = bundle["sources"]["sources"][0]
        private_source["source_id"] = "source-private"
        bundle["variants"]["variants"][0]["source_id"] = "source-private"
        public_link = _variant(1)
        public_link["variant_id"] = "variant-public-link"
        bundle["sources"]["sources"].append(_source("link_only"))
        bundle["variants"]["variants"].append(public_link)
        bundle["groups"]["groups"][0]["appearances"][0]["variant_ids"].append(
            "variant-public-link"
        )

        public = build_browser_dataset(COURSE_ID, bundle, include_private=False)
        local = build_browser_dataset(COURSE_ID, bundle, include_private=True)

        public_question = public["questions"][0]
        self.assertEqual(public_question["content_mode"], "link_only")
        self.assertIsNone(public_question["question_text"])
        self.assertEqual(public_question["choices"], [])
        self.assertIsNone(public_question["accepted_answer"])
        self.assertFalse(public_question["practice_eligible"])
        self.assertEqual(
            [link["rights_status"] for link in public_question["source_links"]],
            ["link_only"],
        )
        self.assertFalse(public["privacy"]["contains_private_content"])
        public_topic = next(item for item in public["topics"] if item["code"] == TOPIC_CODE)
        self.assertEqual(public_topic["source_count"], 1)

        local_question = local["questions"][0]
        self.assertEqual(local_question["content_mode"], "full")
        self.assertEqual(local_question["rights_status"], "private_only")
        self.assertEqual(local_question["accepted_answer"], 1)
        self.assertTrue(local_question["practice_eligible"])

    def test_private_only_appearance_does_not_affect_public_aggregates(self) -> None:
        bundle = _bundle(
            rights_status="private_only",
            content_mode="full",
            answer_status="expert_reviewed",
        )

        public = build_browser_dataset(COURSE_ID, bundle, include_private=False)
        local = build_browser_dataset(COURSE_ID, bundle, include_private=True)

        public_topic = next(item for item in public["topics"] if item["code"] == TOPIC_CODE)
        self.assertEqual(public["questions"], [])
        self.assertEqual(public["summary"]["source_count"], 0)
        self.assertEqual(public["summary"]["observed_appearances"], 0)
        self.assertEqual(public_topic["observed_questions"], 0)
        self.assertEqual(public["coverage"], [])
        self.assertEqual(len(local["questions"]), 1)
        self.assertTrue(local["privacy"]["contains_private_content"])


class QuestionBankAnalysisTests(unittest.TestCase):
    def test_active_analysis_set_is_authoritative(self) -> None:
        bundle = _bundle(3)
        bundle["analysis_sets"]["analysis_sets"][0][
            "included_appearance_ids"
        ] = []

        topics, coverage, summary = analyze_topics(COURSE_ID, bundle)
        topic = next(item for item in topics if item["code"] == TOPIC_CODE)

        self.assertEqual(summary["active_analysis_set_id"], "analysis-fixture-active")
        self.assertEqual(summary["analysis_eligible_appearances"], 0)
        self.assertEqual(summary["frequency_included_appearances"], 0)
        self.assertEqual(topic["observed_questions"], 0)
        self.assertTrue(all(item["observed_questions"] == 0 for item in coverage))

    def test_low_single_source_rounds_never_unlock_importance(self) -> None:
        bundle = _bundle(3)
        bundle["sources"]["sources"][0]["reliability"] = "low"

        topics, coverage, summary = analyze_topics(COURSE_ID, bundle)
        topic = next(item for item in topics if item["code"] == TOPIC_CODE)

        self.assertEqual(summary["eligible_rounds"], 0)
        self.assertIsNone(topic["importance_score"])
        self.assertTrue(all(item["coverage"] == 1.0 for item in coverage))
        self.assertTrue(all(not item["evidence_quality_met"] for item in coverage))
        self.assertTrue(
            all(
                item["exclusion_reason"] == "evidence_quality_insufficient"
                for item in coverage
            )
        )

    def test_generated_questions_have_a_separate_validated_artifact(self) -> None:
        bundle = _bundle()
        generated = {
            "question_id": "generated-fixture",
            "origin_type": "generated",
            "question_text": "Which choice is correct?",
            "choices": ["First", "Second"],
            "answer": 1,
            "topic_codes": [TOPIC_CODE],
            "keywords": ["fixture"],
            "explanation": "The first choice is correct.",
            "choice_explanations": {"1": "Correct.", "2": "Incorrect."},
            "producer": "test-suite",
            "created_at": "2026-08-29T00:00:00+09:00",
            "review_status": "approved",
        }
        draft = {**generated, "question_id": "generated-draft", "review_status": "needs_review"}
        bundle["generated"]["questions"] = [generated, draft]

        dataset = build_generated_dataset(COURSE_ID, bundle)
        dataset["generated_at"] = "2026-08-29T00:00:00+09:00"

        self.assertEqual([item["question_id"] for item in dataset["questions"]], ["generated-fixture"])
        self.assertEqual(dataset["dataset_hash_version"], DATASET_HASH_VERSION)
        self.assertEqual(validation.validate_generated_dataset(COURSE_ID, dataset).errors, [])

    def test_sqlite_round_trips_all_canonical_collections(self) -> None:
        bundle = _bundle()
        browser = build_browser_dataset(COURSE_ID, bundle)
        generated = build_generated_dataset(COURSE_ID, bundle)
        browser["generated_at"] = "2026-08-29T00:00:00+09:00"
        generated["generated_at"] = "2026-08-29T00:00:00+09:00"

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "questions.sqlite"
            write_sqlite(COURSE_ID, bundle, browser, generated, output_path=path)
            self.assertEqual(
                validate_sqlite_artifact(path, bundle, browser, generated), []
            )
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM analysis_sets").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM generated_questions").fetchone()[0],
                    0,
                )
            finally:
                connection.close()

    def test_sqlite_check_does_not_require_a_persistent_database(self) -> None:
        bundle = _bundle()
        browser = build_browser_dataset(COURSE_ID, bundle)
        generated = build_generated_dataset(COURSE_ID, bundle)
        browser["generated_at"] = "2026-08-29T00:00:00+09:00"
        generated["generated_at"] = "2026-08-29T00:00:00+09:00"

        with tempfile.TemporaryDirectory() as folder:
            missing_persistent = Path(folder) / "build" / "questions.sqlite"
            self.assertFalse(missing_persistent.exists())
            self.assertEqual(
                validate_ephemeral_sqlite_build(
                    COURSE_ID,
                    bundle,
                    browser,
                    generated,
                ),
                [],
            )
            self.assertFalse(missing_persistent.exists())

    def test_importance_is_withheld_until_three_eligible_rounds(self) -> None:
        limited_topics, _, limited_summary = analyze_topics(COURSE_ID, _bundle(2))
        limited_topic = next(item for item in limited_topics if item["code"] == TOPIC_CODE)

        self.assertEqual(limited_summary["evidence_level"], "limited")
        self.assertIsNone(limited_topic["importance_score"])
        self.assertEqual(limited_topic["importance_label"], "근거 부족")

        scored_topics, _, scored_summary = analyze_topics(COURSE_ID, _bundle(3))
        scored_topic = next(item for item in scored_topics if item["code"] == TOPIC_CODE)

        self.assertEqual(scored_summary["evidence_level"], "provisional")
        self.assertEqual(scored_topic["importance_score"], 100.0)
        self.assertEqual(scored_topic["stars"], 5)

    def test_dataset_and_version_are_deterministic_for_identical_input(self) -> None:
        bundle = _bundle(3)

        first = build_browser_dataset(COURSE_ID, copy.deepcopy(bundle))
        second = build_browser_dataset(COURSE_ID, copy.deepcopy(bundle))

        self.assertEqual(first, second)
        self.assertEqual(first["dataset_version"], second["dataset_version"])
        self.assertNotIn("generated_at", first)


class QuestionBankSchemaTests(unittest.TestCase):
    def test_question_bank_schemas_are_parseable_and_versioned(self) -> None:
        schema_paths = sorted(SCHEMAS_DIR.glob("question-bank*.json"))

        self.assertGreaterEqual(len(schema_paths), 2)
        for schema_path in schema_paths:
            with self.subTest(schema=schema_path.name):
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertTrue(schema["$id"].endswith(schema_path.name))

    def test_canonical_and_public_documents_conform_to_full_schemas(self) -> None:
        canonical_schema = json.loads(
            (SCHEMAS_DIR / "question-bank-canonical.schema.json").read_text(
                encoding="utf-8"
            )
        )
        canonical_dir = SCHEMAS_DIR.parents[1] / "question-bank" / COURSE_ID
        for filename in (
            "sources.json",
            "rounds.json",
            "question-groups.json",
            "question-variants.json",
            "annotations.json",
            "analysis-sets.json",
            "generated_questions.json",
        ):
            with self.subTest(document=filename):
                document = json.loads(
                    (canonical_dir / filename).read_text(encoding="utf-8")
                )
                self.assertEqual(json_schema_errors(document, canonical_schema), [])

        public_schema = json.loads(
            (SCHEMAS_DIR / "question-bank-public.schema.json").read_text(
                encoding="utf-8"
            )
        )
        public_path = (
            SCHEMAS_DIR.parents[1]
            / "courses"
            / COURSE_ID
            / "questions"
            / "data"
            / "questions.public.json"
        )
        public = json.loads(public_path.read_text(encoding="utf-8"))
        self.assertEqual(json_schema_errors(public, public_schema), [])

        generated_schema = json.loads(
            (SCHEMAS_DIR / "question-bank-generated.schema.json").read_text(
                encoding="utf-8"
            )
        )
        generated_path = public_path.with_name(
            "questions.generated.public.json"
        )
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
        self.assertEqual(
            json_schema_errors(generated, generated_schema), []
        )


if __name__ == "__main__":
    unittest.main()
