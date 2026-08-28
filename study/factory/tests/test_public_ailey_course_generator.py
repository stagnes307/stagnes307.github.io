from __future__ import annotations

import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


FACTORY_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = FACTORY_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_public_ailey_course as generator  # noqa: E402
import public_ailey_course_content as content  # noqa: E402
from common import iter_lessons, load_curriculum  # noqa: E402
from public_ailey_course_content import classify_topic  # noqa: E402


class PublicAileyCourseGeneratorTest(unittest.TestCase):
    def test_all_supported_courses_pass_read_only_preflight(self) -> None:
        expected_counts = {
            "quality-management-engineer-practical": 30,
            "quality-management-engineer-written": 48,
            "industrial-safety-engineer-practical": 96,
            "industrial-safety-engineer-written": 132,
        }
        for course_id in sorted(generator.SUPPORTED_COURSES):
            with self.subTest(course_id=course_id):
                curriculum = load_curriculum(course_id)
                self.assertEqual(
                    sum(1 for _ in iter_lessons(curriculum)),
                    expected_counts[course_id],
                )
                metrics = generator.preflight_course(course_id, curriculum)
                self.assertLessEqual(metrics["max_pairwise_common_sentences"], 3)
                self.assertLessEqual(metrics["max_pairwise_fact_overlap"], 0.25)

    def test_atom_fact_catalogs_cover_every_official_atom(self) -> None:
        for course_id in sorted(generator.SUPPORTED_COURSES):
            curriculum = load_curriculum(course_id)
            self.assertEqual(
                content.atom_fact_catalog_errors(course_id, curriculum),
                [],
                course_id,
            )

    def test_lesson_meta_matches_closed_schema_contract(self) -> None:
        course_id = "quality-management-engineer-practical"
        lesson = next(iter_lessons(load_curriculum(course_id)))
        metadata = generator.lesson_meta(
            course_id,
            lesson,
            timestamp="2026-08-28T12:34:56+09:00",
            ff_sha256="a" * 64,
            cc_sha256="b" * 64,
        )
        schema = json.loads(
            (FACTORY_DIR / "schemas" / "meta.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(set(schema["required"]) <= set(metadata))
        self.assertTrue(set(metadata) <= set(schema["properties"]))
        self.assertNotIn("provenance", metadata)
        self.assertEqual(metadata["artifacts"]["ff"]["prompt_profile"], generator.FF_PROFILE)
        self.assertEqual(metadata["artifacts"]["cc"]["prompt_profile"], generator.CC_PROFILE)
        self.assertEqual(generator.meta_schema_errors(metadata), [])
        bad_nested = copy.deepcopy(metadata)
        bad_nested["artifacts"]["ff"]["provenance"] = {"unexpected": True}
        self.assertTrue(generator.meta_schema_errors(bad_nested))
        bad_hash = copy.deepcopy(metadata)
        bad_hash["artifacts"]["cc"]["sha256"] = "not-a-sha256"
        self.assertTrue(generator.meta_schema_errors(bad_hash))
        bad_time = copy.deepcopy(metadata)
        bad_time["published_at"] = "2026-08-28"
        self.assertTrue(generator.meta_schema_errors(bad_time))

    def test_same_input_renders_identical_artifacts(self) -> None:
        course_id = "quality-management-engineer-practical"
        curriculum = load_curriculum(course_id)
        lesson = next(iter_lessons(curriculum))
        first_ff = generator.render_ff(course_id, curriculum, lesson)
        second_ff = generator.render_ff(course_id, curriculum, lesson)
        self.assertEqual(first_ff, second_ff)
        first_cc = generator.render_cc_document(
            course_id,
            curriculum,
            lesson,
            first_ff,
        )
        second_cc = generator.render_cc_document(
            course_id,
            curriculum,
            lesson,
            second_ff,
        )
        self.assertEqual(first_cc, second_cc)

    def test_every_teaching_h3_contains_facts_without_overuse(self) -> None:
        for course_id in sorted(generator.SUPPORTED_COURSES):
            curriculum = load_curriculum(course_id)
            for lesson in iter_lessons(curriculum):
                context = generator.build_lesson_context(
                    course_id,
                    curriculum,
                    lesson,
                )
                source = generator.render_ff(course_id, curriculum, lesson)
                counts = generator.teaching_h3_fact_counts(context, source)
                self.assertEqual(len(counts), 13)
                self.assertTrue(
                    all(count >= 3 for count in counts),
                    (course_id, lesson["id"], counts),
                )
                guide_occurrences = generator.teaching_fact_occurrences(context, source)
                self.assertLessEqual(
                    max(guide_occurrences.values(), default=0),
                    3,
                    (course_id, lesson["id"]),
                )
                self.assertTrue(
                    all(
                        count == 1
                        for count in generator.atom_fact_occurrences(context, source).values()
                    ),
                    (course_id, lesson["id"]),
                )

    def test_missing_formula_lessons_select_canonical_guides(self) -> None:
        course_id = "quality-management-engineer-written"
        curriculum = load_curriculum(course_id)
        expected = {
            "2-2-1-1": ["sampling", "sampling", "sampling-oc"],
            "4-1-1-1": ["reliability", "reliability-life-distribution"],
            "4-1-1-2": [
                "reliability-function-measures",
                "reliability-function-measures",
            ],
            "4-1-3-1": ["reliability", "reliability-test", "reliability-test"],
        }
        lessons = {
            lesson["id"]: lesson
            for lesson in iter_lessons(curriculum)
        }
        for lesson_id, guide_codes in expected.items():
            context = generator.build_lesson_context(
                course_id,
                curriculum,
                lessons[lesson_id],
            )
            guides = [
                classify_topic(context, topic)
                for topic in context.topics
            ]
            self.assertEqual([guide.code for guide in guides], guide_codes)
        formula_expectations = {
            "2-2-1-1": ("P_accept", "0.911", "무차원"),
            "4-1-1-1": ("R_exponential", "0.9048", "시간의 역수"),
            "4-1-1-2": ("MTTF", "500시간", "시간단위"),
            "4-1-3-1": ("lambda_hat", "5000장치시간", "시간의 역수"),
        }
        for lesson_id, tokens in formula_expectations.items():
            context = generator.build_lesson_context(
                course_id,
                curriculum,
                lessons[lesson_id],
            )
            guide_text = " ".join(
                " ".join((
                    guide.formula,
                    guide.variables,
                    *guide.example,
                ))
                for guide in (
                    classify_topic(context, topic)
                    for topic in context.topics
                )
            )
            for token in tokens:
                self.assertIn(token, guide_text, (lesson_id, token))

    def test_domain_specific_guide_mappings(self) -> None:
        expected = {
            "quality-management-engineer-practical": {
                "1-3-3-1": ["taguchi-characteristic", "anova-contribution", "tolerance-design"],
                "1-4-1-1": ["critical-control-plan"] * 3,
                "1-8-1-1": ["workplace-organization-5s"] * 2,
                "1-8-2-1": ["visual-management"] * 2,
            },
            "industrial-safety-engineer-written": {
                "1-4-2-1": ["accident-propensity"] * 3,
                "3-2-1-1": ["accident-investigation"] * 2,
                "3-2-1-2": ["accident-investigation"] * 2,
                "3-2-2-1": ["accident-classification", "accident-statistics-definition"],
                "5-2-2-1": ["fire-chemical"] * 3,
                "5-2-3-2": ["fire-chemical", "electrical"],
                "5-3-1-1": ["management-emergency"] * 3,
                "2-5-1-1": ["occupational-hygiene-agents"] * 3,
                "2-5-2-1": ["occupational-hygiene-agents"] * 3,
                "2-5-3-1": ["occupational-hygiene-agents"] * 3,
                "2-6-4-1": ["safety-work-study", "work-sampling", "predetermined-motion-time"],
                "2-6-5-2": ["thermal-environment", "abnormal-environment", "human-factors-work"],
                "2-6-2-1": ["human-physiology", "biomechanics"],
                "2-6-2-2": ["human-physiology", "motor-control"],
                "4-5-2-1": ["machinery", "management-emergency", "electrical"],
                "6-1-1-1": ["construction"] * 3,
                "6-2-2-1": ["risk"] * 2,
            },
            "industrial-safety-engineer-practical": {
                "1-1-2-2": ["management-emergency"] * 2,
                "1-2-2-1": ["machinery"] * 2,
                "1-8-1-1": ["electrical-explosion"] * 3,
                "1-9-4-1": ["electrical-proximity", "electrical-proximity", "electrical"],
                "1-10-2-1": ["fire-chemical"] * 3,
                "1-13-1-2": ["construction"] * 2,
                "1-15-1-1": ["legal", "risk", "risk-assessment-administration"],
                "1-15-3-2": ["risk-additive-formula", "risk"],
                "1-15-3-3": ["risk", "risk"],
            },
        }
        for course_id, course_expected in expected.items():
            curriculum = load_curriculum(course_id)
            lessons = {lesson["id"]: lesson for lesson in iter_lessons(curriculum)}
            for lesson_id, guide_codes in course_expected.items():
                context = generator.build_lesson_context(
                    course_id,
                    curriculum,
                    lessons[lesson_id],
                )
                actual = [
                    classify_topic(context, topic).code
                    for topic in context.topics
                ]
                self.assertEqual(actual, guide_codes, (course_id, lesson_id))

    def test_reviewed_formula_routes_are_topic_specific(self) -> None:
        expected = {
            "quality-management-engineer-written": {
                "1-1-2-1": ["doe-factorial", "doe-factorial", "doe-two-factor-no-rep"],
                "1-1-5-1": ["doe-split-plot", "doe-nested"],
                "3-3-1-1": ["production-planning", "dispatching-rules", "production-scheduling"],
                "3-4-1-2": ["standard-time", "productivity"],
                "4-1-3-2": ["reliability-test-operation", "reliability-probability-plot", "accelerated-life"],
                "5-1-4-1": ["capability", "six-sigma"],
            },
            "industrial-safety-engineer-written": {
                "2-2-2-2": ["risk", "system-reliability"],
                "2-6-6-1": ["manual-material-handling", "niosh-lifting"],
                "4-3-1-1": ["static-control", "static-control"],
                "4-4-2-1": ["electrical-explosion", "electrical-explosion"],
            },
            "industrial-safety-engineer-practical": {
                "1-7-2-1": ["static-control", "static", "static-control"],
                "1-15-3-1": ["risk", "risk-multiplication", "risk-matrix"],
                "1-15-3-2": ["risk-additive-formula", "risk"],
            },
        }
        for course_id, course_expected in expected.items():
            curriculum = load_curriculum(course_id)
            lessons = {lesson["id"]: lesson for lesson in iter_lessons(curriculum)}
            for lesson_id, guide_codes in course_expected.items():
                context = generator.build_lesson_context(
                    course_id, curriculum, lessons[lesson_id]
                )
                actual = [classify_topic(context, topic).code for topic in context.topics]
                self.assertEqual(actual, guide_codes, (course_id, lesson_id))

        course_id = "quality-management-engineer-written"
        curriculum = load_curriculum(course_id)
        lesson = next(lesson for lesson in iter_lessons(curriculum) if lesson["id"] == "3-3-1-1")
        context = generator.build_lesson_context(course_id, curriculum, lesson)
        source = generator.render_ff(course_id, curriculum, lesson)
        paragraphs = content.extract_h3_paragraphs(source)[:13]
        pert_paragraphs = []
        for paragraph, (_stage, focus, guide) in zip(
            paragraphs, content.teaching_focus_assignments(context)
        ):
            if guide.code == "production-scheduling":
                pert_paragraphs.append(paragraph)
            else:
                self.assertNotIn("t_e = (a + 4m + b) / 6", paragraph, focus)
        self.assertIn("t_e = (a + 4m + b) / 6", " ".join(pert_paragraphs))

        course_id = "industrial-safety-engineer-practical"
        curriculum = load_curriculum(course_id)
        lesson = next(lesson for lesson in iter_lessons(curriculum) if lesson["id"] == "1-15-3-1")
        context = generator.build_lesson_context(course_id, curriculum, lesson)
        source = generator.render_ff(course_id, curriculum, lesson)
        paragraphs = content.extract_h3_paragraphs(source)[:13]
        for paragraph, (_stage, focus, guide) in zip(
            paragraphs, content.teaching_focus_assignments(context)
        ):
            if guide.code == "risk-matrix":
                self.assertNotIn("R = L times S", paragraph, focus)

    def test_minimize_is_not_misclassified_as_fire_suppression(self) -> None:
        self.assertFalse(content._keyword_matches("피해를 최소화할 수 있다", "소화"))
        self.assertTrue(content._keyword_matches("소화설비를 점검한다", "소화"))

    def test_each_formula_guide_requires_formula_units_and_worked_example(self) -> None:
        course_id = "industrial-safety-engineer-written"
        curriculum = load_curriculum(course_id)
        lesson = next(
            lesson
            for lesson in iter_lessons(curriculum)
            if lesson["id"] == "2-6-4-1"
        )
        context = generator.build_lesson_context(course_id, curriculum, lesson)
        guides = [classify_topic(context, topic) for topic in context.topics]
        source = generator.render_ff(course_id, curriculum, lesson)
        formula_guide = next(guide for guide in guides if guide.code == "work-sampling")

        without_formula = source.replace(formula_guide.formula, "공식 삭제 fixture")
        errors = generator.public_ailey_content_quality_errors(
            course_id, curriculum, lesson, without_formula,
        )
        self.assertTrue(any("canonical formula work-sampling" in error for error in errors))

        without_example = source
        for example in formula_guide.example:
            without_example = without_example.replace(example, "수치 예시 삭제 fixture")
        errors = generator.public_ailey_content_quality_errors(
            course_id, curriculum, lesson, without_example,
        )
        self.assertTrue(any("worked example work-sampling" in error for error in errors))

    def test_accident_metric_units_distinguish_days_hours_and_counts(self) -> None:
        course_id = "industrial-safety-engineer-written"
        curriculum = load_curriculum(course_id)
        lesson = next(
            lesson
            for lesson in iter_lessons(curriculum)
            if lesson["id"] == "3-2-2-2"
        )
        context = generator.build_lesson_context(course_id, curriculum, lesson)
        guide = classify_topic(context, context.topics[0])
        self.assertEqual(guide.code, "accident-metrics")
        for token in (
            "lost_days는 손실일수인 일 단위",
            "도수율은 건/백만 근로시간",
            "강도율은 손실일/천 근로시간",
            "연천인율은 명/천 근로자",
        ):
            self.assertIn(token, guide.variables)

    def test_valid_korean_quotation_particle_is_not_rejected(self) -> None:
        self.assertFalse(
            any(pattern.search("여러 결점이 생길 수 있다는 차이가 있다") for pattern in content.BROKEN_KOREAN)
        )

    def test_target_substitution_does_not_hide_shared_fact(self) -> None:
        course_id = "quality-management-engineer-practical"
        curriculum = load_curriculum(course_id)
        lessons = list(iter_lessons(curriculum))[:2]
        contexts = [
            generator.build_lesson_context(course_id, curriculum, lesson)
            for lesson in lessons
        ]
        shared = "공통 원인과 판정근거를 연결하지 않으면 같은 오류가 재발한다."
        left = f"{content.topic_action_target(contexts[0], contexts[0].topics[0], classify_topic(contexts[0], contexts[0].topics[0]), content.action_profile_for(contexts[0], contexts[0].topics[0]))}에서 {shared}"
        right = f"{content.topic_action_target(contexts[1], contexts[1].topics[0], classify_topic(contexts[1], contexts[1].topics[0]), content.action_profile_for(contexts[1], contexts[1].topics[0]))}에서 {shared}"
        self.assertEqual(
            content.factual_sentence(left, contexts[0]),
            content.factual_sentence(right, contexts[1]),
        )

    def test_real_staging_builds_complete_isolated_course(self) -> None:
        course_id = "quality-management-engineer-practical"
        curriculum = load_curriculum(course_id)
        _metrics, prepared = generator.prepare_course(
            course_id,
            curriculum,
            timestamp="2026-08-28T12:34:56+09:00",
        )
        original_courses_dir = generator.common.COURSES_DIR
        catalog_before = generator.common.CATALOG_PATH.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            staging_root = Path(temporary)
            progress = generator.stage_course(
                course_id,
                curriculum,
                prepared,
                staging_root,
            )
            staged_course = staging_root / course_id
            self.assertEqual(len(list(staged_course.rglob("ff.md"))), 30)
            self.assertEqual(len(list(staged_course.rglob("cc.html"))), 30)
            self.assertEqual(len(list(staged_course.rglob("meta.json"))), 30)
            self.assertEqual(
                sum(
                    state["status"] == "published"
                    for state in progress["lessons"].values()
                ),
                30,
            )
        self.assertEqual(generator.common.COURSES_DIR, original_courses_dir)
        self.assertEqual(generator.common.CATALOG_PATH.read_bytes(), catalog_before)

    def test_existing_course_is_refused_before_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "existing-course"
            target.mkdir()
            with (
                patch.object(generator, "assemble_public_system_prompt"),
                patch.object(generator, "load_curriculum", return_value={}),
                patch.object(generator, "course_dir", return_value=target),
                patch.object(generator, "prepare_course") as prepare,
            ):
                with self.assertRaises(FileExistsError):
                    generator.publish_course("quality-management-engineer-practical")
            prepare.assert_not_called()

    def test_staging_failure_never_creates_final_course(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "new-course"
            with (
                patch.object(generator, "assemble_public_system_prompt"),
                patch.object(generator, "load_curriculum", return_value={}),
                patch.object(generator, "course_dir", return_value=target),
                patch.object(generator, "prepare_course", return_value=({}, [])),
                patch.object(generator, "print_audit"),
                patch.object(
                    generator,
                    "stage_course",
                    side_effect=RuntimeError("fixture staging failure"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "fixture staging failure"):
                    generator.publish_course("quality-management-engineer-practical")
            self.assertFalse(target.exists())

    def test_catalog_failure_restores_catalog_and_never_creates_course(self) -> None:
        course_id = "quality-management-engineer-practical"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / course_id
            catalog = root / "catalog.json"
            original = b'{"version": 1}\n'
            catalog.write_bytes(original)

            def stage(_course_id, _curriculum, _prepared, staging_root):
                (staging_root / course_id).mkdir()
                return {"lessons": {}}

            def fail_catalog(*_args):
                catalog.write_bytes(b"partial")
                raise RuntimeError("catalog failure")

            with (
                patch.object(generator, "assemble_public_system_prompt"),
                patch.object(generator, "load_curriculum", return_value={}),
                patch.object(generator, "course_dir", return_value=target),
                patch.object(generator, "prepare_course", return_value=({}, [])),
                patch.object(generator, "print_audit"),
                patch.object(generator, "stage_course", side_effect=stage),
                patch.object(generator, "sync_catalog", side_effect=fail_catalog),
                patch.object(generator.common, "CATALOG_PATH", catalog),
            ):
                with self.assertRaisesRegex(RuntimeError, "catalog failure"):
                    generator.publish_course(course_id)
            self.assertFalse(target.exists())
            self.assertEqual(catalog.read_bytes(), original)

    def test_rename_failure_rolls_back_catalog(self) -> None:
        course_id = "quality-management-engineer-practical"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / course_id
            catalog = root / "catalog.json"
            original = b'{"version": 1}\n'
            catalog.write_bytes(original)

            def stage(_course_id, _curriculum, _prepared, staging_root):
                (staging_root / course_id).mkdir()
                return {"lessons": {}}

            def update_catalog(*_args):
                catalog.write_bytes(b"updated")

            real_replace = generator.os.replace

            def fail_course_rename(source, destination):
                if Path(destination) == target:
                    raise OSError("rename failure")
                return real_replace(source, destination)

            with (
                patch.object(generator, "assemble_public_system_prompt"),
                patch.object(generator, "load_curriculum", return_value={}),
                patch.object(generator, "course_dir", return_value=target),
                patch.object(generator, "prepare_course", return_value=({}, [])),
                patch.object(generator, "print_audit"),
                patch.object(generator, "stage_course", side_effect=stage),
                patch.object(generator, "sync_catalog", side_effect=update_catalog),
                patch.object(generator.os, "replace", side_effect=fail_course_rename),
                patch.object(generator.common, "CATALOG_PATH", catalog),
            ):
                with self.assertRaisesRegex(OSError, "rename failure"):
                    generator.publish_course(course_id)
            self.assertFalse(target.exists())
            self.assertEqual(catalog.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
