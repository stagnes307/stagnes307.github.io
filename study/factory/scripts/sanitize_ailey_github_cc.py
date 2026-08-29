#!/usr/bin/env python3
"""Staticize one real same-context GitHub-Ailey ``.cc`` response.

The educational HTML body comes from the live Codex turn.  This module only
extracts that body and replaces its executable upstream shell with the inert
Study Factory shell required by the empty-sandbox viewer.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import Path

from common import codex_artifact_quality_errors
from visual_cc_quality import css_svg_min_width_rule_count


FF_PROFILE = "ailey-bailey-public-8a36e77d-ff-codex-live-v1"
CC_PROFILE = "ailey-bailey-public-8a36e77d-cc-codex-live-static-v1"
CC_VISUAL_PROFILE = "ailey-bailey-public-8a36e77d-cc-codex-live-visual-v2"
UPSTREAM_COMMIT = "8a36e77d025bb9c258bfeaf8587424783140b185"

STATICIZER_PROFILES = {
    CC_PROFILE: "ailey-public-live-static-v1",
    CC_VISUAL_PROFILE: "ailey-public-live-visual-static-v2",
}

DOCTYPE_RE = re.compile(r"<!doctype\s+html\b", re.IGNORECASE)
HTML_CLOSE_RE = re.compile(r"</html\s*>", re.IGNORECASE)
MAIN_RE = re.compile(
    r"<main\b(?=[^>]*\bid=[\"']ai-content-placeholder[\"'])[^>]*>"
    r"(?P<body>.*?)</main\s*>",
    re.IGNORECASE | re.DOTALL,
)
BODY_OPEN_RE = re.compile(r"<body\b[^>]*>", re.IGNORECASE | re.DOTALL)
TITLE_RE = re.compile(r"<title\b[^>]*>(?P<title>.*?)</title\s*>", re.IGNORECASE | re.DOTALL)
CLASS_ATTR_RE = re.compile(
    r"(?<![\w:-])class\s*=\s*(?:"
    r'"(?P<double>[^"]*)"|'
    r"'(?P<single>[^']*)'|"
    r"(?P<bare>[^\s>]+))",
    re.IGNORECASE,
)
BLOCKED_BLOCK_RE = re.compile(
    r"<(?P<tag>script|style|iframe|object|embed|template|noscript)\b[^>]*>"
    r".*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
SELF_CLOSING_ACTIVE_RE = re.compile(
    r"<(?:script|iframe|object|embed|template|noscript)\b[^>]*/\s*>",
    re.IGNORECASE | re.DOTALL,
)
BLOCKED_VOID_RE = re.compile(
    r"<(?:link|meta|source|input)\b[^>]*?/?>",
    re.IGNORECASE | re.DOTALL,
)
IMG_RE = re.compile(r"<img\b(?P<attrs>[^>]*)/?>", re.IGNORECASE | re.DOTALL)
ALT_ATTR_RE = re.compile(
    r"\balt\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
EVENT_ATTR_RE = re.compile(
    r"\s+on[a-z][a-z0-9_-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
STYLE_ATTR_RE = re.compile(
    r"\s+style\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
RESOURCE_ATTR_RE = re.compile(
    r"(?P<prefix>\s+)(?P<name>"
    r"src|href|xlink:href|srcset|action|formaction|poster|ping|cite|data|"
    r"background|longdesc|xmlns(?::xlink)?"
    r")"
    r"\s*=\s*(?P<value>\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
HIDDEN_ATTR_RE = re.compile(r"\s+hidden(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?", re.IGNORECASE)
PRESENTATION_ATTR_RE = re.compile(
    r"\s+(?P<name>display|visibility|opacity|transform)\s*=\s*"
    r"(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))",
    re.IGNORECASE,
)
FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```$", re.IGNORECASE)
TEXT_AUDIT_IGNORED_TAGS = frozenset({"script", "style", "template", "noscript"})
STYLE_COLLECTION_IGNORED_TAGS = frozenset({
    "script",
    "iframe",
    "object",
    "template",
    "noscript",
    "noembed",
    "noframes",
    "textarea",
    "xmp",
    "plaintext",
    "foreignobject",
    "animate",
    "animatemotion",
    "animatetransform",
    "set",
    "discard",
})
UNSAFE_MAIN_TAGS = frozenset({
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "template",
    "noscript",
    "noembed",
    "noframes",
    "textarea",
    "xmp",
    "plaintext",
    "foreignobject",
})
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|(.))", re.DOTALL)
CSS_DANGEROUS_PATTERNS = (
    ("@import", re.compile(r"@\s*import\b", re.IGNORECASE)),
    ("url()", re.compile(r"\burl\s*\(", re.IGNORECASE)),
    ("expression()", re.compile(r"\bexpression\s*\(", re.IGNORECASE)),
    ("behavior property", re.compile(r"(?:^|[;{])\s*behavior\s*:", re.IGNORECASE)),
    ("-moz-binding property", re.compile(r"-moz-binding\s*:", re.IGNORECASE)),
    (
        "remote or executable protocol",
        re.compile(r"(?:https?|ftp|file|javascript|data)\s*:", re.IGNORECASE),
    ),
)
VISUAL_CSS_DANGEROUS_PATTERNS = (
    ("hidden display", re.compile(r"\bdisplay\s*:\s*none\b", re.IGNORECASE)),
    (
        "hidden visibility",
        re.compile(r"\bvisibility\s*:\s*(?:hidden|collapse)\b", re.IGNORECASE),
    ),
    (
        "hidden content visibility",
        re.compile(r"\bcontent-visibility\s*:\s*hidden\b", re.IGNORECASE),
    ),
    (
        "zero opacity",
        re.compile(
            r"\bopacity\s*:\s*0(?:\.0+)?(?=\s*(?:!important\s*)?[;}]|\s*$)",
            re.IGNORECASE,
        ),
    ),
    (
        "fixed or sticky positioning",
        re.compile(r"\bposition\s*:\s*(?:fixed|sticky)\b", re.IGNORECASE),
    ),
    (
        "placeholder presentation",
        re.compile(
            r"(?:이미지\s*설계|구조\s*시각화\s*설계|"
            r"(?:image|visuali[sz]ation|diagram|chart)[-_ ]?placeholder)",
            re.IGNORECASE,
        ),
    ),
)
TRANSFORM_DECLARATION_RE = re.compile(
    r"\btransform\s*:\s*(?P<value>[^;}]+)",
    re.IGNORECASE,
)
SCALE_FUNCTION_RE = re.compile(
    r"\bscale(?:x|y)?\s*\((?P<arguments>[^()]*)\)",
    re.IGNORECASE,
)
CSS_NUMBER_RE = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?",
    re.IGNORECASE,
)
VISUAL_FORBIDDEN_TAG_RE = re.compile(
    r"<(?:script|link|iframe|object|embed|template|noscript|img|canvas|"
    r"form|input|button|select|textarea|video|audio|source|animate|"
    r"animateMotion|animateTransform|set|discard|details|summary|dialog)\b",
    re.IGNORECASE,
)
POPOVER_ATTR_RE = re.compile(
    r"\s+(?:popover|popovertarget|popovertargetaction)"
    r"(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?",
    re.IGNORECASE,
)


class _TextAuditParser(HTMLParser):
    """Collect human-readable body text while ignoring non-content elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized in TEXT_AUDIT_IGNORED_TAGS:
            self._ignored_depth += 1
        elif normalized == "img" and not self._ignored_depth:
            alt = next((value for name, value in attrs if name.casefold() == "alt"), None)
            if alt:
                self.parts.append(alt)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in TEXT_AUDIT_IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


