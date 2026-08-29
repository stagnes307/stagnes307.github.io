from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from visual_cc_quality import (  # noqa: E402
    MAX_DISPLAY_H1_CHARS,
    analyze_visual_cc_quality,
    required_visual_v2_svg_count,
    visual_cc_quality_errors,
    visual_cc_quality_metrics,
    visual_v2_contract_errors,
    visual_v2_style_diversity_errors,
)


def document(body: str, style: str = "") -> str:
    return f"""<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><style>{style}</style></head>
<body><main>{body}</main></body>
</html>"""


def meaningful_svg() -> str:
    return """
<figure>
  <figcaption>수집에서 분석과 의사결정으로 이어지는 데이터 처리 흐름</figcaption>
  <svg viewBox="0 0 640 220" role="img"
       aria-label="세 단계 데이터 처리 흐름과 단계 사이의 연결 관계"
       aria-labelledby="flow-title flow-desc">
    <title id="flow-title">데이터 처리 흐름</title>
    <desc id="flow-desc">수집, 분석, 의사결정을 왼쪽에서 오른쪽으로 연결한 도식</desc>
    <rect x="10" y="50" width="150" height="90" rx="12"></rect>
    <rect x="245" y="50" width="150" height="90" rx="12"></rect>
    <rect x="480" y="50" width="150" height="90" rx="12"></rect>
    <line x1="160" y1="95" x2="245" y2="95"></line>
    <line x1="395" y1="95" x2="480" y2="95"></line>
    <text x="85" y="100">수집</text>
    <text x="320" y="100">분석</text>
    <text x="555" y="100">의사결정</text>
  </svg>
</figure>
"""


