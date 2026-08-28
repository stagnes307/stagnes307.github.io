#!/usr/bin/env python3
"""Pinned public Ailey prompt assembly and Study Factory quality gates."""

from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any

from common import FACTORY_ROOT, codex_artifact_quality_errors


AILEY_REPOSITORY = "https://github.com/lemos999/ailey-bailey-canvas"
AILEY_COMMIT = "8a36e77d025bb9c258bfeaf8587424783140b185"
AILEY_VENDOR_ROOT = (
    FACTORY_ROOT / "vendor" / "ailey-bailey-canvas" / "8a36e77d"
)
AILEY_MANIFEST_PATH = AILEY_VENDOR_ROOT / "manifest.json"
AILEY_OVERLAY_PATH = (
    FACTORY_ROOT / "prompts" / "ailey-bailey-public-study-v1.md"
)
AILEY_FF_PROFILE = "ailey-bailey-public-8a36e77d-ff-literal-v1"
AILEY_CC_PROFILE = "ailey-bailey-public-8a36e77d-cc-safe-v1"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
SENTENCE_END_RE = re.compile(
    r"[.!?。！？]+(?=[\"'”’)}\]]*(?:\s|$))"
)
BLOCK_START_RE = re.compile(
    r"^(?:\s*[-+*]\s+|\s*\d+[.)]\s+|\s*>|\s*\||\s*<|\s*#{1,6}\s+)"
)
REMOTE_URL_RE = re.compile(
    r"(?:https?|ftp)://[^\s<>\"']+"
    r"|(?<!:)//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s<>\"']*",
    re.IGNORECASE,
)
RAW_CC_RISKS = (
    ("command wrapper", re.compile(r"(?m)^\s*\.cc[c]?\b", re.IGNORECASE)),
    (
        "Markdown HTML fence",
        re.compile(r"(?m)^\s*`{3,}\s*html\b", re.IGNORECASE),
    ),
    ("active script", re.compile(r"<\s*script\b", re.IGNORECASE)),
    (
        "external resource tag",
        re.compile(r"<\s*(?:link|iframe|object|embed)\b", re.IGNORECASE),
    ),
    ("CSS import", re.compile(r"@import\b", re.IGNORECASE)),
    ("javascript URL", re.compile(r"javascript\s*:", re.IGNORECASE)),
    ("inline event handler", re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)),
    (
        "hidden content",
        re.compile(
            r"id=[\"']ai-content-placeholder[\"'][^>]*"
            r"(?:display\s*:\s*none|visibility\s*:\s*hidden|\bhidden\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "invalid Korean language tag",
        re.compile(r"<html\b[^>]*\blang=[\"']KR[\"']", re.IGNORECASE),
    ),
    (
        "upstream executable app shell",
        re.compile(
            r"(?:renderAppShell|loadContentFrom|DOMContentLoaded|"
            r"sessionStorage|localStorage)",
            re.IGNORECASE,
        ),
    ),
)


def load_vendor_manifest(
    path: Path = AILEY_MANIFEST_PATH,
) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{path}: root must be an object")
    return manifest


def _safe_vendor_path(relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    resolved = (AILEY_VENDOR_ROOT / path).resolve()
    try:
        resolved.relative_to(AILEY_VENDOR_ROOT.resolve())
    except ValueError:
        return None
    return resolved


def _file_record_errors(
    label: str,
    record: object,
) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label}: file record must be an object"]
    path = _safe_vendor_path(record.get("path"))
    if path is None:
        return [f"{label}: invalid path"]
    if not path.is_file():
        return [f"{label}: missing vendored file {path}"]
    payload = path.read_bytes()
    errors: list[str] = []
    if record.get("bytes") != len(payload):
        errors.append(
            f"{label}: byte count mismatch "
            f"(manifest {record.get('bytes')!r}, actual {len(payload)})"
        )
    digest = hashlib.sha256(payload).hexdigest()
    if record.get("sha256") != digest:
        errors.append(f"{label}: sha256 mismatch")
    return errors


