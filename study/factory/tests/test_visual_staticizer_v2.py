from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import sanitize_ailey_github_cc as staticizer  # noqa: E402


COURSE_ID = "visual-fixture"
COURSE_TITLE = "시각화 검증 과정"
LESSON_ID = "1-1-1-1"
LESSON_TITLE = "안전한 시각화 정적화"
TOPICS = ["위험 흐름 시각화", "보호 계층 비교"]


SAFE_CSS = """
/* a duplicate block must be emitted only once */
:root { --lesson-accent: #0b7285; }
.visual-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.visual-grid > .visual-card { border: 2px solid var(--lesson-accent); }
.visual-page .visual-root { background: #f8fbfc; color: #17324d; }
.visual-card::after { content: "literal /* text */"; }
@media (max-width: 42rem) {
  .visual-grid { grid-template-columns: 1fr; }
}
""".strip()


def raw_visual_cc(css: str = SAFE_CSS, *, unsafe_shell: bool = False) -> str:
    filler = " ".join(f"시각적 설명 {index}." for index in range(1, 230))
    unsafe_head = (
        '<link rel="stylesheet" href="https://remote.invalid/theme.css">'
        if unsafe_shell else ""
    )
    main_attrs = ' style="display:none" onload="steal()"' if unsafe_shell else ""
    unsafe_body = "" if not unsafe_shell else """
<img src="https://remote.invalid/photo.png" alt="보호 계층 보조 설명">
<a href="https://remote.invalid/tracker" ping="https://remote.invalid/ping">읽을 수 있는 설명</a>
<script src="https://remote.invalid/app.js">const fake = '<style>.script-only { display: block; }</style>';</script>
"""
    return f"""<!doctype html>
<html lang="ko">
<head>
<title>{LESSON_ID}. {LESSON_TITLE}</title>
<style data-lesson-style="visual-v2">{css}</style>
{unsafe_head}
</head>
<body class="visual-page">
<main id="ai-content-placeholder" class="visual-root"{main_attrs}>
<h1>{LESSON_ID}. {LESSON_TITLE}</h1>
<p>{COURSE_TITLE} · {TOPICS[0]} · {TOPICS[1]}</p>
<section class="visual-grid">
<article class="visual-card"><h2>실제 SVG 흐름도</h2><p>{filler}</p></article>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 320 120" role="img" aria-label="위험에서 보호 계층까지의 흐름" aria-labelledby="barrier-title barrier-desc">
  <title id="barrier-title">장벽 흐름</title>
  <desc id="barrier-desc">위험에서 두 보호 장벽을 거쳐 안전 상태로 이동하는 도식</desc>
  <defs>
    <linearGradient id="safe-gradient"><stop offset="0" stop-color="#0b7285"></stop></linearGradient>
    <g id="safe-node"><rect width="90" height="44" rx="8"></rect></g>
  </defs>
  <use href="#safe-node" x="10" y="20" fill="url(#safe-gradient)"></use>
  <use xlink:href="#safe-node" x="180" y="20"></use>
  <text x="65" y="95">위험 → 장벽 → 안전</text>
</svg>
{unsafe_body}
</section>
</main>
</body>
</html>"""


def staticize(raw: str) -> str:
    return staticizer.staticize_cc_response(
        raw,
        course_id=COURSE_ID,
        course_title=COURSE_TITLE,
        lesson_id=LESSON_ID,
        lesson_title=LESSON_TITLE,
        topics=TOPICS,
        profile=staticizer.CC_VISUAL_PROFILE,
        context_ff_sha256="a" * 64,
        model_instructions_sha256="b" * 64,
        codex_thread_id="12345678-1234-4234-9234-123456789abc",
        codex_model="gpt-5.6-sol",
        codex_reasoning="medium",
    )


def raw_visual_cc_with_markers() -> str:
    markers = """  <defs>
    <marker id="missing" markerWidth="10" markerHeight="10"><path d="M0 0 L10 5 L0 10 Z"></path></marker>
    <marker id="stroke" markerUnits="strokeWidth" markerWidth="10" markerHeight="10"></marker>
    <marker id="user" MARKERUNITS='userSpaceOnUse' markerWidth="10" markerHeight="10"></marker>
    <marker id="empty" markerUnits markerWidth="10" markerHeight="10"></marker>
    <MaRkEr id="self" data-note="> markerUnits=x"/>
"""
    return raw_visual_cc().replace("  <defs>\n", markers, 1)


