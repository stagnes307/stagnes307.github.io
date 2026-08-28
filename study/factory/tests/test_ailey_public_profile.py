from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from copy import deepcopy
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import ailey_public_profile as profile  # noqa: E402
import assemble_ailey_prompt as assembler  # noqa: E402
import render_ailey_public_cc as renderer  # noqa: E402
from prompt_profiles import (  # noqa: E402
    get_prompt_profile,
    prompt_profile_registry_errors,
)


COURSE_ID = "fixture-course"
LESSON_ID = "1-1-1-1"
LESSON_TITLE = "공개 프롬프트 안전 변환"
TOPICS = ["첫 번째 핵심 토픽", "두 번째 핵심 토픽"]
OFFICIAL_URL = "https://example.invalid/official"
CURRICULUM = {
    "version": 1,
    "course_id": COURSE_ID,
    "title": "공개 프롬프트 시험 과정",
    "certification": "검증용 자격",
    "mode": "written",
    "authority": "검증 기관",
    "verified_at": "2026-08-28",
    "sources": [{
        "id": "fixture-source",
        "title": "검증 기준",
        "authority": "검증 기관",
        "url": OFFICIAL_URL,
        "effective_from": "2026-01-01",
        "effective_to": None,
        "retrieved_at": "2026-08-28",
    }],
    "sections": [{
        "id": "1",
        "title": "시험 섹션",
        "units": [{
            "id": "1-1",
            "title": "시험 유닛",
            "lessons": [{
                "id": "1-1-1",
                "title": "시험 그룹",
                "sublessons": [{
                    "id": LESSON_ID,
                    "title": LESSON_TITLE,
                    "slug": "public-prompt-safe-rendering",
                    "topics": TOPICS,
                    "lesson_type": "concept",
                    "supplemental": False,
                    "source_refs": ["fixture-source"],
                    "official_basis": ["시험 섹션 > 시험 유닛 > 시험 그룹"],
                }],
            }],
        }],
    }],
}

H2_EMOJIS = ["😀", "😃", "😄", "😁", "😆"]
H3_EMOJIS = [
    "🐶", "🐱", "🐭",
    "🐹", "🐰", "🦊",
    "🐻", "🐼", "🐨",
    "🐯", "🦁", "🐮",
    "🐷", "🐸", "🐵",
]
H3_TITLES = [
    "학습 목표", "핵심 정의", "용어 경계",
    "작동 원리", "처리 순서", "인과 관계",
    "작은 예시", "비교 기준", "경계 사례",
    "판별 절차", "시험 함정", "실전 점검",
    "통합 적용", "확인 문제와 정답·해설", "요약",
]


def fixture_lesson() -> dict:
    return renderer.find_lesson(CURRICULUM, LESSON_ID)


def fixture_ff(*, sentence_count: int = 15) -> str:
    lines = [f"# {LESSON_ID}. {LESSON_TITLE}", ""]
    h3_index = 0
    for section_index, h2_emoji in enumerate(H2_EMOJIS, start=1):
        lines.extend([
            f"## {h2_emoji} {section_index}부 학습 프레임",
            "",
        ])
        for local_index in range(3):
            title = H3_TITLES[h3_index]
            emoji = H3_EMOJIS[h3_index]
            topic = TOPICS[h3_index % len(TOPICS)]
            sentences = [
                (
                    f"{topic}에 관한 {section_index}-{local_index + 1}-"
                    f"{number} 설명은 정의와 원리와 예시와 비교 기준을 "
                    "한 흐름으로 연결합니다."
                )
                for number in range(1, sentence_count + 1)
            ]
            lines.extend([
                f"### {emoji} {title}",
                "",
                " ".join(sentences),
                "",
            ])
            h3_index += 1
    return "\n".join(lines)


