from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validation  # noqa: E402


COURSE_ID = "official-atom-fixture"
LESSON_A = "1-1-1-1"
LESSON_B = "1-1-1-2"
SHARED_ATOM = "두 경로에서 같은 텍스트로 쓰이는 공식 atom"
UNIQUE_ATOM = "첫 번째 레슨만의 공식 atom"


def fixture_curriculum() -> dict:
    return {
        "version": 1,
        "course_id": COURSE_ID,
        "title": "공식 atom 검증 과정",
        "certification": "검증 자격",
        "mode": "written",
        "authority": "검증 기관",
        "verified_at": "2026-08-28",
        "sources": [{
            "id": "official-source",
            "title": "공식 출제기준",
            "authority": "검증 기관",
            "url": "https://example.invalid/official",
            "effective_from": None,
            "effective_to": None,
            "retrieved_at": "2026-08-28",
        }],
        "sections": [{
            "id": "1",
            "title": "검증 섹션",
            "units": [{
                "id": "1-1",
                "title": "검증 유닛",
                "lessons": [{
                    "id": "1-1-1",
                    "title": "검증 그룹",
                    "sublessons": [
                        {
                            "id": LESSON_A,
                            "title": "복수 atom 레슨",
                            "slug": "multiple-atoms",
                            "topics": [SHARED_ATOM, UNIQUE_ATOM],
                            "lesson_type": "concept",
                            "supplemental": False,
                            "source_refs": ["official-source"],
                            "official_basis": ["검증 > 복수 atom"],
                        },
                        {
                            "id": LESSON_B,
                            "title": "단일 atom 레슨",
                            "slug": "single-atom",
                            "topics": [SHARED_ATOM],
                            "singleton_reason": (
                                "공식 출제기준의 이 atom을 더 나누면 의미가 훼손된다."
                            ),
                            "lesson_type": "concept",
                            "supplemental": False,
                            "source_refs": ["official-source"],
                            "official_basis": ["검증 > 단일 atom"],
                        },
                    ],
                }],
            }],
        }],
    }


def coverage_item(
    path: str,
    lesson_id: str,
    atom: str,
) -> dict:
    return {
        "official_path": path,
        "official_atom": atom,
        "source_refs": ["official-source"],
        "lesson_ids": [lesson_id],
        "mapping": "direct",
    }


def fixture_coverage() -> dict:
    return {
        "version": 1,
        "course_id": COURSE_ID,
        "verified_at": "2026-08-28",
        "coverage_granularity": "official-atom",
        "official_item_count": 3,
        "items": [
            coverage_item("공식 경로 A > 공통", LESSON_A, SHARED_ATOM),
            coverage_item("공식 경로 A > 고유", LESSON_A, UNIQUE_ATOM),
            coverage_item("공식 경로 B > 공통", LESSON_B, SHARED_ATOM),
        ],
    }


def validate_coverage(coverage: dict) -> validation.Report:
    with patch.object(
        validation,
        "load_json",
        side_effect=[fixture_curriculum(), coverage],
    ):
        return validation.validate_coverage(COURSE_ID)


class OfficialAtomCoverageTest(unittest.TestCase):
    def test_positive_multiset_allows_same_atom_text_on_distinct_lessons(self) -> None:
        report = validate_coverage(fixture_coverage())
        self.assertEqual(report.errors, [])

    def test_missing_official_atom_is_rejected(self) -> None:
        coverage = fixture_coverage()
        coverage["items"][1].pop("official_atom")
        report = validate_coverage(coverage)
        self.assertTrue(
            any("missing official_atom" in error for error in report.errors)
        )
        self.assertTrue(
            any("curriculum leaf topics" in error for error in report.errors)
        )

    def test_missing_coverage_item_is_rejected_as_multiset_difference(self) -> None:
        coverage = fixture_coverage()
        coverage["items"].pop()
        coverage["official_item_count"] = 2
        report = validate_coverage(coverage)
        self.assertTrue(
            any("topic atom count 3" in error for error in report.errors)
        )
        self.assertTrue(
            any("missing=" in error and LESSON_B in error for error in report.errors)
        )

    def test_duplicate_pair_is_rejected_even_with_distinct_paths(self) -> None:
        coverage = fixture_coverage()
        coverage["items"][1]["official_atom"] = SHARED_ATOM
        report = validate_coverage(coverage)
        mismatch = next(
            error
            for error in report.errors
            if "curriculum leaf topics" in error
        )
        self.assertIn("missing=", mismatch)
        self.assertIn("extra=", mismatch)

    def test_duplicate_official_path_remains_invalid(self) -> None:
        coverage = fixture_coverage()
        coverage["items"][1]["official_path"] = (
            coverage["items"][0]["official_path"]
        )
        report = validate_coverage(coverage)
        self.assertTrue(
            any("duplicate official_path" in error for error in report.errors)
        )

    def test_atom_typo_is_not_accepted_as_a_lesson_topic(self) -> None:
        coverage = fixture_coverage()
        coverage["items"][1]["official_atom"] = UNIQUE_ATOM + " 오타"
        report = validate_coverage(coverage)
        self.assertTrue(
            any(
                "official_atom is not a topic" in error
                for error in report.errors
            )
        )
        self.assertTrue(
            any("curriculum leaf topics" in error for error in report.errors)
        )

    def test_official_atom_mapping_must_be_direct(self) -> None:
        coverage = fixture_coverage()
        coverage["items"][0]["mapping"] = "split"
        report = validate_coverage(coverage)
        self.assertTrue(
            any(
                "official-atom item mapping must be direct" in error
                for error in report.errors
            )
        )

    def test_official_atom_item_must_have_exactly_one_lesson(self) -> None:
        for lesson_ids in ([], [LESSON_A, LESSON_B]):
            with self.subTest(lesson_ids=lesson_ids):
                coverage = fixture_coverage()
                coverage["items"][0]["lesson_ids"] = lesson_ids
                report = validate_coverage(coverage)
                self.assertTrue(
                    any(
                        "must map to exactly one lesson" in error
                        for error in report.errors
                    )
                )

    def test_official_item_count_must_equal_curriculum_atom_count(self) -> None:
        coverage = fixture_coverage()
        coverage["official_item_count"] = 2
        report = validate_coverage(coverage)
        self.assertTrue(
            any(
                "official_item_count must equal curriculum topic atom count 3"
                in error
                for error in report.errors
            )
        )