class _UnsafeTagAuditParser(HTMLParser):
    """Find active/raw-text tags while allowing accessible titles in SVG."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.svg_depth = 0
        self.first_unsafe: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized == "svg":
            self.svg_depth += 1
        if self.first_unsafe is None and (
            normalized in UNSAFE_MAIN_TAGS
            or (normalized == "title" and self.svg_depth == 0)
        ):
            self.first_unsafe = f"<{normalized}"

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "svg" and self.svg_depth:
            self.svg_depth -= 1


class _StyleBlockCollector(HTMLParser):
    """Collect real style elements, excluding markup-shaped script/template data."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.ignored_depth = 0
        self.active_style: list[str] | None = None
        self.active_attrs: dict[str, str] = {}
        self.active_in_head = False
        self.head_depth = 0
        self.blocks: list[tuple[dict[str, str], bool, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.casefold()
        if normalized == "head":
            self.head_depth += 1
        if normalized in STYLE_COLLECTION_IGNORED_TAGS:
            self.ignored_depth += 1
        elif normalized == "style" and not self.ignored_depth:
            self.active_style = []
            self.active_attrs = {
                name.casefold(): value or "" for name, value in attrs
            }
            self.active_in_head = self.head_depth > 0

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized == "style" and self.active_style is not None:
            self.blocks.append((
                self.active_attrs,
                self.active_in_head,
                "".join(self.active_style),
            ))
            self.active_style = None
            self.active_attrs = {}
            self.active_in_head = False
        elif normalized in STYLE_COLLECTION_IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        if normalized == "head" and self.head_depth:
            self.head_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.active_style is not None:
            self.active_style.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.active_style is not None:
            self.active_style.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self.active_style is not None:
            self.active_style.append(f"&#{name};")


def _first_unsafe_main_tag(fragment: str) -> str | None:
    parser = _UnsafeTagAuditParser()
    parser.feed(fragment)
    parser.close()
    return parser.first_unsafe


def _normalized_visible_text(fragment: str) -> str:
    parser = _TextAuditParser()
    parser.feed(fragment)
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def normalized_visible_main_text(document: str) -> str:
    """Return normalized human-readable text from the canonical CC main element."""
    match = MAIN_RE.search(document)
    if match is None:
        raise ValueError('CC HTML lacks id="ai-content-placeholder" main')
    return _normalized_visible_text(match.group(0))


def residual_unsafe_main_tag(document: str) -> str | None:
    """Return the first unsafe raw-text/active tag name retained inside main."""
    match = MAIN_RE.search(document)
    if match is None:
        raise ValueError('CC HTML lacks id="ai-content-placeholder" main')
    return _first_unsafe_main_tag(match.group(0))


def _strip_css_comments(source: str) -> str:
    """Remove CSS comments without treating comment markers in strings as syntax."""
    output: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(source):
        char = source[index]
        if quote is not None:
            output.append(char)
            if char == "\\" and index + 1 < len(source):
                index += 1
                output.append(source[index])
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise ValueError("unsafe lesson CSS: unterminated comment")
            index = end + 2
            continue
        output.append(char)
        index += 1
    if quote is not None:
        raise ValueError("unsafe lesson CSS: unterminated string")
    return "".join(output)


def _decode_css_escapes_for_audit(source: str) -> str:
    """Decode CSS escapes only for security matching, not for emitted styling."""
    def replace(match: re.Match[str]) -> str:
        hexadecimal, escaped = match.groups()
        if hexadecimal is not None:
            value = int(hexadecimal, 16)
            if value == 0 or value > 0x10FFFF:
                return "\ufffd"
            return chr(value)
        return escaped or ""

    return CSS_ESCAPE_RE.sub(replace, source)


def _has_zero_scale_transform(source: str) -> bool:
    """Return whether a transform flattens either axis to exactly zero.

    Parsing the numeric arguments avoids treating a valid value such as
    ``scale(0.5)`` as zero merely because it begins with the character ``0``.
    SVG/CSS permit comma- or whitespace-separated two-axis scale arguments.
    """

    for match in SCALE_FUNCTION_RE.finditer(source):
        tokens = [
            token for token in re.split(r"[\s,]+", match.group("arguments").strip())
            if token
        ]
        if not tokens or any(CSS_NUMBER_RE.fullmatch(token) is None for token in tokens):
            continue
        if any(float(token) == 0 for token in tokens[:2]):
            return True
    return False


def collect_sanitized_lesson_css(
    raw_html: str,
    *,
    profile: str = CC_PROFILE,
) -> str:
    """Collect unique safe style blocks from the live CC document.

    A contaminated style block rejects the artifact instead of silently
    falling back to the shared skin.  That keeps visual-v2 generation honest:
    the caller can retry the live turn rather than publish an unstyled canvas.
    """
    collector = _StyleBlockCollector()
    collector.feed(raw_html)
    collector.close()

    blocks = collector.blocks
    if profile == CC_VISUAL_PROFILE:
        if len(blocks) != 1:
            raise ValueError(
                "visual-v2 CC must contain exactly one style block "
                f"(found {len(blocks)})"
            )
        attrs, in_head, _ = blocks[0]
        if attrs.get("data-lesson-style") != "visual-v2":
            raise ValueError(
                'visual-v2 CC style must set data-lesson-style="visual-v2"'
            )
        if not in_head:
            raise ValueError("visual-v2 CC style must be inside head")
    elif profile not in STATICIZER_PROFILES:
        raise ValueError(f"unknown CC prompt profile: {profile}")

    unique_blocks: list[str] = []
    seen: set[str] = set()
    for index, (attrs, _, block) in enumerate(blocks, start=1):
        if attrs.get("media"):
            raise ValueError(
                f"unsafe lesson CSS block {index}: style media attribute is not preserved"
            )
        css = _strip_css_comments(block).strip()
        if not css:
            continue
        if any(ord(char) < 32 and char not in "\t\n\r\f" for char in css):
            raise ValueError(f"unsafe lesson CSS block {index}: control character")
        audited = _decode_css_escapes_for_audit(css)
        for label, pattern in CSS_DANGEROUS_PATTERNS:
            if pattern.search(audited):
                raise ValueError(f"unsafe lesson CSS block {index}: {label}")
        if profile == CC_VISUAL_PROFILE:
            for label, pattern in VISUAL_CSS_DANGEROUS_PATTERNS:
                if pattern.search(audited):
                    raise ValueError(f"unsafe visual-v2 CSS block {index}: {label}")
            if css_svg_min_width_rule_count(audited):
                raise ValueError(
                    f"unsafe visual-v2 CSS block {index}: forced SVG minimum width"
                )
            if any(
                _has_zero_scale_transform(match.group("value"))
                for match in TRANSFORM_DECLARATION_RE.finditer(audited)
            ):
                raise ValueError(
                    f"unsafe visual-v2 CSS block {index}: zero scale transform"
                )
        if css in seen:
            continue
        seen.add(css)
        unique_blocks.append(css)
    return "\n\n".join(unique_blocks)


def _strip_resource_attribute(match: re.Match[str]) -> str:
    """Retain only same-document SVG references; discard load-capable URLs."""
    name = match.group("name").casefold()
    raw_value = match.group("value")
    value = raw_value[1:-1] if raw_value[:1] in {'"', "'"} else raw_value
    value = html.unescape(value).strip()
    if name in {"href", "xlink:href"} and re.fullmatch(r"#[A-Za-z_][\w:.-]*", value):
        return match.group(0)
    return ""


def _safe_class_tokens(opening_tag: str, *, required: tuple[str, ...] = ()) -> list[str]:
    match = CLASS_ATTR_RE.search(opening_tag)
    raw = ""
    if match is not None:
        raw = next(
            value
            for value in match.group("double", "single", "bare")
            if value is not None
        )
    tokens = [*required]
    for token in html.unescape(raw).split():
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", token) and token not in tokens:
            tokens.append(token)
    return tokens


def _validate_visual_raw_markup(raw_html: str) -> None:
    """Reject visual-v2 model output that violates its static response contract."""

    forbidden = VISUAL_FORBIDDEN_TAG_RE.search(raw_html)
    if forbidden is not None:
        raise ValueError(
            f"visual-v2 CC contains forbidden raw tag {forbidden.group(0)!r}"
        )
    if EVENT_ATTR_RE.search(raw_html):
        raise ValueError("visual-v2 CC contains an inline event attribute")
    if STYLE_ATTR_RE.search(raw_html):
        raise ValueError("visual-v2 CC contains an inline style attribute")
    if HIDDEN_ATTR_RE.search(raw_html):
        raise ValueError("visual-v2 CC contains a hidden attribute")
    if POPOVER_ATTR_RE.search(raw_html):
        raise ValueError("visual-v2 CC contains a popover disclosure attribute")
    for match in PRESENTATION_ATTR_RE.finditer(raw_html):
        name = match.group("name").casefold()
        value = next(
            item
            for item in match.group("double", "single", "bare")
            if item is not None
        ).strip().casefold()
        hidden = (
            (name == "display" and value == "none")
            or (name == "visibility" and value in {"hidden", "collapse"})
            or (name == "opacity" and re.fullmatch(r"0(?:\.0+)?", value) is not None)
            or (
                name == "transform"
                and _has_zero_scale_transform(value)
            )
        )
        if hidden:
            raise ValueError(
                f"visual-v2 CC contains hidden presentation attribute {name!r}"
            )
    for match in RESOURCE_ATTR_RE.finditer(raw_html):
        name = match.group("name").casefold()
        raw_value = match.group("value")
        value = raw_value[1:-1] if raw_value[:1] in {'"', "'"} else raw_value
        value = html.unescape(value).strip()
        if name in {"href", "xlink:href"} and re.fullmatch(
            r"#[A-Za-z_][\w:.-]*",
            value,
        ):
            continue
        if name == "xmlns" and value == "http://www.w3.org/2000/svg":
            continue
        if name == "xmlns:xlink" and value == "http://www.w3.org/1999/xlink":
            continue
        raise ValueError(
            f"visual-v2 CC contains load-capable resource attribute {name!r}"
        )


STATIC_CSS = r"""
:root {
  color-scheme: light dark;
  --bg: #f4f1ea;
  --paper: #fffdf8;
  --ink: #22272f;
  --muted: #626b78;
  --line: #d8d1c5;
  --brand: #6e4f38;
  --accent: #176f74;
  --soft: #efe7da;
  --strong: #f5df9d;
  --shadow: 0 18px 52px rgba(52, 41, 31, .12);
  font-family: "Noto Sans KR", "Malgun Gothic", system-ui, sans-serif;
  font-size: 17px;
  line-height: 1.78;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; background: var(--bg); }
body {
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(circle at 10% 0, rgba(23, 111, 116, .10), transparent 28rem),
    radial-gradient(circle at 95% 18%, rgba(110, 79, 56, .09), transparent 25rem),
    var(--bg);
  overflow-wrap: anywhere;
}
.skip-link {
  position: fixed;
  z-index: 20;
  inset: .75rem auto auto .75rem;
  padding: .65rem .9rem;
  color: #fff;
  background: #17202a;
  border-radius: .55rem;
  transform: translateY(-180%);
}
.skip-link:focus { transform: none; }
#ai-content-placeholder {
  display: block;
  width: min(100% - 2rem, 1040px);
  margin: 2rem auto;
  padding: clamp(1.1rem, 4vw, 3.5rem);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 1.4rem;
  box-shadow: var(--shadow);
}
.header {
  margin: 0 0 2.25rem;
  padding: 0 0 1.5rem;
  text-align: center;
  border-bottom: 2px solid var(--line);
}
h1, h2, h3 { line-height: 1.32; text-wrap: balance; }
h1 { margin: 0 0 .75rem; color: var(--brand); font-size: clamp(2rem, 6vw, 3.25rem); }
h2 {
  margin: 2.8rem 0 1.25rem;
  padding: .55rem 0 .55rem 1rem;
  color: var(--brand);
  border-left: .35rem solid var(--accent);
  font-size: clamp(1.45rem, 4vw, 2rem);
}
h3 { margin: 2rem 0 .8rem; color: var(--accent); font-size: clamp(1.15rem, 3vw, 1.4rem); }
p { margin: .8rem 0 1.1rem; text-align: justify; }
.subtitle { color: var(--muted); font-size: 1.08rem; text-align: center; }
.content-section { margin: 0 0 2.25rem; }
.type-key-terms, .type-summary, blockquote, details {
  margin: 1.3rem 0;
  padding: 1rem 1.2rem;
  background: color-mix(in srgb, var(--soft) 72%, var(--paper));
  border: 1px solid var(--line);
  border-radius: .9rem;
}
.keyword-list { display: flex; flex-wrap: wrap; gap: .55rem; }
.keyword-chip {
  display: inline-block;
  padding: .35rem .7rem;
  color: #fff;
  background: var(--accent);
  border-radius: 999px;
  font-size: .92rem;
  font-weight: 700;
}
strong { padding: .03rem .18rem; background: var(--strong); border-radius: .2rem; }
.image-alt { display: block; margin: 1rem 0; padding: .8rem 1rem; color: var(--muted); border: 1px dashed var(--line); border-radius: .7rem; }
ul, ol { padding-left: 1.45rem; }
li + li { margin-top: .45rem; }
code, pre { font-family: "Cascadia Code", Consolas, monospace; }
code { padding: .12rem .3rem; background: var(--soft); border-radius: .3rem; }
pre { overflow-x: auto; padding: 1rem; background: #17202a; color: #f4f6f7; border-radius: .8rem; }
table { width: 100%; margin: 1.3rem 0; border-collapse: collapse; font-size: .95rem; }
caption { margin-bottom: .55rem; color: var(--brand); font-weight: 800; text-align: left; }
th, td { padding: .65rem .7rem; border: 1px solid var(--line); vertical-align: top; }
th { background: var(--soft); text-align: left; }
mark { padding: .05rem .2rem; background: var(--strong); }
[data-component="image-placeholder"], [data-component="visualization-placeholder"] {
  min-height: 6rem;
  margin: 1.25rem 0;
  padding: 1rem 1.15rem;
  color: var(--muted);
  background: linear-gradient(135deg, rgba(23,111,116,.08), rgba(110,79,56,.08));
  border: 1px dashed var(--accent);
  border-radius: .9rem;
}
[data-component="image-placeholder"]::before,
[data-component="visualization-placeholder"]::before {
  display: block;
  margin-bottom: .4rem;
  color: var(--accent);
  font-weight: 800;
}
[data-component="image-placeholder"]::before { content: "🖼️ 이미지 설계"; }
[data-component="visualization-placeholder"]::before { content: "📊 구조 시각화 설계"; }
[data-component]::after { content: attr(data-prompt); display: block; font-size: .9rem; }
.ailey-attribution {
  width: min(100% - 2rem, 1040px);
  margin: -1rem auto 2rem;
  color: var(--muted);
  font-size: .78rem;
  text-align: center;
}
a { color: var(--accent); text-underline-offset: .2em; }
:focus-visible { outline: 3px solid #e59400; outline-offset: 3px; }
@media (max-width: 640px) {
  :root { font-size: 16px; }
  #ai-content-placeholder { width: 100%; margin: 0; padding: 1.05rem; border: 0; border-radius: 0; }
  p { text-align: left; }
  table { display: block; overflow-x: auto; white-space: nowrap; }
  .ailey-attribution { width: 100%; margin: 0; padding: 1rem; }
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #11151a;
    --paper: #191f26;
    --ink: #e8edf2;
    --muted: #aeb7c2;
    --line: #39434e;
    --brand: #efc39e;
    --accent: #79d0d1;
    --soft: #28313b;
    --strong: #5c4b1e;
    --shadow: 0 18px 52px rgba(0, 0, 0, .35);
  }
  .keyword-chip { color: #102526; background: #79d0d1; }
  pre { background: #0c0f13; }
}
@media print {
  :root { color-scheme: light; --bg: #fff; --paper: #fff; --ink: #000; --line: #bbb; }
  body { background: #fff; }
  #ai-content-placeholder { width: 100%; margin: 0; padding: 0; border: 0; box-shadow: none; }
  .skip-link, .ailey-attribution, [data-component] { display: none; }
}
""".strip()


VISUAL_STATIC_CSS = r"""
:root {
  color-scheme: light;
  font-family: "Malgun Gothic", "Apple SD Gothic Neo", system-ui, sans-serif;
  font-size: 17px;
  line-height: 1.65;
}
* { box-sizing: border-box; }
html, body { min-width: 320px; margin: 0; }
body { overflow-wrap: anywhere; }
#ai-content-placeholder { display: block; min-height: 100vh; }
svg { display: block; max-width: 100%; height: auto; }
table { max-width: 100%; border-collapse: collapse; }
.skip-link {
  position: absolute;
  z-index: 1000;
  inset: .5rem auto auto .5rem;
  padding: .65rem .9rem;
  color: #fff;
  background: #111827;
  border-radius: .4rem;
  transform: translateY(-180%);
}
.skip-link:focus { transform: none; }
.ailey-attribution {
  max-width: 72rem;
  margin: 0 auto;
  padding: 1rem;
  color: #4b5563;
  background: #fff;
  font-size: .75rem;
  line-height: 1.5;
  text-align: center;
}
:focus-visible { outline: 3px solid #b45309; outline-offset: 3px; }
@media (max-width: 640px) {
  :root { font-size: 16px; }
  .ailey-attribution { padding: .85rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}
@media print {
  .skip-link, .ailey-attribution { display: none; }
}
""".strip()


def extract_html_response(raw_response: str, *, strict: bool = False) -> str:
    """Return the first complete HTML document from the `.cc` assistant turn."""
    source = raw_response.lstrip("\ufeff").strip()
    if strict:
        if DOCTYPE_RE.match(source) is None:
            raise ValueError("visual-v2 CC response must start with <!doctype html>")
        closes = list(HTML_CLOSE_RE.finditer(source))
        if len(closes) != 1 or closes[0].end() != len(source):
            raise ValueError(
                "visual-v2 CC response must end with exactly one closing </html>"
            )
        return source
    start_match = DOCTYPE_RE.search(source)
    if start_match is None:
        html_match = re.search(r"<html\b", source, re.IGNORECASE)
        if html_match is None:
            raise ValueError("CC response does not contain an HTML document")
        start = html_match.start()
        source = "<!doctype html>\n" + source[start:]
    else:
        source = source[start_match.start():]
    closes = list(HTML_CLOSE_RE.finditer(source))
    if not closes:
        raise ValueError("CC response does not contain a closing </html>")
    return source[:closes[0].end()].strip()


def _strip_executable_shell(main_html: str) -> str:
    """Remove active/resource markup without rewriting educational text."""
    def preserve_image_alt(match: re.Match[str]) -> str:
        alt_match = ALT_ATTR_RE.search(match.group("attrs"))
        if alt_match is None:
            return ""
        alt = next(
            value
            for value in alt_match.group("double", "single", "bare")
            if value is not None
        )
        if not alt.strip():
            return ""
        return f'<span class="image-alt">{html.escape(html.unescape(alt))}</span>'

    value = COMMENT_RE.sub("", main_html)
    previous = None
    while previous != value:
        previous = value
        value = BLOCKED_BLOCK_RE.sub("", value)
        value = SELF_CLOSING_ACTIVE_RE.sub("", value)
    value = IMG_RE.sub(preserve_image_alt, value)
    value = BLOCKED_VOID_RE.sub("", value)
    value = EVENT_ATTR_RE.sub("", value)
    value = STYLE_ATTR_RE.sub("", value)
    value = RESOURCE_ATTR_RE.sub(_strip_resource_attribute, value)
    value = HIDDEN_ATTR_RE.sub("", value)
    if _first_unsafe_main_tag(value) is not None:
        raise ValueError("CC main retains an unsafe raw-text or active tag")
    return value.strip()


def staticize_cc_response(
    raw_response: str,
    *,
    course_id: str,
    course_title: str,
    lesson_id: str,
    lesson_title: str,
    topics: list[str],
    profile: str = CC_PROFILE,
    context_ff_sha256: str | None = None,
    model_instructions_sha256: str | None = None,
    codex_thread_id: str | None = None,
    codex_model: str | None = None,
    codex_reasoning: str | None = None,
) -> str:
    """Preserve live CC body text and replace only its unsafe app shell."""
    try:
        staticizer_profile = STATICIZER_PROFILES[profile]
    except KeyError as error:
        raise ValueError(f"unknown CC prompt profile: {profile}") from error
    is_visual_v2 = profile == CC_VISUAL_PROFILE
    generation_method = (
        "codex-live-same-context-static-visual-v2"
        if is_visual_v2
        else "codex-live-same-context-cc-staticized"
    )
    raw_html = extract_html_response(raw_response, strict=is_visual_v2)
    if is_visual_v2:
        _validate_visual_raw_markup(raw_html)
    lesson_css = collect_sanitized_lesson_css(raw_html, profile=profile)
    main_match = MAIN_RE.search(raw_html)
    if main_match is None:
        raise ValueError('CC HTML lacks id="ai-content-placeholder" main')
    raw_main = main_match.group(0)
    raw_visible_text = _normalized_visible_text(raw_main)
    required = [course_title, lesson_id, lesson_title, *topics]
    missing = [value for value in required if value not in raw_visible_text]
    if missing:
        raise ValueError(
            f"raw CC visible body is missing exact lesson identity/topics: {missing}"
        )

    sanitized_main = _strip_executable_shell(raw_main)
    opening_end = sanitized_main.find(">")
    if opening_end < 0:
        raise ValueError("CC main opening tag is malformed")
    main_classes = _safe_class_tokens(
        sanitized_main[:opening_end + 1],
        required=("ailey-canvas",),
    )
    sanitized_main = (
        '<main id="ai-content-placeholder" '
        f'class="{html.escape(" ".join(main_classes), quote=True)}" '
        f'data-course="{html.escape(course_id, quote=True)}" '
        f'data-lesson="{html.escape(lesson_id, quote=True)}">'
        + sanitized_main[opening_end + 1:]
    )
    sanitized_visible_text = _normalized_visible_text(sanitized_main)
    if sanitized_visible_text != raw_visible_text:
        raise ValueError("staticization changed the normalized visible CC body text")

    title_match = TITLE_RE.search(raw_html)
    raw_title = (
        re.sub(r"<[^>]+>", "", title_match.group("title")).strip()
        if title_match
        else f"{lesson_id}. {lesson_title}"
    )
    raw_digest = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
    source_digest = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()
    lesson_css_digest = (
        hashlib.sha256(lesson_css.encode("utf-8")).hexdigest()
        if lesson_css
        else ""
    )
    lesson_css_meta = (
        f'<meta name="lesson-css-sha256" content="{lesson_css_digest}">\n'
        if lesson_css_digest
        else ""
    )
    lesson_css_block = (
        '<style data-ailey-lesson-css="sanitized" '
        f'data-css-sha256="{lesson_css_digest}">\n'
        f'{lesson_css}\n'
        '</style>'
        if lesson_css
        else ""
    )
    generation_audit_meta = ""
    if is_visual_v2:
        digests = {
            "context-ff-sha256": context_ff_sha256,
            "model-instructions-sha256": model_instructions_sha256,
        }
        invalid_digests = [
            name
            for name, value in digests.items()
            if not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{64}", value) is None
        ]
        if invalid_digests:
            raise ValueError(
                f"visual-v2 CC is missing valid generation digest(s): {invalid_digests}"
            )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (codex_thread_id, codex_model, codex_reasoning)
        ):
            raise ValueError("visual-v2 CC is missing Codex generation audit fields")
        thread_digest = hashlib.sha256(codex_thread_id.encode("utf-8")).hexdigest()
        audit_values = {
            **digests,
            "codex-thread-sha256": thread_digest,
            "generation-model": codex_model,
            "generation-reasoning": codex_reasoning,
        }
        generation_audit_meta = "".join(
            f'<meta name="{name}" content="{html.escape(value, quote=True)}">\n'
            for name, value in audit_values.items()
            if isinstance(value, str)
        )
    canvas_id = f"ailey-codex-live-{course_id}-{lesson_id}-{raw_digest[:12]}"
    body_match = BODY_OPEN_RE.search(raw_html)
    body_classes = _safe_class_tokens(body_match.group(0) if body_match else "")
    body_open = (
        f'<body class="{html.escape(" ".join(body_classes), quote=True)}">'
        if body_classes
        else "<body>"
    )
    csp = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "font-src data:; script-src 'none'; connect-src 'none'; "
        "frame-src 'none'; object-src 'none'; media-src 'none'; "
        "worker-src 'none'; manifest-src 'none'; base-uri 'none'; "
        "form-action 'none'"
    )
    output = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="canvas-id" content="{html.escape(canvas_id, quote=True)}">
