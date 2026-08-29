from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import call, patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import assemble_ailey_visual_prompt as assembler  # noqa: E402
import run_ailey_visual_cc as runner  # noqa: E402


COURSE_ID = "fixture-visual-course"
COURSE_TITLE = "시각화 검증 과정"
LESSON_ID = "1-1-1-1"
LESSON_TITLE = "위험 흐름과 통계 판정"
TOPICS = ["위험 원인과 결과의 관계", "통계 검정 절차"]
CURRICULUM = {
    "version": 1,
    "course_id": COURSE_ID,
    "title": COURSE_TITLE,
    "verified_at": "2026-08-29",
    "sources": [{
        "id": "official",
        "title": "공식 기준",
        "authority": "검증 기관",
        "url": "https://example.invalid/official",
        "retrieved_at": "2026-08-29",
    }],
    "sections": [{
        "id": "1",
        "title": "섹션",
        "units": [{
            "id": "1-1",
            "title": "유닛",
            "lessons": [{
                "id": "1-1-1",
                "title": "그룹",
                "sublessons": [{
                    "id": LESSON_ID,
                    "title": LESSON_TITLE,
                    "slug": "visual-transaction",
                    "topics": TOPICS,
                    "lesson_type": "concept",
                    "supplemental": False,
                    "official_basis": ["섹션 > 유닛 > 그룹"],
                    "source_refs": ["official"],
                }],
            }],
        }],
    }],
}


def lesson() -> dict:
    return assembler.find_lesson(CURRICULUM, LESSON_ID)


