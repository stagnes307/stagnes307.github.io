from __future__ import annotations

import json
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import assemble_ailey_live_prompt as assembler  # noqa: E402
import run_ailey_github_codex as runner  # noqa: E402
import sanitize_ailey_github_cc as staticizer  # noqa: E402
import validation  # noqa: E402
from common import codex_artifact_quality_errors  # noqa: E402
from prompt_profiles import get_prompt_profile  # noqa: E402


COURSE_ID = "fixture-course"
COURSE_TITLE = "검증 과정"
LESSON_ID = "1-1-1-1"
LESSON_TITLE = "실제 응답 정적화"
TOPICS = ["첫 번째 토픽 원문", "두 번째 토픽 원문"]
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
                    "slug": "live-staticization",
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


def raw_cc() -> str:
    filler = " ".join(
        f"실제 모델이 만든 상세 설명 {index}."
        for index in range(1, 260)
    )
    return f"""```html
<!DOCTYPE html>
<html lang="KR">
<head>
<title>{LESSON_ID}. {LESSON_TITLE}</title>
<link rel="stylesheet" href="https://remote.invalid/main.css">
<script src="https://remote.invalid/main.js"></script>
</head>
<body>
<div id="initial-loader">Loading</div>
<main id="ai-content-placeholder" style="display:none" data-subject="시험">
<header class="header">
<h1>{LESSON_ID}. {LESSON_TITLE}</h1>
<p>{COURSE_TITLE} · {TOPICS[0]} · {TOPICS[1]}</p>
</header>
<section class="content-section">
<h2>🧭 실제 `.cc` 본문</h2>
<p><strong>핵심</strong> {filler}</p>
<table>
<caption>검증 표</caption>
<thead><tr><th scope="col">구분</th><th scope="col">설명</th></tr></thead>
<tbody><tr><th scope="row">A</th><td>내용</td></tr></tbody>
</table>
</section>
</main>
<script>document.addEventListener('DOMContentLoaded', function() {{}});</script>
</body>
</html>
```

후속 나침반은 HTML 파일 바깥의 대화 UI다.
"""