class VisualCCQualityTest(unittest.TestCase):
    def test_accepts_accessible_nontrivial_legacy_like_inline_svg(self) -> None:
        result = analyze_visual_cc_quality(document(
            "<h1>데이터 가치 흐름</h1>" + meaningful_svg()
        ))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.metrics["inline_svg_count"], 1)
        self.assertEqual(result.metrics["accessible_svg_count"], 1)
        self.assertEqual(result.metrics["meaningful_svg_count"], 1)
        self.assertEqual(result.metrics["svg_primitive_count"], 5)
        self.assertEqual(result.metrics["svg_text_count"], 3)
        self.assertTrue(result.metrics["has_qualifying_visualization"])
        self.assertEqual(visual_cc_quality_errors(document(meaningful_svg())), [])

    def test_rejects_real_component_and_visible_placeholder_phrase(self) -> None:
        body = f"""
<h1>완성되지 않은 레슨</h1>
{meaningful_svg()}
<div data-component="image-placeholder" data-prompt="현장 사진 생성"></div>
<p>🖼️ 이미지 설계</p>
"""
        result = analyze_visual_cc_quality(document(body))

        self.assertFalse(result.ok)
        self.assertEqual(result.metrics["placeholder_component_count"], 1)
        self.assertEqual(result.metrics["visible_placeholder_phrase_count"], 1)
        self.assertTrue(any("placeholder component" in error for error in result.errors))
        self.assertTrue(any("visible placeholder phrase" in error for error in result.errors))
        # A real diagram does not excuse an unfinished placeholder elsewhere.
        self.assertEqual(result.metrics["meaningful_svg_count"], 1)

    def test_does_not_treat_inert_stylesheet_selectors_as_live_placeholders(self) -> None:
        style = """
[data-component="image-placeholder"]::before { content: "이미지 설계"; }
[data-component="visualization-placeholder"]::before { content: "구조 시각화 설계"; }
"""
        result = analyze_visual_cc_quality(document(meaningful_svg(), style))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.metrics["placeholder_component_count"], 0)
        self.assertEqual(result.metrics["visible_placeholder_phrase_count"], 0)

    def test_rejects_accessible_but_decorative_trivial_svg(self) -> None:
        result = analyze_visual_cc_quality(document("""
<h1>별 아이콘만 있는 레슨</h1>
<svg viewBox="0 0 20 20" role="img" aria-label="장식용 별 아이콘">
  <path d="M10 1 L12 7 L19 7 L14 11 L16 18 L10 14 L4 18 L6 11 L1 7 L8 7 Z"></path>
</svg>
"""))

        self.assertFalse(result.ok)
        self.assertEqual(result.metrics["accessible_svg_count"], 1)
        self.assertEqual(result.metrics["meaningful_svg_count"], 0)
        self.assertTrue(any(
            "meaningful accessible inline SVG" in error
            for error in result.errors
        ))

    def test_accepts_compact_labelled_line_chart(self) -> None:
        result = analyze_visual_cc_quality(document("""
<h1>분포 변화</h1>
<svg viewBox="0 0 420 130" role="img" aria-label="과거와 현재의 분포 변화 비교 도식">
  <path d="M10 105 C65 100 70 25 145 30 C210 35 218 100 280 102"></path>
  <path d="M130 104 C185 100 195 45 270 42 C340 40 350 98 410 101"></path>
  <text x="70" y="20">과거 분포</text>
  <text x="310" y="28">현재 분포</text>
</svg>
"""))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.metrics["svg_primitive_count"], 2)
        self.assertEqual(result.metrics["svg_text_count"], 2)
        self.assertEqual(result.metrics["meaningful_svg_count"], 1)

    def test_accepts_substantial_accessible_semantic_css_flow(self) -> None:
        style = """
.process-flow .flow-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}
"""
        body = """
<h1>위험성평가 흐름</h1>
<figure class="process-flow" aria-label="위험성평가의 네 단계 순환 흐름도">
  <figcaption>유해위험요인 파악부터 개선 확인까지 이어지는 순환</figcaption>
  <ol class="flow-steps">
    <li class="flow-item">1. 유해위험요인 파악</li>
    <li class="flow-item">2. 위험성 추정과 결정</li>
    <li class="flow-item">3. 감소대책 수립과 실행</li>
    <li class="flow-item">4. 결과 기록과 개선 확인</li>
  </ol>
</figure>
"""
        result = analyze_visual_cc_quality(document(body, style))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.metrics["inline_svg_count"], 0)
        self.assertGreaterEqual(
            result.metrics["semantic_html_visualization_count"],
            1,
        )
        self.assertGreaterEqual(result.metrics["semantic_visual_node_count"], 4)
        self.assertGreaterEqual(result.metrics["css_grid_declaration_count"], 1)
        self.assertTrue(result.metrics["has_qualifying_visualization"])

    def test_quantifies_long_h1_and_table_heavy_no_visual_page(self) -> None:
        rows = "".join(
            f"<tr><th scope='row'>{index}</th><td>설명 {index}</td></tr>"
            for index in range(1, 8)
        )
        tables = "".join(
            f"<table><caption>표 {index}</caption><tbody>{rows}</tbody></table>"
            for index in range(1, 5)
        )
        result = analyze_visual_cc_quality(document(
            f"<h1>{'가' * (MAX_DISPLAY_H1_CHARS + 1)}</h1>{tables}"
        ))

        self.assertEqual(result.metrics["excessively_long_h1_count"], 1)
        self.assertEqual(
            result.metrics["max_display_h1_char_count"],
            MAX_DISPLAY_H1_CHARS + 1,
        )
        self.assertEqual(result.metrics["table_count"], 4)
        self.assertEqual(result.metrics["table_row_count"], 28)
        self.assertTrue(result.metrics["table_heavy_no_visual"])
        self.assertTrue(any("display H1" in error for error in result.errors))
        self.assertTrue(any("table-heavy" in error for error in result.errors))
        self.assertEqual(
            visual_cc_quality_metrics(document(tables))["table_count"],
            4,
        )

    def test_visual_v2_contract_requires_completed_svg_and_lesson_css(self) -> None:
        css = "\n".join([
            ":root { --lesson-accent: #135f72; --lesson-paper: #f8fbfc; }",
            ".lesson-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }",
            *(
                f".lesson-node-{index} {{ border: 1px solid var(--lesson-accent); "
                f"padding: {index}px; background: var(--lesson-paper); }}"
                for index in range(1, 8)
            ),
            "@media (max-width: 42rem) { .lesson-grid { grid-template-columns: 1fr; } }",
            "@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }",
            "@media print { .lesson-grid { display: block; } }",
        ])
        filler = " ".join(f"개념 설명 {index}" for index in range(1, 520))
        source = f"""<!doctype html>
<html lang="ko"><head>
<style data-ailey-lesson-css="sanitized">{css}</style>
</head><body><main>
<h1>데이터가 가치로 흐르는 의사결정 지도</h1>
<p class="official-title">데이터의 수집·분석·의사결정</p>
<p>{filler}</p>
{meaningful_svg()}
<section><h2>확인 문제</h2><p>수집과 분석 사이에서 검증해야 할 조건을 설명하세요.</p></section>
<section><h2>정답과 해설</h2><p>입력의 품질과 분석 목적을 함께 확인해야 올바른 판단이 가능합니다.</p></section>
<section><h2>핵심 요약</h2><p>수집, 분석, 의사결정은 검증 가능한 하나의 흐름으로 연결됩니다.</p></section>
</main></body></html>"""

        self.assertEqual(visual_v2_contract_errors(source), [])
        metrics = visual_cc_quality_metrics(source)
        self.assertEqual(metrics["visual_v2_complete_svg_count"], 1)
        self.assertEqual(metrics["lesson_style_block_count"], 1)
        self.assertGreaterEqual(metrics["lesson_style_char_count"], 600)
        self.assertEqual(metrics["lesson_style_media_query_count"], 3)
        self.assertTrue(any(
            "at least 2 distinct meaningful SVG" in error
            for error in visual_v2_contract_errors(source, required_svg_count=2)
        ))

        missing_sections = source.replace("<h2>확인 문제</h2>", "<p>확인 문제</p>")
        self.assertTrue(any(
            "substantive content for 확인 문제" in error
            for error in visual_v2_contract_errors(missing_sections)
        ))

        nested_heading = source.replace(
            "<section><h2>확인 문제</h2><p>수집과 분석 사이에서 검증해야 할 조건을 설명하세요.</p></section>",
            "<section><header><h2>확인 문제</h2></header>"
            "<div><h3>문제 1</h3><p>수집과 분석 사이에서 검증해야 할 조건을 설명하세요.</p>"
            "</div></section>",
        )
        self.assertFalse(any(
            "substantive content for 확인 문제" in error
            for error in visual_v2_contract_errors(nested_heading)
        ))

        empty_later_sections = source.replace(
            "<section><h2>확인 문제</h2><p>수집과 분석 사이에서 검증해야 할 조건을 설명하세요.</p></section>\n"
            "<section><h2>정답과 해설</h2><p>입력의 품질과 분석 목적을 함께 확인해야 올바른 판단이 가능합니다.</p></section>\n"
            "<section><h2>핵심 요약</h2><p>수집, 분석, 의사결정은 검증 가능한 하나의 흐름으로 연결됩니다.</p></section>",
            "<section><h2>확인 문제</h2><p>수집과 분석 사이에서 검증해야 할 조건을 자세히 설명하세요.</p>"
            "<h2>정답과 해설</h2><h2>핵심 요약</h2></section>",
        )
        empty_errors = visual_v2_contract_errors(empty_later_sections)
        self.assertTrue(any(
            "substantive content for 정답 또는 해설" in error
            for error in empty_errors
        ))
        self.assertTrue(any(
            "substantive content for 요약" in error
            for error in empty_errors
        ))

    def test_visual_v2_hidden_svg_presentation_attributes_do_not_count(self) -> None:
        safe = document(meaningful_svg())
        for attribute in (
            'opacity="0"',
            'display="none"',
            'visibility="hidden"',
            'transform="scale(1, 0)"',
        ):
            with self.subTest(attribute=attribute):
                source = safe.replace("<svg ", f"<svg {attribute} ", 1)
                metrics = visual_cc_quality_metrics(source)
                self.assertEqual(metrics["meaningful_svg_count"], 0)
                self.assertEqual(metrics["visual_v2_complete_svg_count"], 0)

        scaled = safe.replace("<svg ", '<svg transform="scale(0.5)" ', 1)
        self.assertEqual(
            visual_cc_quality_metrics(scaled)["visual_v2_complete_svg_count"],
            1,
        )

    def test_visual_v2_rejects_missing_use_targets_and_zero_size_primitives(self) -> None:
        def candidate(shapes: str) -> str:
            return document(f"""
<svg viewBox="0 0 320 160" role="img" aria-label="실제로 렌더되는 도형 검증 도식"
 aria-labelledby="shape-title shape-desc">
<title id="shape-title">도형 검증</title>
<desc id="shape-desc">유효한 크기와 참조를 가진 도형만 세는 검증 도식</desc>
{shapes}
<text x="10" y="120">첫째 레이블</text><text x="160" y="120">둘째 레이블</text>
</svg>""")

        missing_uses = candidate("""
<use href="#missing-a"></use><use href="#missing-b"></use>
<use href="#missing-c"></use>
""")
        zero_rects = candidate("<rect></rect><rect></rect><rect></rect>")
        for source in (missing_uses, zero_rects):
            metrics = visual_cc_quality_metrics(source)
            self.assertEqual(metrics["visual_v2_rendered_svg_primitive_count"], 0)
            self.assertEqual(metrics["visual_v2_complete_svg_count"], 0)

        resolved_uses = candidate("""
<defs><g id="real-node"><rect width="40" height="30"></rect></g></defs>
<use href="#real-node" x="0"></use><use href="#real-node" x="80"></use>
<use href="#real-node" x="160"></use>
""")
        metrics = visual_cc_quality_metrics(resolved_uses)
        self.assertEqual(metrics["visual_v2_rendered_svg_primitive_count"], 3)
        self.assertEqual(metrics["visual_v2_complete_svg_count"], 1)

    def test_visual_v2_svg_floor_tracks_lesson_complexity(self) -> None:
        self.assertEqual(required_visual_v2_svg_count({
            "title": "단일 개념",
            "topics": ["정의"],
            "lesson_type": "concept",
        }), 1)
        self.assertEqual(required_visual_v2_svg_count({
            "title": "관리도 계산",
            "topics": ["관리한계"],
            "lesson_type": "calculation",
        }), 2)
        self.assertEqual(required_visual_v2_svg_count({
            "title": "두 개념",
            "topics": ["정의", "적용"],
            "lesson_type": "concept",
        }), 2)

    def test_visual_v2_course_rejects_a_repeated_css_shell(self) -> None:
        repeated = {f"lesson-{index}": "same" for index in range(1, 21)}
        errors = visual_v2_style_diversity_errors(
            repeated,
            expected_lesson_count=20,
        )
        self.assertTrue(any("CSS diversity" in error for error in errors))
        self.assertTrue(any("repeats one lesson CSS shell" in error for error in errors))

        diverse = {f"lesson-{index}": f"hash-{index}" for index in range(1, 21)}
        self.assertEqual(
            visual_v2_style_diversity_errors(
                diverse,
                expected_lesson_count=20,
            ),
            [],
        )
        self.assertEqual(
            visual_v2_style_diversity_errors(
                {"pilot": "hash"},
                expected_lesson_count=20,
            ),
            [],
        )
    def test_visual_v2_does_not_count_unused_defs_as_rendered_shapes(self) -> None:
        css = (
            ".lesson { display:grid; grid-template-columns:1fr 1fr; gap:1rem; }\n"
            + "\n".join(
                f".node-{index} {{ padding:{index}px; border:1px solid #234; }}"
                for index in range(1, 15)
            )
            + "\n@media (max-width:40rem){.lesson{grid-template-columns:1fr;}}"
            + "\n@media (prefers-reduced-motion:reduce){*{animation:none!important;}}"
            + "\n@media print{.lesson{display:block;}}"
        )
        unused = "".join(
            f'<rect x="{index}" y="{index}" width="10" height="10"></rect>'
            for index in range(8)
        )
        filler = " ".join(f"학습 설명 {index}" for index in range(1, 560))
        source = f"""<!doctype html><html lang="ko"><head>
<style data-ailey-lesson-css="sanitized">{css}</style></head><body><main>
<h1>정의 속 도형과 실제 화면을 구별하는 지도</h1>
<p class="official-title">실제 렌더링 검증</p><p>{filler}</p>
<svg viewBox="0 0 400 200" role="img" aria-label="정의만 있고 실제 도형은 없는 도식"
 aria-labelledby="unused-title unused-desc">
<title id="unused-title">정의 전용 도식</title>
<desc id="unused-desc">화면에 실제 도형이 렌더되지 않는 잘못된 사례</desc>
<defs>{unused}</defs><text x="10" y="20">레이블 하나</text><text x="10" y="50">레이블 둘</text>
</svg></main></body></html>"""

        metrics = visual_cc_quality_metrics(source)
        self.assertEqual(metrics["visual_v2_rendered_svg_primitive_count"], 0)
        self.assertEqual(metrics["visual_v2_complete_svg_count"], 0)
        self.assertTrue(any(
            "at least 1 distinct meaningful SVG" in error
            for error in visual_v2_contract_errors(source)
        ))

    def test_visual_v2_rejects_zero_sized_viewbox(self) -> None:
        source = document(meaningful_svg().replace(
            'viewBox="0 0 640 220"',
            'viewBox="0 0 0 220"',
        ))
        metrics = visual_cc_quality_metrics(source)
        self.assertEqual(metrics["meaningful_svg_count"], 1)
        self.assertEqual(metrics["visual_v2_complete_svg_count"], 0)

    def test_visual_v2_counts_cloned_diagrams_only_once(self) -> None:
        first = meaningful_svg()
        second = (
            meaningful_svg()
            .replace("flow-title", "flow-title-copy")
            .replace("flow-desc", "flow-desc-copy")
        )
        metrics = visual_cc_quality_metrics(document(first + second))
        self.assertEqual(metrics["visual_v2_complete_svg_count"], 2)
        self.assertEqual(metrics["visual_v2_distinct_complete_svg_count"], 1)


if __name__ == "__main__":
    unittest.main()