class AileyVendorAndRegistryTest(unittest.TestCase):
    def test_pinned_vendor_manifest_and_assembly(self) -> None:
        self.assertFalse(profile.vendor_snapshot_errors())
        manifest = profile.load_vendor_manifest()
        self.assertEqual(
            manifest["commit"],
            "8a36e77d025bb9c258bfeaf8587424783140b185",
        )
        self.assertEqual(len(manifest["assembly_order"]), 16)
        self.assertEqual(
            manifest["assembly_order"],
            sorted(manifest["assembly_order"]),
        )
        self.assertEqual(manifest["license"]["spdx"], "CC-BY-NC-SA-4.0")
        for record in [*manifest["files"], manifest["license"]]:
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            manifest["text_normalization"],
            "none; byte-identical upstream Git blobs",
        )

        assembled = profile.assemble_upstream_prompt()
        first = manifest["assembly_order"][0]
        expected_start = (
            profile.AILEY_VENDOR_ROOT / first
        ).read_text(encoding="utf-8").strip()
        self.assertTrue(assembled.startswith(expected_start))
        self.assertIn("Ailey & Bailey Canvas", assembled)
        self.assertIn("~했어?", assembled)
        self.assertIn("[M-C] Canvas Engine", assembled)

    def test_registry_enforces_kind_and_producer(self) -> None:
        self.assertFalse(prompt_profile_registry_errors())
        ff = get_prompt_profile(
            profile.AILEY_FF_PROFILE,
            artifact_kind="ff",
            producer="openai-codex",
        )
        self.assertEqual(ff["upstream"]["commit"], profile.AILEY_COMMIT)
        with self.assertRaises(ValueError):
            get_prompt_profile(profile.AILEY_FF_PROFILE, artifact_kind="cc")
        cc = get_prompt_profile(
            profile.AILEY_CC_PROFILE,
            artifact_kind="cc",
        )
        self.assertEqual(cc["license"]["spdx"], "CC-BY-NC-SA-4.0")
        for public_profile in (ff, cc):
            self.assertEqual(
                public_profile["generation"],
                {
                    "method": "deterministic-study-factory-compatibility",
                    "implements": "pinned-public-prompt-output-contract",
                    "upstream_llm_invoked": False,
                },
            )

    def test_public_profile_fingerprint_covers_pinned_prompt_and_overlay(self) -> None:
        self.assertEqual(
            profile.public_profile_fingerprint(),
            "878ff66b8ea0d71f413f1daef9af3dc6467cbd7074d5fdc7f4d4de8bb44f05e9",
        )
        expected = profile.assemble_public_system_prompt().encode("utf-8")
        self.assertEqual(
            profile.public_profile_fingerprint(),
            hashlib.sha256(expected).hexdigest(),
        )


class AileyLiteralFFGateTest(unittest.TestCase):
    def test_accepts_exact_five_by_three_contract(self) -> None:
        source = fixture_ff()
        self.assertGreaterEqual(len(source), 4_000)
        self.assertFalse(
            profile.ailey_public_ff_quality_errors(
                source,
                TOPICS,
                lesson_id=LESSON_ID,
                lesson_title=LESSON_TITLE,
            )
        )

    def test_rejects_wrong_shape_sentence_count_and_duplicate_emoji(self) -> None:
        source = fixture_ff()
        missing_section = source.split("## 😆", 1)[0]
        shape_errors = profile.ailey_public_ff_quality_errors(
            missing_section,
            TOPICS,
        )
        self.assertTrue(
            any("exactly five H2" in error for error in shape_errors)
        )
        short_errors = profile.ailey_public_ff_quality_errors(
            fixture_ff(sentence_count=14),
            TOPICS,
        )
        self.assertTrue(
            any("15-20 sentences" in error for error in short_errors)
        )
        duplicate_errors = profile.ailey_public_ff_quality_errors(
            source.replace("## 😃", "## 😀", 1),
            TOPICS,
        )
        self.assertIn(
            "all twenty H2/H3 heading emojis must be unique",
            duplicate_errors,
        )

    def test_rejects_missing_topic_and_wrong_final_roles(self) -> None:
        source = fixture_ff()
        topic_errors = profile.ailey_public_ff_quality_errors(
            source.replace(TOPICS[1], "바뀐 토픽"),
            TOPICS,
        )
        self.assertTrue(any("curriculum topic" in error for error in topic_errors))
        role_errors = profile.ailey_public_ff_quality_errors(
            source.replace("통합 적용", "별도 연습", 1),
            TOPICS,
        )
        self.assertIn(
            "fifth H2 first H3 must be the 통합 적용 section",
            role_errors,
        )

    def test_rejects_nonparagraph_first_block_and_raw_chrome(self) -> None:
        source = fixture_ff()
        first_sentence = (
            f"{TOPICS[0]}에 관한 1-1-1 설명은 정의와 원리와 예시와 "
            "비교 기준을 한 흐름으로 연결합니다."
        )
        list_first = source.replace(first_sentence, "- " + first_sentence, 1)
        errors = profile.ailey_public_ff_quality_errors(list_first, TOPICS)
        self.assertTrue(
            any("plain paragraph" in error for error in errors)
        )
        chrome = source + "\n.COMPASS NAVIGATION\n.cc\n"
        chrome_errors = profile.ailey_public_ff_quality_errors(chrome, TOPICS)
        self.assertTrue(any("raw .cc/.ccc" in error for error in chrome_errors))
        self.assertTrue(any("navigation" in error for error in chrome_errors))