class SingletonReasonTest(unittest.TestCase):
    def validate_curriculum(self, curriculum: dict) -> validation.Report:
        with tempfile.TemporaryDirectory() as temporary:
            json_path = Path(temporary) / f"{COURSE_ID}.json"
            json_path.with_suffix(".md").write_text(
                f"# Fixture\n\n{LESSON_A}\n\n{LESSON_B}\n",
                encoding="utf-8",
            )
            with (
                patch.object(validation, "load_json", return_value=curriculum),
                patch.object(
                    validation,
                    "curriculum_path",
                    return_value=json_path,
                ),
            ):
                return validation.validate_curriculum(COURSE_ID)

    def test_nonempty_singleton_reason_suppresses_warning(self) -> None:
        report = self.validate_curriculum(fixture_curriculum())
        self.assertFalse(
            any("one-topic atomic lesson" in warning for warning in report.warnings)
        )

    def test_missing_or_blank_reason_does_not_suppress_warning(self) -> None:
        for reason in (None, ""):
            with self.subTest(reason=reason):
                curriculum = fixture_curriculum()
                lesson = (
                    curriculum["sections"][0]["units"][0]["lessons"][0]
                    ["sublessons"][1]
                )
                if reason is None:
                    lesson.pop("singleton_reason")
                else:
                    lesson["singleton_reason"] = reason
                report = self.validate_curriculum(curriculum)
                self.assertTrue(
                    any(
                        "one-topic atomic lesson" in warning
                        for warning in report.warnings
                    )
                )

    def test_singleton_reason_is_invalid_on_multiple_topics(self) -> None:
        curriculum = fixture_curriculum()
        lesson = (
            curriculum["sections"][0]["units"][0]["lessons"][0]
            ["sublessons"][0]
        )
        lesson["singleton_reason"] = "잘못 추가된 사유"
        report = self.validate_curriculum(curriculum)
        self.assertTrue(
            any(
                "singleton_reason requires exactly one topic" in error
                for error in report.errors
            )
        )


class TopicNormalizationMetadataTest(SingletonReasonTest):
    def first_lesson(self, curriculum: dict) -> dict:
        return (
            curriculum["sections"][0]["units"][0]["lessons"][0]
            ["sublessons"][0]
        )

    def test_topic_correction_must_reference_an_official_topic(self) -> None:
        curriculum = fixture_curriculum()
        lesson = self.first_lesson(curriculum)
        lesson["topic_corrections"] = {"없는 원문": "바른 표기"}
        report = self.validate_curriculum(curriculum)
        self.assertTrue(
            any("key is not an official topic" in error for error in report.errors)
        )

    def test_duplicate_topics_require_an_explicit_reason(self) -> None:
        curriculum = fixture_curriculum()
        lesson = self.first_lesson(curriculum)
        lesson["topics"] = [SHARED_ATOM, SHARED_ATOM]
        report = self.validate_curriculum(curriculum)
        self.assertTrue(
            any(
                "duplicate official topics require duplicate_topic_reason" in error
                for error in report.errors
            )
        )

        lesson["duplicate_topic_reason"] = "공식 원문이 같은 항목을 두 번 열거함"
        report = self.validate_curriculum(curriculum)
        self.assertFalse(
            any("duplicate official topics" in error for error in report.errors)
        )

    def test_duplicate_reason_is_rejected_without_a_duplicate(self) -> None:
        curriculum = fixture_curriculum()
        lesson = self.first_lesson(curriculum)
        lesson["duplicate_topic_reason"] = "불필요한 사유"
        report = self.validate_curriculum(curriculum)
        self.assertTrue(
            any(
                "duplicate_topic_reason requires duplicate topics" in error
                for error in report.errors
            )
        )


if __name__ == "__main__":
    unittest.main()