class LiveProfileTest(unittest.TestCase):
    def test_registry_records_real_codex_turns_without_custom_gpt_claim(self) -> None:
        ff = get_prompt_profile(
            staticizer.FF_PROFILE,
            artifact_kind="ff",
            producer="openai-codex",
        )
        cc = get_prompt_profile(
            staticizer.CC_PROFILE,
            artifact_kind="cc",
            producer="openai-codex",
        )
        self.assertTrue(ff["generation"]["codex_live_model_invoked"])
        self.assertFalse(ff["generation"]["upstream_custom_gpt_invoked"])
        self.assertEqual(ff["generation"]["same_context_second_turn"], ".cc")
        self.assertFalse(cc["generation"]["content_rewritten"])

    def test_exact_ff_message_contains_no_source_packet(self) -> None:
        value = assembler.build_exact_ff_message(CURRICULUM, lesson())
        self.assertEqual(
            value,
            "\n".join([
                f".ff {COURSE_TITLE}",
                "1-1. 유닛",
                "1-1-1. 그룹",
                f"{LESSON_ID}. {LESSON_TITLE}",
                f"- {TOPICS[0]}",
                f"- {TOPICS[1]}",
            ]),
        )
        self.assertNotIn("SOURCE_PACKET", value)
        context = assembler.build_runtime_context(CURRICULUM, lesson())
        self.assertEqual(context["sources"][0]["id"], "official")

    def test_model_instructions_keep_exact_user_turn_separate(self) -> None:
        with (
            patch.object(assembler, "load_curriculum", return_value=CURRICULUM),
            patch.object(assembler, "assemble_upstream_prompt", return_value="UPSTREAM\n"),
            patch.object(assembler, "get_prompt_profile"),
        ):
            model_instructions, exact = assembler.assemble_live_codex_prompt(
                COURSE_ID,
                LESSON_ID,
            )
        self.assertIn("<<<PINNED_GITHUB_AILEY_PROMPT", model_instructions)
        self.assertIn("<<<USER_AUTHORIZED_LIVE_PROFILE>>>", model_instructions)
        self.assertNotIn("<<<EXACT_USER_MESSAGE>>>", model_instructions)
        self.assertTrue(exact.startswith(f".ff {COURSE_TITLE}\n"))

    def test_codex_transport_uses_model_instruction_file_and_exact_stdin(self) -> None:
        instructions = Path("C:/temp/ailey-model-instructions.md")
        command = runner._codex_commands(
            "codex",
            model="gpt-5.6-sol",
            reasoning="low",
            ff_path=Path("ff.raw.md"),
            cc_path=Path("cc.raw.txt"),
            model_instructions_path=instructions,
        )
        self.assertIn("--strict-config", command)
        expected_config = "model_instructions_file=" + json.dumps(str(instructions))
        self.assertIn(expected_config, command)
        self.assertEqual(command[-1], "-")

    def test_resumable_ff_requires_current_instructions_user_and_model(self) -> None:
        current_instructions = "CURRENT MODEL INSTRUCTIONS\n"
        current_user = ".ff exact lesson"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            attempt = root / "attempt-001"
            attempt.mkdir()
            (attempt / "ff.raw.md").write_text("validated FF", encoding="utf-8")
            (attempt / "model-instructions.md").write_text(
                current_instructions,
                encoding="utf-8",
                newline="\n",
            )
            digest = hashlib.sha256(current_instructions.encode("utf-8")).hexdigest()
            (attempt / "model-instructions.sha256").write_text(
                digest + "\n",
                encoding="utf-8",
            )
            (attempt / "exact-user-message.txt").write_text(
                current_user + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (attempt / "status.json").write_text(
                json.dumps({
                    "phase": "ff-complete",
                    "thread_id": "123e4567-e89b-42d3-a456-426614174000",
                    "model": "gpt-5.6-sol",
                    "reasoning": "low",
                }),
                encoding="utf-8",
            )
            job = runner.LessonJob(COURSE_ID, CURRICULUM, lesson())
            with patch.object(
                runner,
                "assemble_live_codex_prompt",
                return_value=(current_instructions, current_user),
            ):
                self.assertEqual(
                    runner._find_resumable_ff(
                        job,
                        root,
                        model="gpt-5.6-sol",
                        reasoning="low",
                    ),
                    attempt,
                )
                (attempt / "exact-user-message.txt").write_text(
                    ".ff stale lesson\n",
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIsNone(
                    runner._find_resumable_ff(
                        job,
                        root,
                        model="gpt-5.6-sol",
                        reasoning="low",
                    )
                )

    def test_transaction_journal_recovers_prepared_and_finalizes_committed(self) -> None:
        for state, expected in (("prepared", "old"), ("committed", "new")):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temp_dir:
                folder = Path(temp_dir)
                target = folder / "ff.md"
                stage = folder / ".ff.stage"
                backup = folder / ".ff.backup"
                target.write_text("new", encoding="utf-8")
                stage.write_text("staged", encoding="utf-8")
                backup.write_text("old", encoding="utf-8")
                marker = {
                    "version": 1,
                    "state": state,
                    "entries": [{
                        "target": target.name,
                        "stage": stage.name,
                        "backup": backup.name,
                        "had_original": True,
                    }],
                }
                (folder / runner.TRANSACTION_MARKER).write_text(
                    json.dumps(marker),
                    encoding="utf-8",
                )
                self.assertTrue(runner._recover_artifact_transaction(folder))
                self.assertEqual(target.read_text(encoding="utf-8"), expected)
                self.assertFalse(stage.exists())
                self.assertFalse(backup.exists())
                self.assertFalse((folder / runner.TRANSACTION_MARKER).exists())

    def test_prepared_recovery_is_idempotent_after_mid_restore_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            entries = []
            for name in ("ff.md", "cc.html"):
                target = folder / name
                stage = folder / f".{name}.stage"
                backup = folder / f".{name}.backup"
                target.write_text(f"new-{name}", encoding="utf-8")
                stage.write_text(f"stage-{name}", encoding="utf-8")
                backup.write_text(f"old-{name}", encoding="utf-8")
                entries.append({
                    "target": target.name,
                    "stage": stage.name,
                    "backup": backup.name,
                    "had_original": True,
                })
            marker_path = folder / runner.TRANSACTION_MARKER
            marker_path.write_text(
                json.dumps({"version": 1, "state": "prepared", "entries": entries}),
                encoding="utf-8",
            )
            real_copy = runner.shutil.copyfile
            calls = 0

            def fail_second_copy(source: Path, target: Path) -> str:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected recovery interruption")
                return str(real_copy(source, target))

            with (
                patch.object(runner.shutil, "copyfile", side_effect=fail_second_copy),
                self.assertRaises(OSError),
            ):
                runner._recover_artifact_transaction(folder)
            self.assertTrue(marker_path.exists())
            self.assertTrue(all((folder / entry["backup"]).exists() for entry in entries))
            self.assertTrue(runner._recover_artifact_transaction(folder))
            self.assertEqual((folder / "ff.md").read_text(encoding="utf-8"), "old-ff.md")
            self.assertEqual((folder / "cc.html").read_text(encoding="utf-8"), "old-cc.html")

    def test_committed_missing_target_rolls_back_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            entries = []
            for name in ("ff.md", "cc.html", "meta.json"):
                target = folder / name
                stage = folder / f".{name}.stage"
                backup = folder / f".{name}.backup"
                if name != "meta.json":
                    target.write_text(f"new-{name}", encoding="utf-8")
                stage.write_text(f"stage-{name}", encoding="utf-8")
                backup.write_text(f"old-{name}", encoding="utf-8")
                entries.append({
                    "target": target.name,
                    "stage": stage.name,
                    "backup": backup.name,
                    "had_original": True,
                })
            (folder / runner.TRANSACTION_MARKER).write_text(
                json.dumps({"version": 1, "state": "committed", "entries": entries}),
                encoding="utf-8",
            )
            self.assertTrue(runner._recover_artifact_transaction(folder))
            for name in ("ff.md", "cc.html", "meta.json"):
                self.assertEqual(
                    (folder / name).read_text(encoding="utf-8"),
                    f"old-{name}",
                )

    def test_recovery_clears_marker_before_best_effort_backup_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            target = folder / "ff.md"
            stage = folder / ".ff.stage"
            backup = folder / ".ff.backup"
            target.write_text("new", encoding="utf-8")
            stage.write_text("stage", encoding="utf-8")
            backup.write_text("old", encoding="utf-8")
            marker_path = folder / runner.TRANSACTION_MARKER
            marker_path.write_text(
                json.dumps({
                    "version": 1,
                    "state": "prepared",
                    "entries": [{
                        "target": target.name,
                        "stage": stage.name,
                        "backup": backup.name,
                        "had_original": True,
                    }],
                }),
                encoding="utf-8",
            )
            real_unlink = Path.unlink

            def fail_backup_cleanup(path: Path, *args: object, **kwargs: object) -> None:
                if path == backup:
                    raise OSError("injected cleanup failure")
                real_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", new=fail_backup_cleanup):
                self.assertTrue(runner._recover_artifact_transaction(folder))
            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertFalse(marker_path.exists())
            self.assertTrue(backup.exists())


class StaticizerTest(unittest.TestCase):
    def test_preserves_live_body_and_removes_only_unsafe_shell(self) -> None:
        result = staticizer.staticize_cc_response(
            raw_cc(),
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        self.assertIn("실제 모델이 만든 상세 설명 259.", result)
        self.assertIn("검증 표", result)
        self.assertNotIn("remote.invalid", result)
        self.assertNotRegex(result, re.compile(r"<script\b", re.IGNORECASE))
        main_tag = re.search(
            r'<main\b[^>]*id="ai-content-placeholder"[^>]*>',
            result,
            re.IGNORECASE,
        )
        self.assertIsNotNone(main_tag)
        self.assertNotIn("display:none", main_tag.group(0).replace(" ", ""))
        self.assertIn('<html lang="ko">', result)
        self.assertIn(f'name="prompt-profile" content="{staticizer.CC_PROFILE}"', result)
        self.assertIn('name="source-turn" content=".cc-after-.ff-same-context"', result)
        self.assertIn("adapted by OpenAI Codex", result)
        self.assertFalse(codex_artifact_quality_errors("cc", result, TOPICS))
        self.assertFalse(validation.live_ailey_cc_errors(result, CURRICULUM, lesson()))

    def test_live_cc_validator_requires_audit_markers(self) -> None:
        result = staticizer.staticize_cc_response(
            raw_cc(),
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        broken = result.replace(
            '<meta name="source-turn" content=".cc-after-.ff-same-context">',
            "",
        )
        self.assertTrue(validation.live_ailey_cc_errors(broken, CURRICULUM, lesson()))

    def test_live_cc_validator_requires_identity_in_visible_main(self) -> None:
        result = staticizer.staticize_cc_response(
            raw_cc(),
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        broken = result.replace(COURSE_TITLE, "과정 누락", 1)
        self.assertTrue(validation.live_ailey_cc_errors(broken, CURRICULUM, lesson()))

    def test_live_cc_validator_rejects_residual_main_raw_text_tag(self) -> None:
        result = staticizer.staticize_cc_response(
            raw_cc(),
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        broken = result.replace(
            '<main id="ai-content-placeholder"',
            '<main id="ai-content-placeholder"><style/><span hidden="hidden"',
            1,
        )
        self.assertTrue(validation.live_ailey_cc_errors(broken, CURRICULUM, lesson()))

    def test_rejects_missing_raw_topic_instead_of_synthesizing_it(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing exact lesson identity/topics"):
            staticizer.staticize_cc_response(
                raw_cc().replace(TOPICS[1], "누락됨"),
                course_id=COURSE_ID,
                course_title=COURSE_TITLE,
                lesson_id=LESSON_ID,
                lesson_title=LESSON_TITLE,
                topics=TOPICS,
            )

    def test_rejects_staticization_that_would_drop_visible_body_text(self) -> None:
        unsafe = raw_cc().replace(
            "<section class=\"content-section\">",
            '<section class="content-section"><iframe>보존해야 할 본문</iframe>',
            1,
        )
        with self.assertRaisesRegex(ValueError, "changed the normalized visible"):
            staticizer.staticize_cc_response(
                unsafe,
                course_id=COURSE_ID,
                course_title=COURSE_TITLE,
                lesson_id=LESSON_ID,
                lesson_title=LESSON_TITLE,
                topics=TOPICS,
            )

    def test_rejects_self_closing_raw_text_tag(self) -> None:
        unsafe = raw_cc().replace(
            "<section class=\"content-section\">",
            '<section class="content-section"><style/>',
            1,
        )
        with self.assertRaisesRegex(ValueError, "unsafe raw-text or active tag"):
            staticizer.staticize_cc_response(
                unsafe,
                course_id=COURSE_ID,
                course_title=COURSE_TITLE,
                lesson_id=LESSON_ID,
                lesson_title=LESSON_TITLE,
                topics=TOPICS,
            )

    def test_rejects_legacy_raw_text_tags(self) -> None:
        for tag in ("noembed", "noframes"):
            unsafe = raw_cc().replace(
                "<section class=\"content-section\">",
                f'<section class="content-section"><{tag}/>',
                1,
            )
            with self.subTest(tag=tag), self.assertRaisesRegex(
                ValueError,
                "unsafe raw-text or active tag",
            ):
                staticizer.staticize_cc_response(
                    unsafe,
                    course_id=COURSE_ID,
                    course_title=COURSE_TITLE,
                    lesson_id=LESSON_ID,
                    lesson_title=LESSON_TITLE,
                    topics=TOPICS,
                )

    def test_preserves_image_alt_as_inert_visible_text(self) -> None:
        raw = raw_cc().replace(
            "<section class=\"content-section\">",
            '<section class="content-section"><img src="https://remote.invalid/a.png" alt="공정 흐름 설명">',
            1,
        )
        result = staticizer.staticize_cc_response(
            raw,
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        self.assertIn('<span class="image-alt">공정 흐름 설명</span>', result)
        self.assertNotIn("remote.invalid", result)

    def test_extracts_only_first_complete_html_document(self) -> None:
        raw = raw_cc() + "\n<!doctype html><html><body>second</body></html>"
        extracted = staticizer.extract_html_response(raw)
        self.assertNotIn("second", extracted)

    def test_ff_gate_requires_identity_format_and_study_sections(self) -> None:
        source = (
            f"# {LESSON_ID}. {LESSON_TITLE}\n\n"
            + "\n\n".join(
                f"## {index}. 구조\n\n**핵심** {TOPICS[index % 2]} "
                + "상세 설명입니다. " * 180
                for index in range(1, 7)
            )
            + f"\n\n### 확인 문제\n문제\n\n### 정답과 해설\n정답\n\n### 요약\n요약\n{TOPICS[0]}\n{TOPICS[1]}\n"
        )
        self.assertFalse(runner._ff_errors(source, lesson()))
        self.assertTrue(runner._ff_errors(source.replace(f"# {LESSON_ID}.", "### 다른 제목", 1), lesson()))


if __name__ == "__main__":
    unittest.main()