def artifact_record(path: Path, profile: str) -> dict[str, str]:
    return {
        "producer": "openai-codex",
        "prompt_profile": profile,
        "generated_at": "2026-08-29T12:34:56+09:00",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def write_fixture_artifacts(folder: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    ff_path = folder / "ff.md"
    cc_path = folder / "cc.html"
    meta_path = folder / "meta.json"
    ff_path.write_bytes(b"\xef\xbb\xbf# preserved FF\r\n\r\nexact bytes\r\n")
    cc_path.write_bytes(b"<!doctype html>\r\n<p>old CC</p>\r\n")
    ff_record = artifact_record(
        ff_path,
        "ailey-bailey-public-8a36e77d-ff-codex-live-v1",
    )
    meta = {
        "version": 2,
        "course_id": COURSE_ID,
        "lesson_id": LESSON_ID,
        "title": LESSON_TITLE,
        "slug": "visual-transaction",
        "section_id": "1",
        "section_title": "섹션",
        "unit_id": "1-1",
        "unit_title": "유닛",
        "lesson_group_id": "1-1-1",
        "lesson_group_title": "그룹",
        "topics": TOPICS,
        "artifacts": {
            "ff": ff_record,
            "cc": artifact_record(
                cc_path,
                "ailey-bailey-public-8a36e77d-cc-codex-live-static-v1",
            ),
        },
        "published_at": "2026-08-29T12:34:56+09:00",
        "status": "published",
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return ff_path, cc_path, meta_path, ff_record


class VisualPromptAssemblyTest(unittest.TestCase):
    def test_exact_initial_ff_and_visual_profile_markers_are_separate(self) -> None:
        expected_ff = "\n".join([
            f".ff {COURSE_TITLE}",
            "1-1. 유닛",
            "1-1-1. 그룹",
            f"{LESSON_ID}. {LESSON_TITLE}",
            f"- {TOPICS[0]}",
            f"- {TOPICS[1]}",
        ])
        with tempfile.TemporaryDirectory() as temporary:
            spec_path = Path(temporary) / "visual-spec.md"
            spec_path.write_text(
                "STATIC VISUAL V2 TEST CONTRACT\n",
                encoding="utf-8",
            )
            with (
                patch.object(assembler, "load_curriculum", return_value=CURRICULUM),
                patch.object(assembler, "assemble_upstream_prompt", return_value="PINNED\n"),
                patch.object(assembler, "VISUAL_SPEC_PATH", spec_path),
                patch.object(assembler, "get_prompt_profile") as get_profile,
            ):
                instructions, exact_ff = assembler.assemble_visual_codex_prompt(
                    COURSE_ID,
                    LESSON_ID,
                )

        self.assertEqual(exact_ff, expected_ff)
        self.assertNotIn(expected_ff, instructions)
        self.assertIn("<<<PINNED_GITHUB_AILEY_PROMPT", instructions)
        self.assertIn("<<<USER_AUTHORIZED_STATIC_VISUAL_PROFILE>>>", instructions)
        self.assertIn("STATIC VISUAL V2 TEST CONTRACT", instructions)
        self.assertIn(assembler.FF_VISUAL_PROFILE, instructions)
        self.assertIn(assembler.CC_VISUAL_PROFILE, instructions)
        self.assertIn('"visual_design_brief": {', instructions)
        self.assertIn("back to placeholders", instructions)
        self.assertIn("Never output HTML or a doctype on that turn", instructions)
        self.assertIn("Only when the same thread later receives", instructions)
        self.assertIn(f"`# {LESSON_ID}. `", instructions)
        self.assertIn(
            f'<p class="official-title">{LESSON_TITLE}</p>',
            instructions,
        )
        self.assertIn("directly include both `aria-label`", instructions)
        self.assertIn("never set `min-width` on an", instructions)
        self.assertIn("must render at least 10px high", instructions)
        self.assertIn("viewBox-width / smallest visible", instructions)
        self.assertIn("label-free gutters and terminate", instructions)
        self.assertIn("formulas in a separate legend", instructions)
        self.assertIn("both 360px and 390px viewports", instructions)
        self.assertIn("at least 0.5em outside all text boxes", instructions)
        self.assertIn("eyebrow paragraphs do not count", instructions)
        self.assertEqual(
            get_profile.call_args_list,
            [
                call(
                    assembler.FF_VISUAL_PROFILE,
                    artifact_kind="ff",
                    producer="openai-codex",
                ),
                call(
                    assembler.CC_VISUAL_PROFILE,
                    artifact_kind="cc",
                    producer="openai-codex",
                ),
            ],
        )

    def test_visual_design_brief_is_deterministic_and_lesson_scoped(self) -> None:
        current_lesson = lesson()
        first = assembler.build_visual_design_brief(COURSE_ID, current_lesson)
        second = assembler.build_visual_design_brief(COURSE_ID, dict(current_lesson))
        expected_seed = hashlib.sha256(
            f"{COURSE_ID}:{LESSON_ID}".encode("utf-8")
        ).digest()[:8].hex()

        self.assertEqual(first, second)
        self.assertEqual(first["seed"], expected_seed)
        self.assertIn("위험 장벽 또는 원인-결과 경로", first["suggested_visual_forms"])
        self.assertIn("좌표축·분포·계산 구조도", first["suggested_visual_forms"])
        self.assertEqual(len(first["palette"]), 4)

        other = {**current_lesson, "id": "1-1-1-2"}
        self.assertNotEqual(
            first["seed"],
            assembler.build_visual_design_brief(COURSE_ID, other)["seed"],
        )


class VisualPairTransactionTest(unittest.TestCase):
    def test_definite_cc_interruption_restores_resumable_ff_status(self) -> None:
        job = runner.LessonJob(COURSE_ID, CURRICULUM, lesson())
        thread_id = "12345678-1234-4234-9234-123456789abc"
        for exception in (
            runner.GlobalLimitError("account limit"),
            runner.CancelledGeneration("batch stopped"),
        ):
            with self.subTest(exception=type(exception).__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                status_path = root / "status.json"
                with (
                    patch.object(runner, "_run_turn", side_effect=exception),
                    self.assertRaises(type(exception)),
                ):
                    runner._run_cc_turn_with_resumable_status(
                        job,
                        status_path=status_path,
                        command=["codex", "exec", "resume", thread_id],
                        output_path=root / "cc.raw.txt",
                        log_dir=root / "transport",
                        timeout_seconds=600,
                        stop_event=threading.Event(),
                        thread_id=thread_id,
                        ff_usage={"input_tokens": 12},
                        model="gpt-5.6-sol",
                        reasoning="medium",
                        resumed_after_ff=True,
                    )
                status = json.loads(status_path.read_text(encoding="utf-8"))
                self.assertEqual(status["phase"], "ff-complete")
                self.assertEqual(status["thread_id"], thread_id)
                self.assertEqual(status["ff_usage"], {"input_tokens": 12})
                self.assertTrue(status["resumed_after_ff"])

    def test_shared_artifact_lock_blocks_a_second_runner(self) -> None:
        with runner.artifact_generation_lock(COURSE_ID, LESSON_ID):
            with self.assertRaisesRegex(RuntimeError, "another Study Factory runner"):
                with runner.artifact_generation_lock(COURSE_ID, LESSON_ID):
                    self.fail("nested lock unexpectedly succeeded")

    def test_ff_context_hash_uses_the_exact_published_canonical_bytes(self) -> None:
        variants = ("FF body", "FF body\n", "FF body\n\n  \n")
        canonical = "FF body\n"
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        for source in variants:
            with self.subTest(source=repr(source)):
                published = runner._canonical_ff_source(source)
                self.assertEqual(published, canonical)
                self.assertEqual(
                    hashlib.sha256(published.encode("utf-8")).hexdigest(),
                    expected,
                )

    def test_success_publishes_same_thread_ff_and_cc_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            ff_path, cc_path, meta_path, ff_record = write_fixture_artifacts(folder)
            job = runner.LessonJob(COURSE_ID, CURRICULUM, lesson())
            new_ff = "# 1-1-1-1. 새 시각 학습 제목\n\n새 FF 본문"

            with patch.object(runner, "lesson_dir", return_value=folder):
                runner._record_visual_pair(
                    job,
                    new_ff,
                    "<!doctype html>\n<p>new CC</p>",
                )

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(ff_path.read_text(encoding="utf-8"), new_ff + "\n")
            self.assertNotEqual(meta["artifacts"]["ff"], ff_record)
            self.assertEqual(
                meta["artifacts"]["ff"]["prompt_profile"],
                assembler.FF_VISUAL_PROFILE,
            )
            self.assertEqual(cc_path.read_text(encoding="utf-8"), "<!doctype html>\n<p>new CC</p>\n")
            self.assertEqual(
                meta["artifacts"]["cc"]["prompt_profile"],
                assembler.CC_VISUAL_PROFILE,
            )
            self.assertEqual(
                meta["artifacts"]["cc"]["sha256"],
                hashlib.sha256(cc_path.read_bytes()).hexdigest(),
            )
            self.assertFalse((folder / runner.TRANSACTION_MARKER).exists())
            self.assertFalse(list(folder.glob(".*.stage")))
            self.assertFalse(list(folder.glob(".*.backup")))

    def test_meta_replace_failure_rolls_back_cc_and_meta_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            ff_path, cc_path, meta_path, _ = write_fixture_artifacts(folder)
            before_ff = ff_path.read_bytes()
            before_cc = cc_path.read_bytes()
            before_meta = meta_path.read_bytes()
            real_replace = os.replace
            injected = False

            def fail_meta_publish_once(source: Path | str, target: Path | str) -> None:
                nonlocal injected
                source_path = Path(source)
                target_path = Path(target)
                if (
                    not injected
                    and target_path == meta_path
                    and source_path.name.startswith(".meta.json.")
                    and source_path.name.endswith(".stage")
                ):
                    injected = True
                    raise OSError("injected meta replacement failure")
                real_replace(source, target)

            job = runner.LessonJob(COURSE_ID, CURRICULUM, lesson())
            with (
                patch.object(runner, "lesson_dir", return_value=folder),
                patch.object(runner.os, "replace", side_effect=fail_meta_publish_once),
                self.assertRaisesRegex(OSError, "injected meta replacement failure"),
            ):
                runner._record_visual_pair(
                    job,
                    "# 1-1-1-1. 새 시각 학습 제목\n\n새 FF 본문",
                    "<!doctype html>\n<p>new CC</p>",
                )

            self.assertTrue(injected)
            self.assertEqual(ff_path.read_bytes(), before_ff)
            self.assertEqual(cc_path.read_bytes(), before_cc)
            self.assertEqual(meta_path.read_bytes(), before_meta)
            self.assertFalse((folder / runner.TRANSACTION_MARKER).exists())
            self.assertFalse(list(folder.glob(".*.stage")))
            self.assertFalse(list(folder.glob(".*.backup")))
            self.assertFalse(list(folder.glob(".*.recovery.tmp")))


if __name__ == "__main__":
    unittest.main()