class AileySafeRendererTest(unittest.TestCase):
    def test_safe_deterministic_render_has_visible_attribution(self) -> None:
        source = fixture_ff()
        lesson = fixture_lesson()
        first = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            lesson,
            source,
        )
        second = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            lesson,
            source,
        )
        self.assertEqual(first, second)
        self.assertFalse(
            profile.raw_upstream_cc_errors(
                first,
                TOPICS,
                allowed_urls=[OFFICIAL_URL],
            )
        )
        self.assertTrue(profile.raw_upstream_cc_errors(first, TOPICS))
        self.assertEqual(
            len(re.findall(r"<h1\b", first, re.IGNORECASE)),
            1,
        )
        self.assertIn('html lang="ko"', first)
        self.assertIn('name="prompt-profile"', first)
        self.assertIn(profile.AILEY_CC_PROFILE, first)
        self.assertIn(profile.public_profile_fingerprint(), first)
        self.assertIn(
            'name="generation-method" '
            'content="deterministic-study-factory-compatibility"',
            first,
        )
        self.assertIn(
            'name="upstream-llm-invoked" content="false"',
            first,
        )
        self.assertIn('id="official-sources-title">공식 출처</h2>', first)
        self.assertIn("검증 기준", first)
        self.assertIn("검증 기관", first)
        self.assertIn("2026-08-28", first)
        self.assertIn("2026-01-01부터", first)
        self.assertIn(
            f'href="{OFFICIAL_URL}" target="_blank" '
            'rel="noopener noreferrer"',
            first,
        )
        self.assertEqual(first.count(OFFICIAL_URL), 1)
        self.assertIn("fewweekslater (Ray You)", first)
        self.assertIn("adapted by OpenAI Codex", first)
        self.assertIn("CC BY-NC-SA 4.0", first)
        self.assertIn("제3자 고지와 변경 사항", first)
        self.assertIn("실제 upstream LLM 호출 기록이 아닙니다", first)
        self.assertNotRegex(first.lower(), r"<script\b")
        self.assertNotRegex(
            first.replace(OFFICIAL_URL, ""),
            r"(?:https?|ftp)://",
        )

    def test_only_selected_curriculum_sources_are_rendered(self) -> None:
        curriculum = deepcopy(CURRICULUM)
        curriculum["sources"].append({
            "id": "unselected-source",
            "title": "선택되지 않은 기준",
            "authority": "다른 기관",
            "url": "https://other.invalid/unselected",
            "effective_from": None,
            "effective_to": "2025-12-31",
            "retrieved_at": "2026-08-27",
        })
        document = renderer.render_cc_document(
            COURSE_ID,
            curriculum,
            renderer.find_lesson(curriculum, LESSON_ID),
            fixture_ff(),
        )
        self.assertIn(OFFICIAL_URL, document)
        self.assertNotIn("https://other.invalid/unselected", document)
        self.assertNotIn("선택되지 않은 기준", document)

    def test_html_escaped_official_url_is_masked_after_context_check(self) -> None:
        curriculum = deepcopy(CURRICULUM)
        escaped_url = "https://example.invalid/official?part=1&view=full"
        curriculum["sources"][0]["url"] = escaped_url
        document = renderer.render_cc_document(
            COURSE_ID,
            curriculum,
            renderer.find_lesson(curriculum, LESSON_ID),
            fixture_ff(),
        )
        self.assertIn(
            'href="https://example.invalid/official?part=1&amp;view=full"',
            document,
        )
        self.assertFalse(
            profile.raw_upstream_cc_errors(
                document,
                TOPICS,
                allowed_urls=[escaped_url],
            )
        )

    def test_allowlist_rejects_random_urls_and_asset_contexts(self) -> None:
        document = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            fixture_lesson(),
            fixture_ff(),
        )
        random_url = document.replace(
            OFFICIAL_URL,
            "https://attacker.invalid/random",
            1,
        )
        random_errors = profile.raw_upstream_cc_errors(
            random_url,
            TOPICS,
            allowed_urls=[OFFICIAL_URL],
        )
        self.assertTrue(
            any("unapproved remote URL" in error for error in random_errors)
        )

        image = document.replace(
            "</main>",
            f'<img src="{OFFICIAL_URL}" alt="unsafe"></main>',
            1,
        )
        image_errors = profile.raw_upstream_cc_errors(
            image,
            TOPICS,
            allowed_urls=[OFFICIAL_URL],
        )
        self.assertTrue(
            any("unapproved remote URL in <img> src" in error for error in image_errors)
        )

        style = document.replace(
            "</style>",
            f".unsafe{{background:url({OFFICIAL_URL})}}</style>",
            1,
        )
        style_errors = profile.raw_upstream_cc_errors(
            style,
            TOPICS,
            allowed_urls=[OFFICIAL_URL],
        )
        self.assertTrue(
            any("unapproved remote URL in <style> data" in error for error in style_errors)
        )

    def test_official_navigation_requires_blank_noopener_noreferrer(self) -> None:
        document = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            fixture_lesson(),
            fixture_ff(),
        )
        for unsafe, expected in (
            (
                document.replace(' target="_blank"', "", 1),
                'target="_blank"',
            ),
            (
                document.replace(
                    'rel="noopener noreferrer"',
                    'rel="noopener"',
                    1,
                ),
                'rel="noopener noreferrer"',
            ),
        ):
            errors = profile.raw_upstream_cc_errors(
                unsafe,
                TOPICS,
                allowed_urls=[OFFICIAL_URL],
            )
            self.assertTrue(any(expected in error for error in errors), errors)

    def test_raw_upstream_shell_is_rejected(self) -> None:
        raw = """ .cc
```html
<html lang="KR"><head>
<link rel="stylesheet" href="https://cdn.example/x.css">
</head><body>
<main id="ai-content-placeholder" style="display:none;"></main>
<script>renderAppShell("unsafe")</script>
</body></html>
```
"""
        errors = profile.raw_upstream_cc_errors(raw)
        for risk in (
            "command wrapper",
            "Markdown HTML fence",
            "active script",
            "external resource tag",
            "remote URL",
            "hidden content",
            "invalid Korean language tag",
            "upstream executable app shell",
        ):
            self.assertTrue(any(risk in error for error in errors), risk)

    def test_generate_interface_refuses_overwrite_and_force_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "lesson"
            folder.mkdir()
            (folder / "ff.md").write_text(
                fixture_ff(),
                encoding="utf-8",
                newline="\n",
            )
            with (
                patch.object(renderer, "load_curriculum", return_value=CURRICULUM),
                patch.object(renderer, "lesson_dir", return_value=folder),
            ):
                output = renderer.generate_cc(COURSE_ID, LESSON_ID)
                original = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    renderer.generate_cc(COURSE_ID, LESSON_ID)
                replaced = renderer.generate_cc(
                    COURSE_ID,
                    LESSON_ID,
                    force=True,
                )
                self.assertEqual(original, replaced.read_bytes())

    def test_explicit_ff_out_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ff_path = root / "source.md"
            output_path = root / "visual.html"
            ff_path.write_text(fixture_ff(), encoding="utf-8", newline="\n")
            argv = [
                "render_ailey_public_cc.py",
                "--course-id",
                COURSE_ID,
                "--lesson-id",
                LESSON_ID,
                "--ff",
                str(ff_path),
                "--out",
                str(output_path),
            ]
            with (
                patch.object(renderer, "load_curriculum", return_value=CURRICULUM),
                patch.object(sys, "argv", argv),
                redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(renderer.main(), 0)
            self.assertTrue(output_path.is_file())
            self.assertIn(str(output_path), stdout.getvalue())


class AileyAssemblerTest(unittest.TestCase):
    def test_lesson_request_contains_literal_command_and_source_packet(self) -> None:
        request = assembler.build_lesson_request(
            CURRICULUM,
            fixture_lesson(),
        )
        self.assertTrue(request.startswith(".ff 공개 프롬프트 시험 과정\n"))
        self.assertIn("[STUDY_FACTORY_SOURCE_PACKET]", request)
        self.assertIn(profile.AILEY_FF_PROFILE, request)
        self.assertIn("시험 섹션 > 시험 유닛 > 시험 그룹", request)
        packet = request.split(
            "[STUDY_FACTORY_SOURCE_PACKET]\n",
            1,
        )[1].split("\n[/STUDY_FACTORY_SOURCE_PACKET]", 1)[0]
        decoded = json.loads(packet)
        self.assertEqual(decoded["learning_lesson"]["topics"], TOPICS)
        self.assertEqual(decoded["sources"][0]["id"], "fixture-source")

    def test_named_cli_flags_emit_user_message(self) -> None:
        argv = [
            "assemble_ailey_prompt.py",
            "--course-id",
            COURSE_ID,
            "--lesson-id",
            LESSON_ID,
            "--part",
            "user",
        ]
        with (
            patch.object(assembler, "load_curriculum", return_value=CURRICULUM),
            patch.object(sys, "argv", argv),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            self.assertEqual(assembler.main(), 0)
        output = stdout.getvalue()
        self.assertTrue(output.startswith(".ff 공개 프롬프트 시험 과정"))
        self.assertIn("[STUDY_FACTORY_SOURCE_PACKET]", output)
        self.assertNotIn("<<<SYSTEM_SPEC>>>", output)


if __name__ == "__main__":
    unittest.main()