<meta name="prompt-profile" content="{html.escape(profile, quote=True)}">
<meta name="upstream-commit" content="{UPSTREAM_COMMIT}">
<meta name="raw-cc-sha256" content="{raw_digest}">
<meta name="source-cc-sha256" content="{source_digest}">
{lesson_css_meta}{generation_audit_meta}<meta name="generation-method" content="{generation_method}">
<meta name="source-turn" content=".cc-after-.ff-same-context">
<meta name="staticizer-profile" content="{staticizer_profile}">
<meta name="upstream-custom-gpt-invoked" content="false">
<title>{html.escape(raw_title)}</title>
<style data-ailey-base-css="{staticizer_profile}">
{VISUAL_STATIC_CSS if is_visual_v2 else STATIC_CSS}
</style>
{lesson_css_block}
</head>
{body_open}
<a class="skip-link" href="#ai-content-placeholder">본문으로 건너뛰기</a>
{sanitized_main}
<footer class="ailey-attribution">
  Ailey &amp; Bailey Canvas by fewweekslater (Ray You) · adapted by OpenAI Codex ·
  CC BY-NC-SA 4.0 · GitHub prompt를 적용한 live `.ff → .cc` 응답을
  Study Factory에서 안전하게 정적화함
</footer>
</body>
</html>
"""
    errors = codex_artifact_quality_errors("cc", output, topics)
    if lesson_id not in output or lesson_title not in output:
        errors.append("static CC does not retain exact lesson identity")
    if errors:
        raise ValueError("static CC validation failed: " + "; ".join(errors))
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_response", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--course-id", required=True)
    parser.add_argument("--course-title", required=True)
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--lesson-title", required=True)
    parser.add_argument("--topic", action="append", dest="topics", required=True)
    parser.add_argument(
        "--profile",
        choices=sorted(STATICIZER_PROFILES),
        default=CC_PROFILE,
    )
    parser.add_argument("--context-ff-sha256")
    parser.add_argument("--model-instructions-sha256")
    parser.add_argument("--codex-thread-id")
    parser.add_argument("--codex-model")
    parser.add_argument("--codex-reasoning")
    args = parser.parse_args()
    result = staticize_cc_response(
        args.raw_response.read_text(encoding="utf-8"),
        course_id=args.course_id,
        course_title=args.course_title,
        lesson_id=args.lesson_id,
        lesson_title=args.lesson_title,
        topics=args.topics,
        profile=args.profile,
        context_ff_sha256=args.context_ff_sha256,
        model_instructions_sha256=args.model_instructions_sha256,
        codex_thread_id=args.codex_thread_id,
        codex_model=args.codex_model,
        codex_reasoning=args.codex_reasoning,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