def vendor_snapshot_errors(
    manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Verify the pinned file set, order, license, sizes, and SHA-256 values."""
    if manifest is None:
        try:
            manifest = load_vendor_manifest()
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return [f"cannot load Ailey vendor manifest: {exc}"]

    errors: list[str] = []
    if manifest.get("version") != 1:
        errors.append("Ailey manifest version must be 1")
    if manifest.get("repository") != AILEY_REPOSITORY:
        errors.append("Ailey manifest repository does not match the pinned source")
    if manifest.get("commit") != AILEY_COMMIT:
        errors.append("Ailey manifest commit does not match the pinned full SHA")
    if not isinstance(manifest.get("source_instruction"), str):
        errors.append("Ailey manifest must record the README assembly instruction")
    if manifest.get("text_normalization") != (
        "none; byte-identical upstream Git blobs"
    ):
        errors.append("Ailey vendor files must be byte-identical upstream blobs")

    assembly_order = manifest.get("assembly_order")
    files = manifest.get("files")
    if not isinstance(assembly_order, list) or not all(
        isinstance(path, str) for path in assembly_order
    ):
        errors.append("Ailey manifest assembly_order must be a string array")
        assembly_order = []
    if assembly_order != sorted(assembly_order):
        errors.append("Ailey manifest assembly_order must be lexically sorted")
    if len(assembly_order) != len(set(assembly_order)):
        errors.append("Ailey manifest assembly_order contains duplicates")
    if len(assembly_order) != 16:
        errors.append(
            f"Ailey manifest must contain exactly 16 prompt files "
            f"(found {len(assembly_order)})"
        )
    for relative in assembly_order:
        if not re.fullmatch(r"prompt_src/.+\.prompt\.txt", relative):
            errors.append(f"Ailey manifest has an invalid prompt path: {relative!r}")

    if not isinstance(files, list):
        errors.append("Ailey manifest files must be an array")
        files = []
    file_paths = [
        record.get("path") if isinstance(record, dict) else None
        for record in files
    ]
    if file_paths != assembly_order:
        errors.append("Ailey manifest files must match assembly_order exactly")
    for index, record in enumerate(files):
        errors.extend(_file_record_errors(f"files[{index}]", record))

    disk_prompts = sorted(
        path.relative_to(AILEY_VENDOR_ROOT).as_posix()
        for path in AILEY_VENDOR_ROOT.glob("prompt_src/**/*.prompt.txt")
        if path.is_file()
    )
    if disk_prompts != assembly_order:
        errors.append("vendored prompt file set does not match assembly_order")

    license_record = manifest.get("license")
    if not isinstance(license_record, dict):
        errors.append("Ailey manifest license must be an object")
    else:
        if license_record.get("spdx") != "CC-BY-NC-SA-4.0":
            errors.append("Ailey manifest license must be CC-BY-NC-SA-4.0")
        if license_record.get("path") != "LICENSE":
            errors.append("Ailey manifest license path must be LICENSE")
        errors.extend(_file_record_errors("license", license_record))
    return errors


def assemble_upstream_prompt() -> str:
    """Assemble all pinned upstream prompt modules in manifest order."""
    manifest = load_vendor_manifest()
    errors = vendor_snapshot_errors(manifest)
    if errors:
        raise ValueError("invalid Ailey vendor snapshot: " + "; ".join(errors))
    parts = [
        (AILEY_VENDOR_ROOT / relative).read_text(encoding="utf-8").rstrip("\n")
        for relative in manifest["assembly_order"]
    ]
    return "\n\n".join(parts) + "\n"


def assemble_public_system_prompt() -> str:
    """Return the immutable upstream bundle followed by the local safety overlay."""
    upstream = assemble_upstream_prompt().rstrip("\n")
    overlay = AILEY_OVERLAY_PATH.read_text(encoding="utf-8").strip()
    return f"{upstream}\n\n{overlay}\n"


def public_profile_fingerprint() -> str:
    """Return the SHA-256 of the pinned upstream bundle plus local overlay."""
    source = assemble_public_system_prompt().encode("utf-8")
    return hashlib.sha256(source).hexdigest()


def _markdown_headings(source: str) -> list[tuple[int, str, int]]:
    headings: list[tuple[int, str, int]] = []
    active_fence: tuple[str, int] | None = None
    for line_number, line in enumerate(source.splitlines(), start=1):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if active_fence is None:
                active_fence = (marker[0], len(marker))
            elif (
                marker[0] == active_fence[0]
                and len(marker) >= active_fence[1]
                and not fence.group(2).strip()
            ):
                active_fence = None
            continue
        if active_fence is not None:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2), line_number))
    return headings


def _is_single_codepoint_emoji(character: str) -> bool:
    value = ord(character)
    return (
        0x1F000 <= value <= 0x1FAFF
        or 0x2600 <= value <= 0x27BF
        or 0x2300 <= value <= 0x23FF
        or 0x2B00 <= value <= 0x2BFF
    )


def _heading_prefix_emoji(title: str) -> str | None:
    value = title.strip()
    if not value or not _is_single_codepoint_emoji(value[0]):
        return None
    if len(value) > 1 and (
        value[1] in {"\ufe0e", "\ufe0f", "\u200d"}
        or _is_single_codepoint_emoji(value[1])
    ):
        return None
    return value[0]


def _first_paragraph_after(
    lines: list[str],
    heading_line_number: int,
) -> tuple[str | None, str | None]:
    index = heading_line_number
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return None, "has no body paragraph"
    first = lines[index]
    if (
        FENCE_RE.match(first)
        or BLOCK_START_RE.match(first)
        or re.match(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", first)
    ):
        return None, "first body block must be a plain paragraph"
    paragraph_lines: list[str] = []
    while index < len(lines) and lines[index].strip():
        if HEADING_RE.match(lines[index]) or FENCE_RE.match(lines[index]):
            break
        paragraph_lines.append(lines[index].strip())
        index += 1
    if not paragraph_lines:
        return None, "has no body paragraph"
    return " ".join(paragraph_lines), None


def ailey_public_ff_quality_errors(
    source: str,
    topics: list[str],
    *,
    lesson_id: str | None = None,
    lesson_title: str | None = None,
) -> list[str]:
    """Validate the literal public-Ailey FF contract used by the safe renderer."""
    errors = codex_artifact_quality_errors("ff", source, topics)
    headings = _markdown_headings(source)
    h1 = [heading for heading in headings if heading[0] == 1]
    h2 = [heading for heading in headings if heading[0] == 2]
    h3 = [heading for heading in headings if heading[0] == 3]
    deeper = [heading for heading in headings if heading[0] >= 4]

    if len(h1) != 1:
        errors.append(f"must contain exactly one H1 (found {len(h1)})")
    elif lesson_id is not None and lesson_title is not None:
        expected_h1 = f"{lesson_id}. {lesson_title}"
        if h1[0][1] != expected_h1:
            errors.append(f"H1 must be exactly {expected_h1!r}")
    if len(h2) != 5:
        errors.append(f"must contain exactly five H2 headings (found {len(h2)})")
    if len(h3) != 15:
        errors.append(f"must contain exactly fifteen H3 headings (found {len(h3)})")
    if deeper:
        errors.append(
            f"must not contain H4-H6 headings (found {len(deeper)})"
        )

    h3_by_h2: list[list[tuple[int, str, int]]] = []
    current: list[tuple[int, str, int]] | None = None
    for heading in headings:
        if heading[0] == 2:
            current = []
            h3_by_h2.append(current)
        elif heading[0] == 3:
            if current is None:
                errors.append(
                    f"H3 at line {heading[2]} appears before the first H2"
                )
            else:
                current.append(heading)
    if len(h3_by_h2) == 5:
        for index, children in enumerate(h3_by_h2, start=1):
            if len(children) != 3:
                errors.append(
                    f"H2 {index} must contain exactly three H3 headings "
                    f"(found {len(children)})"
                )

    prefix_emojis: list[str] = []
    for level, title, line_number in h2 + h3:
        emoji = _heading_prefix_emoji(title)
        if emoji is None:
            errors.append(
                f"H{level} at line {line_number} must start with one "
                "single-codepoint emoji"
            )
        else:
            prefix_emojis.append(emoji)
    if len(set(prefix_emojis)) != len(prefix_emojis):
        errors.append("all twenty H2/H3 heading emojis must be unique")

    lines = source.splitlines()
    for _, title, line_number in h3:
        paragraph, error = _first_paragraph_after(lines, line_number)
        if error:
            errors.append(f"H3 {title!r} at line {line_number} {error}")
            continue
        assert paragraph is not None
        sentence_count = len(SENTENCE_END_RE.findall(paragraph))
        if not 15 <= sentence_count <= 20:
            errors.append(
                f"H3 {title!r} first paragraph must contain 15-20 sentences "
                f"(found {sentence_count})"
            )

    if len(h3_by_h2) == 5 and len(h3_by_h2[4]) == 3:
        final_titles = [heading[1] for heading in h3_by_h2[4]]
        if "통합 적용" not in final_titles[0]:
            errors.append("fifth H2 first H3 must be the 통합 적용 section")
        if not all(
            token in final_titles[1]
            for token in ("확인 문제", "정답", "해설")
        ):
            errors.append(
                "fifth H2 second H3 must be the 확인 문제와 정답·해설 section"
            )
        if "요약" not in final_titles[2]:
            errors.append("fifth H2 third H3 must be the 요약 section")

    for token in ("확인 문제", "정답", "해설", "요약"):
        if token not in source:
            errors.append(f"must include {token}")
    if re.search(r"(?m)^\s*\.(?:cc|ccc)\b", source, re.IGNORECASE):
        errors.append("must not contain raw .cc/.ccc command output")
    if re.search(
        r"(?:COMPASS NAVIGATION|AWAITING YOUR COMMAND|CURRENT TIMESTAMP)",
        source,
        re.IGNORECASE,
    ):
        errors.append("must not contain upstream navigation or timestamp chrome")
    return list(dict.fromkeys(errors))


def _validated_allowed_urls(
    allowed_urls: list[str] | tuple[str, ...] | set[str] | None,
) -> tuple[set[str], list[str]]:
    allowed: set[str] = set()
    errors: list[str] = []
    for url in allowed_urls or ():
        if not isinstance(url, str):
            errors.append("allowed official URL must be a string")
            continue
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or any(character.isspace() for character in url)
        ):
            errors.append(
                f"allowed official URL must be an absolute http/https URL: {url!r}"
            )
            continue
        allowed.add(url)
    return allowed, errors


class _OfficialNavigationParser(HTMLParser):
    """Allow remote navigation only for exact registered official-source links."""

    def __init__(self, allowed_urls: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.allowed_urls = allowed_urls
        self.seen_allowed_urls: set[str] = set()
        self.errors: list[str] = []
        self.open_tags: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        self.open_tags.append(tag)
        normalized = [(name.lower(), value) for name, value in attrs]
        approved_href: str | None = None
        for name, value in normalized:
            if not isinstance(value, str) or not REMOTE_URL_RE.search(value):
                continue
            if tag == "a" and name == "href" and value in self.allowed_urls:
                approved_href = value
                self.seen_allowed_urls.add(value)
            else:
                self.errors.append(
                    f"contains unapproved remote URL in <{tag}> {name}"
                )

        if approved_href is None:
            return
        href_values = [
            value for name, value in normalized if name == "href"
        ]
        target_values = [
            value for name, value in normalized if name == "target"
        ]
        rel_values = [
            value for name, value in normalized if name == "rel"
        ]
        if href_values != [approved_href]:
            self.errors.append(
                "official source link must contain exactly one approved href"
            )
        if target_values != ["_blank"]:
            self.errors.append(
                "official source link must set target=\"_blank\""
            )
        rel_tokens = (
            set(rel_values[0].lower().split())
            if len(rel_values) == 1 and isinstance(rel_values[0], str)
            else set()
        )
        if not {"noopener", "noreferrer"}.issubset(rel_tokens):
            self.errors.append(
                "official source link must set rel=\"noopener noreferrer\""
            )

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index] == tag:
                del self.open_tags[index:]
                return

    def handle_data(self, data: str) -> None:
        remote_context = next(
            (
                tag
                for tag in reversed(self.open_tags)
                if tag in {"script", "style"}
            ),
            None,
        )
        if remote_context is not None and REMOTE_URL_RE.search(data):
            self.errors.append(
                f"contains unapproved remote URL in "
                f"<{remote_context}> data"
            )


def _mask_allowed_urls_for_validation(
    source: str,
    allowed_urls: set[str],
) -> str:
    """Mask approved URL spellings only after HTML context validation."""
    variants = {
        variant
        for url in allowed_urls
        for variant in (
            url,
            html.escape(url, quote=False),
            html.escape(url, quote=True),
        )
    }
    sanitized = source
    for variant in sorted(variants, key=len, reverse=True):
        sanitized = sanitized.replace(
            variant,
            "/study/allowlisted-official-source",
        )
    return sanitized


def raw_upstream_cc_errors(
    source: str,
    topics: list[str] | None = None,
    *,
    allowed_urls: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[str]:
    """Reject raw CC risks, except exact allowlisted official navigation links."""
    allowed, errors = _validated_allowed_urls(allowed_urls)
    navigation = _OfficialNavigationParser(allowed)
    navigation.feed(source)
    navigation.close()
    errors.extend(navigation.errors)
    missing_links = sorted(allowed - navigation.seen_allowed_urls)
    if missing_links:
        errors.append(
            f"must render every allowed official URL: {missing_links}"
        )
    sanitized_source = _mask_allowed_urls_for_validation(source, allowed)
    errors.extend([
        f"contains raw upstream CC risk: {label}"
        for label, pattern in RAW_CC_RISKS
        if pattern.search(sanitized_source)
    ])
    errors.extend(
        codex_artifact_quality_errors("cc", sanitized_source, topics or [])
    )
    if allowed and 'id="official-sources-title"' not in source:
        errors.append("must include a visible 공식 출처 panel")
    if "CC BY-NC-SA 4.0" not in source:
        errors.append("must include visible CC BY-NC-SA 4.0 attribution")
    if "adapted by OpenAI Codex" not in source:
        errors.append("must include visible adapted by OpenAI Codex attribution")
    return list(dict.fromkeys(errors))
