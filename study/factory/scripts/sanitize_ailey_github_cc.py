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


FF_PROFILE = "ailey-bailey-public-8a36e77d-ff-codex-live-v1"
CC_PROFILE = "ailey-bailey-public-8a36e77d-cc-codex-live-static-v1"
UPSTREAM_COMMIT = "8a36e77d025bb9c258bfeaf8587424783140b185"

DOCTYPE_RE = re.compile(r"<!doctype\s+html\b", re.IGNORECASE)
HTML_CLOSE_RE = re.compile(r"</html\s*>", re.IGNORECASE)
MAIN_RE = re.compile(
    r"<main\b(?=[^>]*\bid=[\"']ai-content-placeholder[\"'])[^>]*>"
    r"(?P<body>.*?)</main\s*>",
    re.IGNORECASE | re.DOTALL,
)
TITLE_RE = re.compile(r"<title\b[^>]*>(?P<title>.*?)</title\s*>", re.IGNORECASE | re.DOTALL)
BLOCKED_BLOCK_RE = re.compile(
    r"<(?P<tag>script|style|iframe|object|embed|template|noscript)\b[^>]*>"
    r".*?</(?P=tag)\s*>",
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
    r"\s+(?:src|href|srcset|action|formaction)\s*=\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
HIDDEN_ATTR_RE = re.compile(r"\s+hidden(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))?", re.IGNORECASE)
FENCE_RE = re.compile(r"^```(?:html)?\s*|\s*```$", re.IGNORECASE)
RESIDUAL_UNSAFE_TAG_RE = re.compile(
    r"<(?:script|style|iframe|object|embed|template|noscript|noembed|noframes|textarea|title|xmp|plaintext)\b",
    re.IGNORECASE,
)
TEXT_AUDIT_IGNORED_TAGS = frozenset({"script", "style", "template", "noscript"})


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
    unsafe = RESIDUAL_UNSAFE_TAG_RE.search(match.group(0))
    if unsafe is None:
        return None
    return unsafe.group(0)


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


def extract_html_response(raw_response: str) -> str:
    """Return the first complete HTML document from the `.cc` assistant turn."""
    source = raw_response.lstrip("\ufeff").strip()
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
    value = IMG_RE.sub(preserve_image_alt, value)
    value = BLOCKED_VOID_RE.sub("", value)
    value = EVENT_ATTR_RE.sub("", value)
    value = STYLE_ATTR_RE.sub("", value)
    value = RESOURCE_ATTR_RE.sub("", value)
    value = HIDDEN_ATTR_RE.sub("", value)
    if RESIDUAL_UNSAFE_TAG_RE.search(value):
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
) -> str:
    """Preserve live CC body text and replace only its unsafe app shell."""
    raw_html = extract_html_response(raw_response)
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
    sanitized_main = (
        '<main id="ai-content-placeholder" class="ailey-canvas" '
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
    canvas_id = f"ailey-codex-live-{course_id}-{lesson_id}-{raw_digest[:12]}"
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
<meta name="prompt-profile" content="{CC_PROFILE}">
<meta name="upstream-commit" content="{UPSTREAM_COMMIT}">
<meta name="raw-cc-sha256" content="{raw_digest}">
<meta name="source-cc-sha256" content="{source_digest}">
<meta name="generation-method" content="codex-live-same-context-cc-staticized">
<meta name="source-turn" content=".cc-after-.ff-same-context">
<meta name="staticizer-profile" content="ailey-public-live-static-v1">
<meta name="upstream-custom-gpt-invoked" content="false">
<title>{html.escape(raw_title)}</title>
<style>
{STATIC_CSS}
</style>
</head>
<body>
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
    args = parser.parse_args()
    result = staticize_cc_response(
        args.raw_response.read_text(encoding="utf-8"),
        course_id=args.course_id,
        course_title=args.course_title,
        lesson_id=args.lesson_id,
        lesson_title=args.lesson_title,
        topics=args.topics,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