class VisualStaticizerV2Test(unittest.TestCase):
    def test_preserves_unique_safe_css_and_accessible_inline_svg(self) -> None:
        raw = raw_visual_cc()
        result = staticize(raw)

        self.assertIn('data-ailey-lesson-css="sanitized"', result)
        self.assertIn('name="lesson-css-sha256"', result)
        self.assertEqual(result.count(":root { --lesson-accent: #0b7285; }"), 1)
        self.assertIn('.visual-grid > .visual-card', result)
        self.assertIn('<body class="visual-page">', result)
        self.assertIn('class="ailey-canvas visual-root"', result)
        self.assertIn('content: "literal /* text */"', result)
        self.assertIn('<svg viewBox="0 0 320 120" role="img"', result)
        self.assertIn('<title id="barrier-title">장벽 흐름</title>', result)
        self.assertIn('href="#safe-node"', result)
        self.assertIn('xlink:href="#safe-node"', result)
        self.assertIn('fill="url(#safe-gradient)"', result)
        self.assertEqual(
            staticizer.normalized_visible_main_text(result),
            staticizer.normalized_visible_main_text(raw),
        )
        self.assertIn(
            f'name="prompt-profile" content="{staticizer.CC_VISUAL_PROFILE}"',
            result,
        )
        self.assertIn(
            'name="staticizer-profile" content="ailey-public-live-visual-static-v2"',
            result,
        )
        self.assertIn(
            'name="generation-method" '
            'content="codex-live-same-context-static-visual-v2"',
            result,
        )
        self.assertNotIn(
            'name="generation-method" '
            'content="codex-live-same-context-cc-staticized"',
            result,
        )

    def test_marker_units_normalizer_is_source_preserving_scoped_and_idempotent(self) -> None:
        fragment = """<main>
<!-- <svg><marker id="comment"></marker></svg> -->
<marker id="outside"></marker>
<svg viewBox="0 0 10 10">
<![CDATA[<marker id="cdata"></marker>]]>
<defs>
<marker id="missing" data-note="> markerUnits=x"></marker>
<marker id="stroke" markerUnits="strokeWidth"></marker>
<marker id="user" MARKERUNITS='userSpaceOnUse'></marker>
<marker id="empty" markerUnits></marker>
<MaRkEr id="self"/>
</defs>
<foreignObject>
  <div>
    <marker id="html-in-foreign-object"></marker>
    <svg><marker id="nested-svg"></marker></svg>
  </div>
</foreignObject>
<foreignObject/>
<marker id="after-self-closing-foreign-object"></marker>
</svg>
</main>"""
        normalized = staticizer._normalize_missing_svg_marker_units(fragment)

        self.assertEqual(
            normalized,
            staticizer._normalize_missing_svg_marker_units(normalized),
        )
        self.assertIn(
            '<marker markerUnits="userSpaceOnUse" id="missing" '
            'data-note="> markerUnits=x">',
            normalized,
        )
        self.assertIn('<MaRkEr markerUnits="userSpaceOnUse" id="self"/>', normalized)
        self.assertIn('<marker id="stroke" markerUnits="strokeWidth">', normalized)
        self.assertIn("<marker id=\"user\" MARKERUNITS='userSpaceOnUse'>", normalized)
        self.assertIn('<marker id="empty" markerUnits>', normalized)
        self.assertIn('<marker id="outside"></marker>', normalized)
        self.assertIn(
            '<!-- <svg><marker id="comment"></marker></svg> -->',
            normalized,
        )
        self.assertIn(
            '<![CDATA[<marker id="cdata"></marker>]]>',
            normalized,
        )
        self.assertIn(
            '<marker id="html-in-foreign-object"></marker>',
            normalized,
        )
        self.assertIn(
            '<marker markerUnits="userSpaceOnUse" id="nested-svg">',
            normalized,
        )
        self.assertIn(
            '<marker markerUnits="userSpaceOnUse" '
            'id="after-self-closing-foreign-object">',
            normalized,
        )
        self.assertEqual(4, normalized.count(' markerUnits="userSpaceOnUse"'))
        self.assertEqual(
            fragment,
            normalized.replace(' markerUnits="userSpaceOnUse"', ""),
        )

        with patch.object(
            staticizer._SvgMarkerUnitsInsertionParser,
            "getpos",
            return_value=(999, 0),
        ), self.assertRaisesRegex(ValueError, "cannot map SVG marker"):
            staticizer._normalize_missing_svg_marker_units(
                '<svg><marker id="broken"></marker></svg>'
            )

        with self.assertRaisesRegex(ValueError, "cannot safely track SVG namespace"):
            staticizer._normalize_missing_svg_marker_units(
                "<svg><foreignObject></svg>"
            )

    def test_visual_staticizer_normalizes_marker_units_without_rewriting_audit_source(self) -> None:
        raw = raw_visual_cc_with_markers()
        result = staticize(raw)

        self.assertEqual(result, staticize(raw))
        self.assertIn(
            '<marker markerUnits="userSpaceOnUse" id="missing"',
            result,
        )
        self.assertIn(
            '<MaRkEr markerUnits="userSpaceOnUse" id="self" '
            'data-note="> markerUnits=x"/>',
            result,
        )
        self.assertIn(
            '<marker id="stroke" markerUnits="strokeWidth"',
            result,
        )
        self.assertIn(
            "<marker id=\"user\" MARKERUNITS='userSpaceOnUse'",
            result,
        )
        self.assertIn('<marker id="empty" markerUnits ', result)
        self.assertEqual(2, result.count(' markerUnits="userSpaceOnUse"'))
        self.assertEqual(
            staticizer.normalized_visible_main_text(raw),
            staticizer.normalized_visible_main_text(result),
        )
        raw_digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        source = staticizer.extract_html_response(raw, strict=True)
        source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.assertIn(
            f'<meta name="raw-cc-sha256" content="{raw_digest}">',
            result,
        )
        self.assertIn(
            f'<meta name="source-cc-sha256" content="{source_digest}">',
            result,
        )

        legacy = staticizer.staticize_cc_response(
            raw,
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        self.assertNotIn(' markerUnits="userSpaceOnUse"', legacy)
        self.assertIn('<marker id="missing" markerWidth="10"', legacy)

    def test_visual_profile_rejects_unsafe_raw_shell_and_legacy_strips_it(self) -> None:
        raw = raw_visual_cc(unsafe_shell=True)
        with self.assertRaisesRegex(ValueError, "forbidden raw tag"):
            staticize(raw)

        result = staticizer.staticize_cc_response(
            raw,
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )

        self.assertNotIn("remote.invalid", result)
        self.assertNotRegex(result, re.compile(r"<script\b", re.IGNORECASE))
        self.assertNotIn(".script-only", result)
        self.assertNotRegex(result, re.compile(r"<link\b", re.IGNORECASE))
        self.assertNotRegex(result, re.compile(r"\son[a-z-]*\s*=", re.IGNORECASE))
        self.assertNotRegex(result, re.compile(r"\sstyle\s*=", re.IGNORECASE))
        self.assertIn('<span class="image-alt">보호 계층 보조 설명</span>', result)
        self.assertIn("읽을 수 있는 설명", result)

    def test_visual_profile_rejects_svg_smil_active_content(self) -> None:
        raw = raw_visual_cc().replace(
            "</svg>",
            '<set attributeName="opacity" to="0" begin="0s"></set></svg>',
        )
        with self.assertRaisesRegex(ValueError, "forbidden raw tag"):
            staticize(raw)

    def test_visual_profile_rejects_default_hidden_disclosures(self) -> None:
        for markup, expected in (
            (
                "<details><summary>정답</summary><p>숨은 해설</p></details>",
                "forbidden raw tag",
            ),
            ("<dialog><p>숨은 해설</p></dialog>", "forbidden raw tag"),
            (
                '<section popover="auto"><p>숨은 해설</p></section>',
                "popover disclosure",
            ),
        ):
            with self.subTest(markup=markup):
                raw = raw_visual_cc().replace("</main>", markup + "</main>")
                with self.assertRaisesRegex(ValueError, expected):
                    staticize(raw)

    def test_visual_profile_rejects_hidden_svg_but_accepts_fractional_scale(self) -> None:
        for attribute in (
            'opacity="0"',
            'display="none"',
            'visibility="hidden"',
            'transform="scale(1, 0)"',
        ):
            with self.subTest(attribute=attribute):
                raw = raw_visual_cc().replace("<svg ", f"<svg {attribute} ", 1)
                with self.assertRaisesRegex(ValueError, "hidden presentation"):
                    staticize(raw)

        scaled = raw_visual_cc().replace(
            "<svg ",
            '<svg transform="scale(0.5)" ',
            1,
        )
        self.assertIn('transform="scale(0.5)"', staticize(scaled))

    def test_visual_profile_rejects_zero_scale_css_without_prefix_false_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "zero scale transform"):
            staticize(raw_visual_cc(SAFE_CSS + "\n.visual-card { transform: scale(0.5, 0); }"))
        safe = staticize(
            raw_visual_cc(SAFE_CSS + "\n.visual-card { transform: scale(0.5); }")
        )
        self.assertIn("transform: scale(0.5)", safe)

    def test_visual_profile_rejects_svg_min_width_but_accepts_responsive_svg(self) -> None:
        for selector in (
            ".visual svg",
            "main>svg.diagram",
            "svg[role=img]",
            "*|svg",
            r"s\76 g",
        ):
            with self.subTest(selector=selector):
                forced = (
                    SAFE_CSS
                    + f"\n@media(max-width:600px){{{selector}{{min-width:560px}}}}"
                )
                with self.assertRaisesRegex(ValueError, "forced SVG minimum width"):
                    staticize(raw_visual_cc(forced))

        safe = staticize(
            raw_visual_cc(
                SAFE_CSS
                + "\n.visual svg{width:100%;max-width:100%;height:auto}"
                + "\n.svg-card,[data-kind=svg]{min-width:12rem}"
                + "\n.card:has(svg),svg .caption,svg+.caption{min-width:12rem}"
                + '\nsvg{--min-width:12rem;content:"; min-width:560px"}'
            )
        )
        self.assertIn("max-width:100%", safe)
        self.assertIn(".svg-card,[data-kind=svg]{min-width:12rem}", safe)
        self.assertIn(".card:has(svg),svg .caption,svg+.caption{min-width:12rem}", safe)

    def test_rejects_dangerous_css_instead_of_publishing_a_generic_fallback(self) -> None:
        dangerous_styles = {
            "import": "@import 'theme.css'; .card { color: teal; }",
            "comment-obfuscated import": "@im/**/port 'theme.css';",
            "url": ".card { background: url('#local'); }",
            "escaped url": r".card { background: u\72l('#local'); }",
            "expression": ".card { width: expression(alert(1)); }",
            "behavior": ".card { behavior: url(x.htc); }",
            "moz binding": ".card { -moz-binding: url(x.xml); }",
            "remote protocol": '.card::after { content: "https://remote.invalid"; }',
            "executable protocol": '.card::after { content: "javascript:alert(1)"; }',
        }
        for label, css in dangerous_styles.items():
            with self.subTest(label=label), self.assertRaisesRegex(
                ValueError,
                "unsafe lesson CSS",
            ):
                staticize(raw_visual_cc(css))

    def test_rejects_unknown_profile_without_changing_legacy_default(self) -> None:
        legacy = staticizer.staticize_cc_response(
            raw_visual_cc(),
            course_id=COURSE_ID,
            course_title=COURSE_TITLE,
            lesson_id=LESSON_ID,
            lesson_title=LESSON_TITLE,
            topics=TOPICS,
        )
        self.assertIn(f'name="prompt-profile" content="{staticizer.CC_PROFILE}"', legacy)
        with self.assertRaisesRegex(ValueError, "unknown CC prompt profile"):
            staticizer.staticize_cc_response(
                raw_visual_cc(),
                course_id=COURSE_ID,
                course_title=COURSE_TITLE,
                lesson_id=LESSON_ID,
                lesson_title=LESSON_TITLE,
                topics=TOPICS,
                profile="unknown",
            )


if __name__ == "__main__":
    unittest.main()
