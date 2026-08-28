from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import render_codex_cc as renderer  # noqa: E402
from common import codex_artifact_quality_errors  # noqa: E402


COURSE_ID = "fixture-course"
TOPICS = ["첫 번째 핵심 토픽", "두 번째 핵심 토픽"]
CURRICULUM = {
    "course_id": COURSE_ID,
    "title": "안전 렌더러 시험 과정",
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
                    "id": "1-1-1-1",
                    "title": "안전한 전체 FF 변환",
                    "slug": "safe-full-ff-rendering",
                    "topics": TOPICS,
                }],
            }],
        }],
    }],
}


def fixture_lesson() -> dict:
    return renderer.find_lesson(CURRICULUM, "1-1-1-1")


def fixture_ff() -> str:
    source = """# 1-1-1-1. 안전한 전체 FF 변환

첫 번째 핵심 토픽과 두 번째 핵심 토픽을 하나의 흐름으로 학습한다.
원문 템플릿 {{DANGER}}도 그대로 보이고, raw HTML <script>alert("x")</script>는 실행되지 않아야 한다.
[외부 링크](https://evil.example/path)와 ![위험 이미지](javascript:alert(1)) 및 @import 표현도 학습 텍스트로 남긴다.

> 이 인용문은 **핵심 경계**와 *판별 기준*을 설명한다.

## 1. 개념과 원리

### 1.1 세부 개념

문단 안의 `inline code`와 **굵은 설명**, *강조 설명*을 모두 보존한다.

- 순서 없는 첫 항목
  - 들여쓴 항목도 내용이 사라지지 않는다.
- 마지막 항목

3. 세 번째부터 시작하는 순서 항목
4. 다음 순서 항목

| 비교 항목 | 첫 번째 핵심 토픽 | 두 번째 핵심 토픽 |
| :--- | :---: | ---: |
| 정의 | 입력을 판별한다 | 결과를 해석한다 |
| 경계 | 누락을 찾는다 | 예외를 설명한다 |

```python
payload = "<script>not executable</script>"
reference = "https://code.example/resource"
print(payload, reference)
```

## 2. 안전한 상세 보기

<details onclick="alert(1)">
<summary onmouseover="alert(2)">정답과 해설 보기</summary>
세부 내용에서도 <img src="https://image.example/x"> 같은 raw HTML은 평문으로 남는다.
</details>

## 3. 확인 문제

첫 번째 핵심 토픽과 두 번째 핵심 토픽의 차이를 순서대로 설명하라.

### 정답과 해설

정답은 정의, 적용 조건, 해석 기준을 함께 적는 것이다.

## 4. 최종 요약

두 토픽의 정의와 경계를 다시 확인한다.
"""
    return source + ("\n상세 보존 문장: 정의, 원리, 예시, 경계, 시험 함정을 연결한다." * 110)


class RenderCodexCCTest(unittest.TestCase):
    def test_semantic_safe_complete_render(self) -> None:
        ff_source = fixture_ff()
        lesson = fixture_lesson()
        self.assertFalse(codex_artifact_quality_errors("ff", ff_source, TOPICS))

        first = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            lesson,
            ff_source,
        )
        second = renderer.render_cc_document(
            COURSE_ID,
            CURRICULUM,
            lesson,
            ff_source,
        )

        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first.encode("utf-8")), 8 * 1024)
        self.assertFalse(codex_artifact_quality_errors("cc", first, TOPICS))
        self.assertEqual(len(re.findall(r"<h1\b", first, re.IGNORECASE)), 1)
        self.assertIn('<meta name="canvas-id" content="codex-fixture-course-1-1-1-1-', first)
        self.assertIn('id="ai-content-placeholder"', first)
        self.assertIn("<blockquote>", first)
        self.assertIn('<ol class="markdown-list" start="3">', first)
        self.assertIn("<table>", first)
        self.assertIn("<caption>", first)
        self.assertIn('<th scope="col"', first)
        self.assertIn('<th scope="row"', first)
        self.assertIn('<pre><code class="language-python">', first)
        self.assertIn('<details class="reveal">', first)
        self.assertIn("정답과 해설 보기", first)
        self.assertIn("{{DANGER}}", first)
        self.assertIn("&lt;script&gt;", first)
        self.assertIn("상세 보존 문장", first)
        self.assertIn("원문 주소:", first)
        self.assertNotIn("<script", first.lower())
        self.assertNotIn("onclick", first.lower())
        self.assertNotIn("onmouseover", first.lower())
        self.assertNotIn("https://evil.example", first)
        self.assertNotIn("javascript:", first.lower())
        self.assertNotIn("@import", first.lower())

    def test_generate_is_idempotent_and_refuses_overwrite(self) -> None:
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
                output = renderer.generate_cc(COURSE_ID, "1-1-1-1")
                original = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    renderer.generate_cc(COURSE_ID, "1-1-1-1")
                replaced = renderer.generate_cc(
                    COURSE_ID,
                    "1-1-1-1",
                    force=True,
                )
                self.assertEqual(replaced.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
