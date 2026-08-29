#!/usr/bin/env python3
"""Measure and gate the visual quality of a final CC HTML document.

The live Ailey adapter can leave image-generation instructions in an otherwise
valid lesson.  Text/content validation cannot distinguish those instructions
from a finished diagram.  This module inspects the final DOM-like structure and
accepts only one of the following as a real visualization:

* an accessible, non-trivial inline SVG; or
* a substantial semantic HTML figure/diagram with an accessible name,
  multiple visual nodes, and an actual grid/flex layout.

It deliberately does not search raw HTML for placeholder words.  Doing so
would flag inert CSS selectors and source examples.  Only real placeholder
components and phrases in rendered text are rejected.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Iterator, Mapping, TypeAlias


MetricValue: TypeAlias = int | bool

MAX_DISPLAY_H1_CHARS = 80
VISUAL_V2_MIN_DISPLAY_H1_CHARS = 12
VISUAL_V2_MAX_DISPLAY_H1_CHARS = 36
VISUAL_V2_MIN_VISIBLE_TEXT_CHARS = 3_500
VISUAL_V2_MAX_TABLES = 2
TABLE_HEAVY_MIN_TABLES = 4
TABLE_HEAVY_MIN_ROWS = 24

_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})
_NON_RENDERED_ELEMENTS = frozenset({
    "head", "script", "style", "template", "noscript", "title", "desc",
})
_SCREEN_READER_ONLY_CLASSES = frozenset({
    "hidden", "sr-only", "visually-hidden", "screen-reader-only",
})
_SVG_GEOMETRY = frozenset({
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "use",
})
_SVG_NON_RENDERED_CONTAINERS = frozenset({
    "defs", "symbol", "clippath", "mask", "pattern", "marker",
})
_VISUAL_NODE_TAGS = frozenset({"li", "dt", "dd"})

_PLACEHOLDER_COMPONENT_RE = re.compile(
    r"^(?:image|visuali[sz]ation|diagram|chart)[-_ ]?placeholder$"
    r"|^placeholder[-_ ]?(?:image|visuali[sz]ation|diagram|chart)$",
    re.IGNORECASE,
)
_VISIBLE_PLACEHOLDER_PATTERNS = (
    re.compile(r"(?:이미지\s*설계|구조\s*시각화\s*설계)"),
    re.compile(
        r"\b(?:image|visuali[sz]ation|diagram|chart)\s+placeholder\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bplaceholder\s+for\s+(?:an?\s+)?"
        r"(?:image|visuali[sz]ation|diagram|chart)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:insert|add)\s+(?:an?\s+)?"
        r"(?:image|visuali[sz]ation|diagram|chart)\s+here\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:TODO|TBD)\s*:?\s*"
        r"(?:image|visuali[sz]ation|diagram|chart)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:이미지|도식|차트|시각화)\s*(?:삽입\s*)?예정"),
)
_VISUAL_KEYWORD_RE = re.compile(
    r"(?:^|[-_])(?:diagram|chart|flow|timeline|process|cycle|concept-map|"
    r"matrix|infographic|visuali[sz]ation|pipeline|roadmap|dashboard|gauge|"
    r"steps?)(?:$|[-_])",
    re.IGNORECASE,
)
_VISUAL_NODE_CLASS_RE = re.compile(
    r"(?:^|[-_])(?:step|node|stage|phase|milestone|connector|arrow|lane|"
    r"branch|segment|chart-bar|flow-item|timeline-item|cycle-item)(?:$|[-_])",
    re.IGNORECASE,
)
_DISPLAY_GRID_RE = re.compile(r"\bdisplay\s*:\s*(?:inline-)?grid\b", re.IGNORECASE)
_DISPLAY_FLEX_RE = re.compile(r"\bdisplay\s*:\s*(?:inline-)?flex\b", re.IGNORECASE)
_GRID_PROPERTY_RE = re.compile(r"\bgrid(?:-[a-z-]+)?\s*:", re.IGNORECASE)
_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_HIDDEN_STYLE_RE = re.compile(
    r"(?:\bdisplay\s*:\s*none\b|\bvisibility\s*:\s*(?:hidden|collapse)\b|"
    r"\bopacity\s*:\s*0(?:\.0+)?(?:\s*!important)?\s*(?:;|$))",
    re.IGNORECASE,
)
_TRANSFORM_DECLARATION_RE = re.compile(
    r"\btransform\s*:\s*(?P<value>[^;}]+)",
    re.IGNORECASE,
)
_SCALE_FUNCTION_RE = re.compile(
    r"\bscale(?:x|y)?\s*\((?P<arguments>[^()]*)\)",
    re.IGNORECASE,
)
_CSS_NUMBER_RE = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?",
    re.IGNORECASE,
)
_ARROW_RE = re.compile(r"[→↓↑↔⇒⇢➜➝⟶]")
_SVG_VIEWBOX_RE = re.compile(
    r"^\s*-?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[\s,]+-?(?:\d+(?:\.\d*)?|\.\d+)){3}\s*$"
)
_SVG_NUMBER_RE = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?(?:px|%)?",
    re.IGNORECASE,
)
_MAX_WIDTH_MEDIA_RE = re.compile(
    r"@media\s*(?:screen\s+and\s+)?\([^)]*max-width\s*:",
    re.IGNORECASE,
)
_PRINT_MEDIA_RE = re.compile(r"@media\s+print\b", re.IGNORECASE)
_REDUCED_MOTION_MEDIA_RE = re.compile(
    r"@media\s*\([^)]*prefers-reduced-motion\s*:\s*reduce",
    re.IGNORECASE,
)
_CSS_FLAT_BLOCK_RE = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)
_SVG_TYPE_SELECTOR_RE = re.compile(
    r"^(?:(?:\*|[-_a-z][-_a-z0-9]*)?\|)?svg(?=$|[.#:\[])",
    re.IGNORECASE,
)
_MIN_WIDTH_DECLARATION_RE = re.compile(
    r"(?:^|;)\s*min-width\s*:",
    re.IGNORECASE,
)
_CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9a-fA-F]{1,6})\s?|(.))", re.DOTALL)


def _decode_css_escapes(source: str) -> str:
    def replace(match: re.Match[str]) -> str:
        hexadecimal, escaped = match.groups()
        if hexadecimal is not None:
            value = int(hexadecimal, 16)
            if value == 0 or value > 0x10FFFF:
                return "\ufffd"
            return chr(value)
        return escaped or ""

    return _CSS_ESCAPE_RE.sub(replace, source)


def _blank_css_strings(source: str) -> str:
    """Blank quoted CSS payloads so declaration-like text cannot be audited."""

    output: list[str] = []
    quote = ""
    escaped = False
    for char in source:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            output.append("\n" if char == "\n" else " ")
            continue
        if char in {'"', "'"}:
            quote = char
            output.append(" ")
        else:
            output.append(char)
    return "".join(output)


def _split_top_level_selectors(source: str) -> list[str]:
    """Split a selector list without treating functional-pseudo commas as separators."""

    parts: list[str] = []
    start = 0
    square_depth = 0
    round_depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(source):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            square_depth += 1
        elif char == "]" and square_depth:
            square_depth -= 1
        elif char == "(":
            round_depth += 1
        elif char == ")" and round_depth:
            round_depth -= 1
        elif char == "," and not square_depth and not round_depth:
            parts.append(source[start:index].strip())
            start = index + 1
    parts.append(source[start:].strip())
    return [part for part in parts if part]


def _rightmost_selector_compound(selector: str) -> str:
    """Return the subject compound, excluding SVG mentions in ancestors/:has()."""

    start = 0
    square_depth = 0
    round_depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(selector):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "[":
            square_depth += 1
        elif char == "]" and square_depth:
            square_depth -= 1
        elif char == "(":
            round_depth += 1
        elif char == ")" and round_depth:
            round_depth -= 1
        elif not square_depth and not round_depth and (
            char.isspace() or char in ">+~"
        ):
            start = index + 1
    return selector[start:].strip()


def css_svg_min_width_rule_count(css: str) -> int:
    """Count rules whose actual subject is an SVG and declares ``min-width``.

    This deliberately distinguishes ``.frame svg`` from ``svg .caption`` and
    ignores words inside strings, custom properties, and ``:has(svg)``.
    """

    normalized = _decode_css_escapes(_CSS_COMMENT_RE.sub("", css))
    count = 0
    for match in _CSS_FLAT_BLOCK_RE.finditer(normalized):
        declarations = _blank_css_strings(match.group("body"))
        if _MIN_WIDTH_DECLARATION_RE.search(declarations) is None:
            continue
        if any(
            _SVG_TYPE_SELECTOR_RE.search(_rightmost_selector_compound(selector))
            for selector in _split_top_level_selectors(match.group("selectors"))
        ):
            count += 1
    return count


@dataclass
class VisualCCQualityResult:
    """Structured result suitable for the runner and validation reports."""

    errors: list[str]
    metrics: dict[str, MetricValue]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    content: list[str | "_Node"] = field(default_factory=list)
    parent: "_Node | None" = None

    @property
    def children(self) -> Iterator["_Node"]:
        return (item for item in self.content if isinstance(item, _Node))


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document")
        self._stack = [self.root]

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()
        node = _Node(
            normalized,
            {name.casefold(): value or "" for name, value in attrs},
            parent=self._stack[-1],
        )
        self._stack[-1].content.append(node)
        if normalized not in _VOID_ELEMENTS:
            self._stack.append(node)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()
        node = _Node(
            normalized,
            {name.casefold(): value or "" for name, value in attrs},
            parent=self._stack[-1],
        )
        self._stack[-1].content.append(node)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == normalized:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].content.append(data)


def _walk(node: _Node) -> Iterator[_Node]:
    for child in node.children:
        yield child
        yield from _walk(child)


def _descendants(node: _Node) -> Iterator[_Node]:
    yield from _walk(node)


def _classes(node: _Node) -> tuple[str, ...]:
    return tuple(value for value in node.attrs.get("class", "").split() if value)


def _has_zero_scale_transform(source: str) -> bool:
    for match in _SCALE_FUNCTION_RE.finditer(source):
        tokens = [
            token for token in re.split(r"[\s,]+", match.group("arguments").strip())
            if token
        ]
        if not tokens or any(_CSS_NUMBER_RE.fullmatch(token) is None for token in tokens):
            continue
        if any(float(token) == 0 for token in tokens[:2]):
            return True
    return False


def _is_hidden(node: _Node) -> bool:
    if "hidden" in node.attrs:
        return True
    if _HIDDEN_STYLE_RE.search(node.attrs.get("style", "")):
        return True
    if node.attrs.get("display", "").casefold() == "none":
        return True
    if node.attrs.get("visibility", "").casefold() in {"hidden", "collapse"}:
        return True
    if re.fullmatch(r"0(?:\.0+)?", node.attrs.get("opacity", "").strip()):
        return True
    if _has_zero_scale_transform(node.attrs.get("transform", "")):
        return True
    if any(
        _has_zero_scale_transform(match.group("value"))
        for match in _TRANSFORM_DECLARATION_RE.finditer(
            node.attrs.get("style", "")
        )
    ):
        return True
    return bool(_SCREEN_READER_ONLY_CLASSES.intersection(_classes(node)))


def _is_effectively_hidden(node: _Node) -> bool:
    current: _Node | None = node
    while current is not None:
        if current.tag in _NON_RENDERED_ELEMENTS or _is_hidden(current):
            return True
        current = current.parent
    return False


def _node_text(node: _Node, *, rendered_only: bool = True) -> str:
    if rendered_only and (node.tag in _NON_RENDERED_ELEMENTS or _is_hidden(node)):
        return ""
    parts: list[str] = []
    for item in node.content:
        if isinstance(item, str):
            parts.append(item)
        else:
            parts.append(_node_text(item, rendered_only=rendered_only))
    return " ".join(" ".join(parts).split())


def _attribute_label(node: _Node, id_map: dict[str, _Node]) -> str:
    aria_label = " ".join(node.attrs.get("aria-label", "").split())
    if aria_label:
        return aria_label
    labelledby = node.attrs.get("aria-labelledby", "").split()
    if labelledby:
        labels = [
            _node_text(id_map[target])
            for target in labelledby
            if target in id_map
        ]
        resolved = " ".join(" ".join(labels).split())
        if resolved:
            return resolved
    return ""


def _first_descendant_text(node: _Node, tag: str) -> str:
    for descendant in _descendants(node):
        if descendant.tag == tag:
            value = _node_text(descendant, rendered_only=False)
            if value:
                return value
    return ""


def _enclosing_figure_caption(node: _Node) -> str:
    parent = node.parent
    while parent is not None:
        if parent.tag == "figure":
            return _first_descendant_text(parent, "figcaption")
        parent = parent.parent
    return ""


def _svg_accessible_name(node: _Node, id_map: dict[str, _Node]) -> str:
    if node.attrs.get("aria-hidden", "").casefold() == "true":
        return ""
    label = _attribute_label(node, id_map)
    if label:
        return label
    title = _first_descendant_text(node, "title")
    if title:
        return title
    return _enclosing_figure_caption(node)


def _svg_counts(node: _Node) -> tuple[int, int, int]:
    geometry = 0
    text = 0
    path_commands = 0
    for descendant in _descendants(node):
        if descendant.tag in _SVG_GEOMETRY:
            geometry += 1
        if descendant.tag == "text" and _node_text(descendant):
            text += 1
        if descendant.tag == "path":
            path_commands += len(re.findall(
                r"[MmLlHhVvCcSsQqTtAaZz]",
                descendant.attrs.get("d", ""),
            ))
    return geometry, text, path_commands


def _svg_number(value: str) -> float | None:
    stripped = value.strip()
    if _SVG_NUMBER_RE.fullmatch(stripped) is None:
        return None
    normalized = re.sub(r"(?:px|%)$", "", stripped, flags=re.IGNORECASE)
    try:
        result = float(normalized)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _svg_primitive_has_geometry(node: _Node) -> bool:
    """Conservatively decide whether a primitive paints non-zero geometry."""

    if node.tag == "rect":
        width = _svg_number(node.attrs.get("width", ""))
        height = _svg_number(node.attrs.get("height", ""))
        return width is not None and height is not None and width > 0 and height > 0
    if node.tag == "circle":
        radius = _svg_number(node.attrs.get("r", ""))
        return radius is not None and radius > 0
    if node.tag == "ellipse":
        rx = _svg_number(node.attrs.get("rx", ""))
        ry = _svg_number(node.attrs.get("ry", ""))
        return rx is not None and ry is not None and rx > 0 and ry > 0
    if node.tag == "line":
        coordinates = [
            _svg_number(node.attrs.get(name, "0"))
            for name in ("x1", "y1", "x2", "y2")
        ]
        return bool(
            all(value is not None for value in coordinates)
            and coordinates[:2] != coordinates[2:]
        )
    if node.tag in {"polyline", "polygon"}:
        points = node.attrs.get("points", "").strip()
        if not points or re.search(r"[^\d+.,eE\s-]", points):
            return False
        try:
            values = [float(value) for value in re.findall(
                r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?",
                points,
                re.IGNORECASE,
            )]
        except ValueError:
            return False
        pairs = list(zip(values[0::2], values[1::2])) if len(values) % 2 == 0 else []
        required = 3 if node.tag == "polygon" else 2
        return len(pairs) >= required and len(set(pairs)) >= required
    if node.tag == "path":
        path = node.attrs.get("d", "")
        return bool(
            re.search(r"[Mm]", path)
            and re.search(r"[LlHhVvCcSsQqTtAa]", path)
            and len(re.findall(
                r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?",
                path,
                re.IGNORECASE,
            )) >= 2
        )
    return False


def _use_resolves_to_geometry(
    node: _Node,
    local_ids: dict[str, _Node],
    resolving: frozenset[str] = frozenset(),
) -> bool:
    reference = node.attrs.get("href") or node.attrs.get("xlink:href", "")
    if re.fullmatch(r"#[A-Za-z_][\w:.-]*", reference) is None:
        return False
    target_id = reference[1:]
    target = local_ids.get(target_id)
    if target is None or target_id in resolving:
        return False
    next_resolving = resolving | {target_id}

    def subtree_has_geometry(current: _Node, *, root: bool = False) -> bool:
        if _is_hidden(current):
            return False
        if current.tag == "use":
            return _use_resolves_to_geometry(current, local_ids, next_resolving)
        if current.tag in _SVG_GEOMETRY:
            return _svg_primitive_has_geometry(current)
        for child in current.children:
            if child.tag in _SVG_NON_RENDERED_CONTAINERS and not root:
                continue
            if subtree_has_geometry(child):
                return True
        return False

    return subtree_has_geometry(target, root=True)


def _visual_v2_rendered_svg_counts(node: _Node) -> tuple[int, int]:
    """Count visible primitives/labels while excluding SVG definition subtrees."""

    local_ids = {
        descendant.attrs["id"]: descendant
        for descendant in _descendants(node)
        if descendant.attrs.get("id")
    }
    geometry = 0
    text = 0
    for descendant in _descendants(node):
        ancestor = descendant.parent
        inside_definition = False
        while ancestor is not None and ancestor is not node:
            if ancestor.tag in _SVG_NON_RENDERED_CONTAINERS:
                inside_definition = True
                break
            ancestor = ancestor.parent
        if inside_definition:
            continue
        if _is_effectively_hidden(descendant):
            continue
        if descendant.tag == "use":
            geometry += int(_use_resolves_to_geometry(descendant, local_ids))
        elif descendant.tag in _SVG_GEOMETRY:
            geometry += int(_svg_primitive_has_geometry(descendant))
        text += int(descendant.tag == "text" and bool(_node_text(descendant)))
    return geometry, text


def _meaningful_svg(
    node: _Node,
    id_map: dict[str, _Node],
) -> tuple[bool, bool, int, int, int]:
    if _is_effectively_hidden(node):
        geometry, text, path_commands = _svg_counts(node)
        return False, False, geometry, text, path_commands
    name = _svg_accessible_name(node, id_map)
    accessible = len(name) >= 4
    geometry, text, path_commands = _svg_counts(node)
    if not accessible:
        return False, False, geometry, text, path_commands

    # Text-labelled structures catch charts and process maps.  The shape-rich
    # branch permits illustrations without SVG <text>, but still excludes a
    # logo/icon made from one or two paths.
    text_labelled_structure = (
        geometry >= 2
        and text >= 2
        and geometry + (2 * text) >= 6
        and (geometry >= 3 or path_commands >= 4)
    )
    shape_rich_illustration = geometry >= 8 and len(name) >= 12
    meaningful = text_labelled_structure or shape_rich_illustration
    return meaningful, True, geometry, text, path_commands


def _visual_v2_complete_svg(
    node: _Node,
    *,
    meaningful: bool,
    id_counts: Counter[str],
) -> tuple[bool, int, int]:
    """Return whether an SVG satisfies the complete visual-v2 a11y contract."""

    if not meaningful or node.attrs.get("role", "").casefold() != "img":
        rendered_geometry, rendered_text = _visual_v2_rendered_svg_counts(node)
        return False, rendered_geometry, rendered_text
    rendered_geometry, rendered_text = _visual_v2_rendered_svg_counts(node)
    if rendered_geometry < 3 or rendered_text < 2:
        return False, rendered_geometry, rendered_text
    if len(" ".join(node.attrs.get("aria-label", "").split())) < 4:
        return False, rendered_geometry, rendered_text
    viewbox = node.attrs.get("viewbox", "")
    if _SVG_VIEWBOX_RE.fullmatch(viewbox) is None:
        return False, rendered_geometry, rendered_text
    viewbox_values = [float(value) for value in re.split(r"[\s,]+", viewbox.strip())]
    if (
        len(viewbox_values) != 4
        or not all(math.isfinite(value) for value in viewbox_values)
        or viewbox_values[2] <= 0
        or viewbox_values[3] <= 0
    ):
        return False, rendered_geometry, rendered_text
    labelledby = node.attrs.get("aria-labelledby", "").split()
    if len(labelledby) < 2 or len(set(labelledby)) != len(labelledby):
        return False, rendered_geometry, rendered_text
    descendants = list(_descendants(node))
    title_nodes = [
        item for item in descendants
        if item.tag == "title" and item.attrs.get("id") and _node_text(item, rendered_only=False)
    ]
    desc_nodes = [
        item for item in descendants
        if item.tag == "desc" and item.attrs.get("id") and _node_text(item, rendered_only=False)
    ]
    if len(title_nodes) != 1 or len(desc_nodes) != 1:
        return False, rendered_geometry, rendered_text
    referenced_ids = {title_nodes[0].attrs["id"], desc_nodes[0].attrs["id"]}
    complete = (
        referenced_ids.issubset(labelledby)
        and all(id_counts[value] == 1 for value in referenced_ids)
    )
    return complete, rendered_geometry, rendered_text


def _visual_v2_svg_fingerprint(node: _Node) -> str:
    """Fingerprint rendered diagram structure while ignoring a11y/id renames."""

    parts: list[str] = []
    for descendant in _descendants(node):
        ancestor = descendant.parent
        inside_definition = False
        while ancestor is not None and ancestor is not node:
            if ancestor.tag in _SVG_NON_RENDERED_CONTAINERS:
                inside_definition = True
                break
            ancestor = ancestor.parent
        if inside_definition:
            continue
        if descendant.tag in _SVG_GEOMETRY:
            attrs = sorted(
                (name, value)
                for name, value in descendant.attrs.items()
                if name not in {
                    "id", "href", "xlink:href", "aria-label", "aria-labelledby",
                }
            )
            parts.append(f"shape:{descendant.tag}:{attrs!r}")
        elif descendant.tag == "text" and _node_text(descendant):
            parts.append(f"text:{_node_text(descendant)}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _css_rules(css: str) -> list[tuple[str, str]]:
    cleaned = _CSS_COMMENT_RE.sub("", css)
    return [
        (selector.strip(), declarations)
        for selector, declarations in _CSS_RULE_RE.findall(cleaned)
        if selector.strip()
    ]


def _selector_matches_node(selector: str, node: _Node) -> bool:
    node_id = node.attrs.get("id", "")
    if node_id and re.search(
        rf"(?<![\w-])#{re.escape(node_id)}(?![\w-])",
        selector,
    ):
        return True
    for class_name in _classes(node):
        if re.search(
            rf"(?<![\w-])\.{re.escape(class_name)}(?![\w-])",
            selector,
        ):
            return True
    return bool(re.search(
        rf"(?:^|[\s>+~,]){re.escape(node.tag)}(?:$|[\s>+~,.#:\[])",
        selector,
        re.IGNORECASE,
    ))


def _node_has_layout(node: _Node, rules: list[tuple[str, str]]) -> bool:
    inline = node.attrs.get("style", "")
    if _DISPLAY_GRID_RE.search(inline) or _DISPLAY_FLEX_RE.search(inline):
        return True
    return any(
        (_DISPLAY_GRID_RE.search(declarations) or _DISPLAY_FLEX_RE.search(declarations))
        and _selector_matches_node(selector, node)
        for selector, declarations in rules
    )


def _subtree_has_layout(node: _Node, rules: list[tuple[str, str]]) -> bool:
    return _node_has_layout(node, rules) or any(
        _node_has_layout(descendant, rules)
        for descendant in _descendants(node)
    )


def _visual_keyword_text(node: _Node) -> str:
    values = [node.attrs.get("id", ""), *_classes(node)]
    for name, value in node.attrs.items():
        if name.startswith("data-") and value:
            values.extend((name[5:], value))
    return " ".join(values)


def _is_semantic_visual_candidate(node: _Node) -> bool:
    if (
        node.tag in {"svg", "table", "#document"}
        or _is_effectively_hidden(node)
    ):
        return False
    if node.tag == "figure":
        return True
    if node.attrs.get("role", "").casefold() in {
        "figure", "graphics-document", "img",
    }:
        return True
    return bool(_VISUAL_KEYWORD_RE.search(_visual_keyword_text(node)))


def _semantic_accessible_name(node: _Node, id_map: dict[str, _Node]) -> str:
    label = _attribute_label(node, id_map)
    if label:
        return label
    if node.tag == "figure":
        return _first_descendant_text(node, "figcaption")
    return ""


def _visual_node_count(node: _Node) -> int:
    count = 0
    for descendant in _descendants(node):
        classes = " ".join(_classes(descendant))
        if (
            descendant.tag in _VISUAL_NODE_TAGS
            or _VISUAL_NODE_CLASS_RE.search(classes)
        ):
            count += 1
    return count


def _meaningful_semantic_visual(
    node: _Node,
    id_map: dict[str, _Node],
    rules: list[tuple[str, str]],
) -> tuple[bool, int, bool]:
    name = _semantic_accessible_name(node, id_map)
    visual_nodes = _visual_node_count(node)
    has_layout = _subtree_has_layout(node, rules)
    visible_text = _node_text(node)
    substantial = (
        len(name) >= 4
        and len(visible_text) >= 30
        and visual_nodes >= 3
        and has_layout
    )
    return substantial, visual_nodes, has_layout


def _visible_placeholder_matches(visible_text: str) -> list[str]:
    matches: list[str] = []
    for pattern in _VISIBLE_PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(visible_text):
            value = " ".join(match.group(0).split())
            matches.append(value)
    return matches


def analyze_visual_cc_quality(source: str) -> VisualCCQualityResult:
    """Analyze one final CC HTML document and return errors plus metrics.

    The function is intentionally side-effect free and uses only the standard
    library so it can be called from generation workers and repository-wide
    validation without additional setup.
    """

    if not isinstance(source, str):
        raise TypeError("source must be a string")

    parser = _DocumentParser()
    parser.feed(source)
    parser.close()
    nodes = list(_walk(parser.root))
    id_map = {
        node.attrs["id"]: node
        for node in nodes
        if node.attrs.get("id")
    }
    id_counts = Counter(
        node.attrs["id"] for node in nodes if node.attrs.get("id")
    )

    style_sources = [
        _node_text(node, rendered_only=False)
        for node in nodes
        if node.tag == "style"
    ]
    inline_styles = [node.attrs["style"] for node in nodes if node.attrs.get("style")]
    css = "\n".join([*style_sources, *inline_styles])
    rules = _css_rules("\n".join(style_sources))

    placeholder_components = [
        node
        for node in nodes
        if _PLACEHOLDER_COMPONENT_RE.fullmatch(
            node.attrs.get("data-component", "").strip()
        )
    ]
    visible_text = _node_text(parser.root)
    visible_placeholder_phrases = _visible_placeholder_matches(visible_text)

    svg_nodes = [node for node in nodes if node.tag == "svg"]
    accessible_svgs = 0
    meaningful_svgs = 0
    visual_v2_complete_svgs = 0
    visual_v2_complete_svg_fingerprints: set[str] = set()
    visual_v2_rendered_svg_geometry = 0
    visual_v2_rendered_svg_text = 0
    svg_geometry = 0
    svg_text = 0
    svg_path_commands = 0
    for svg in svg_nodes:
        meaningful, accessible, geometry, text, path_commands = _meaningful_svg(
            svg,
            id_map,
        )
        accessible_svgs += int(accessible)
        meaningful_svgs += int(meaningful)
        complete, rendered_geometry, rendered_text = _visual_v2_complete_svg(
            svg,
            meaningful=meaningful,
            id_counts=id_counts,
        )
        visual_v2_complete_svgs += int(complete)
        if complete:
            visual_v2_complete_svg_fingerprints.add(
                _visual_v2_svg_fingerprint(svg)
            )
        visual_v2_rendered_svg_geometry += rendered_geometry
        visual_v2_rendered_svg_text += rendered_text
        svg_geometry += geometry
        svg_text += text
        svg_path_commands += path_commands

    candidates = [node for node in nodes if _is_semantic_visual_candidate(node)]
    meaningful_semantic = 0
    semantic_visual_nodes = 0
    layout_candidates = 0
    meaningful_candidate_ids: set[int] = set()
    for candidate in candidates:
        meaningful, visual_nodes, has_layout = _meaningful_semantic_visual(
            candidate,
            id_map,
            rules,
        )
        semantic_visual_nodes += visual_nodes
        layout_candidates += int(has_layout)
        if meaningful:
            meaningful_semantic += 1
            meaningful_candidate_ids.add(id(candidate))

    figures = [
        node
        for node in nodes
        if node.tag == "figure" and not _is_effectively_hidden(node)
    ]
    visual_figures = sum(
        1
        for figure in figures
        if id(figure) in meaningful_candidate_ids
        or any(
            descendant.tag in {"svg", "img", "picture", "canvas"}
            for descendant in _descendants(figure)
        )
    )

    h1_lengths = [
        len(_node_text(node))
        for node in nodes
        if (
            node.tag == "h1"
            and not _is_effectively_hidden(node)
            and _node_text(node)
        )
    ]
    long_h1_count = sum(length > MAX_DISPLAY_H1_CHARS for length in h1_lengths)
    visual_v2_long_h1_count = sum(
        length > VISUAL_V2_MAX_DISPLAY_H1_CHARS for length in h1_lengths
    )
    visual_v2_short_h1_count = sum(
        length < VISUAL_V2_MIN_DISPLAY_H1_CHARS for length in h1_lengths
    )

    lesson_style_nodes = [
        node
        for node in nodes
        if (
            node.tag == "style"
            and node.attrs.get("data-ailey-lesson-css", "").casefold() == "sanitized"
        )
    ]
    lesson_css = "\n".join(
        _node_text(node, rendered_only=False) for node in lesson_style_nodes
    )
    official_title_nodes = [
        node
        for node in nodes
        if "official-title" in _classes(node) and _node_text(node)
    ]

    tables = [
        node
        for node in nodes
        if node.tag == "table" and not _is_effectively_hidden(node)
    ]
    table_rows = sum(
        1
        for table in tables
        for descendant in _descendants(table)
        if descendant.tag == "tr" and not _is_effectively_hidden(descendant)
    )
    table_cells = sum(
        1
        for table in tables
        for descendant in _descendants(table)
        if (
            descendant.tag in {"td", "th"}
            and not _is_effectively_hidden(descendant)
        )
    )

    has_visualization = meaningful_svgs > 0 or meaningful_semantic > 0
    table_heavy_no_visual = not has_visualization and (
        len(tables) >= TABLE_HEAVY_MIN_TABLES
        or table_rows >= TABLE_HEAVY_MIN_ROWS
    )

    grid_display_count = len(_DISPLAY_GRID_RE.findall(css))
    flex_display_count = len(_DISPLAY_FLEX_RE.findall(css))
    metrics: dict[str, MetricValue] = {
        "html_char_count": len(source),
        "visible_text_char_count": len(visible_text),
        "placeholder_component_count": len(placeholder_components),
        "visible_placeholder_phrase_count": len(visible_placeholder_phrases),
        "inline_svg_count": len(svg_nodes),
        "accessible_svg_count": accessible_svgs,
        "meaningful_svg_count": meaningful_svgs,
        "visual_v2_complete_svg_count": visual_v2_complete_svgs,
        "visual_v2_distinct_complete_svg_count": len(
            visual_v2_complete_svg_fingerprints
        ),
        "visual_v2_rendered_svg_primitive_count": visual_v2_rendered_svg_geometry,
        "visual_v2_rendered_svg_text_count": visual_v2_rendered_svg_text,
        "svg_primitive_count": svg_geometry,
        "svg_text_count": svg_text,
        "svg_path_command_count": svg_path_commands,
        "figure_count": len(figures),
        "visual_figure_count": visual_figures,
        "semantic_visual_candidate_count": len(candidates),
        "semantic_html_visualization_count": meaningful_semantic,
        "semantic_visual_node_count": semantic_visual_nodes,
        "semantic_layout_candidate_count": layout_candidates,
        "style_block_count": len(style_sources),
        "lesson_style_block_count": len(lesson_style_nodes),
        "lesson_style_char_count": len(lesson_css),
        "lesson_style_media_query_count": len(
            re.findall(r"@media\b", lesson_css, re.IGNORECASE)
        ),
        "lesson_style_max_width_media_count": len(
            _MAX_WIDTH_MEDIA_RE.findall(lesson_css)
        ),
        "lesson_style_print_media_count": len(_PRINT_MEDIA_RE.findall(lesson_css)),
        "lesson_style_reduced_motion_media_count": len(
            _REDUCED_MOTION_MEDIA_RE.findall(lesson_css)
        ),
        "lesson_style_svg_min_width_rule_count": css_svg_min_width_rule_count(
            lesson_css
        ),
        "css_rule_count": len(rules),
        "css_grid_declaration_count": grid_display_count,
        "css_flex_declaration_count": flex_display_count,
        "css_layout_declaration_count": grid_display_count + flex_display_count,
        "css_grid_property_count": len(_GRID_PROPERTY_RE.findall(css)),
        "display_h1_count": len(h1_lengths),
        "max_display_h1_char_count": max(h1_lengths, default=0),
        "excessively_long_h1_count": long_h1_count,
        "visual_v2_excessively_long_h1_count": visual_v2_long_h1_count,
        "visual_v2_excessively_short_h1_count": visual_v2_short_h1_count,
        "official_title_count": len(official_title_nodes),
        "table_count": len(tables),
        "table_row_count": table_rows,
        "table_cell_count": table_cells,
        "table_heavy_no_visual": table_heavy_no_visual,
        "has_qualifying_visualization": has_visualization,
    }

    errors: list[str] = []
    if placeholder_components:
        errors.append(
            "CC contains "
            f"{len(placeholder_components)} unfinished image/visualization "
            "placeholder component(s)"
        )
    if visible_placeholder_phrases:
        distinct_phrases = list(dict.fromkeys(visible_placeholder_phrases))
        preview = ", ".join(repr(value) for value in distinct_phrases[:3])
        errors.append(f"CC contains visible placeholder phrase(s): {preview}")
    if not has_visualization:
        errors.append(
            "CC requires at least one meaningful accessible inline SVG or "
            "substantial semantic HTML visualization"
        )
    if long_h1_count:
        errors.append(
            "CC has "
            f"{long_h1_count} display H1 heading(s) longer than "
            f"{MAX_DISPLAY_H1_CHARS} characters (maximum "
            f"{max(h1_lengths)} characters)"
        )
    if table_heavy_no_visual:
        errors.append(
            "CC is table-heavy without a meaningful visualization "
            f"({len(tables)} tables, {table_rows} rows)"
        )

    return VisualCCQualityResult(errors=errors, metrics=metrics)


def visual_cc_quality_errors(source: str) -> list[str]:
    """Compatibility helper for validators that consume only error strings."""

    return analyze_visual_cc_quality(source).errors


def visual_cc_quality_metrics(source: str) -> dict[str, MetricValue]:
    """Compatibility helper for audit/reporting code that consumes metrics."""

    return analyze_visual_cc_quality(source).metrics


def visual_v2_contract_errors(
    source: str,
    *,
    required_svg_count: int = 1,
    expected_official_title: str | None = None,
    required_visible_values: tuple[str, ...] = (),
) -> list[str]:
    """Apply the stricter static visual-v2 publication contract.

    The general analyzer intentionally accepts a substantial semantic HTML
    diagram so it can audit older corpora without false failures.  New visual-v2
    pages are stricter: every lesson needs completed inline SVG, a focused H1,
    its own responsive CSS, and no table-first fallback.
    """

    if required_svg_count not in {1, 2}:
        raise ValueError("required_svg_count must be 1 or 2")
    result = analyze_visual_cc_quality(source)
    errors = list(result.errors)
    metrics = result.metrics
    complete_svgs = int(metrics["visual_v2_complete_svg_count"])
    distinct_complete_svgs = int(metrics["visual_v2_distinct_complete_svg_count"])
    if distinct_complete_svgs < required_svg_count:
        errors.append(
            "visual-v2 requires at least "
            f"{required_svg_count} distinct meaningful SVG(s) with role=img, aria-label, "
            "aria-labelledby, title, and desc "
            f"(found {complete_svgs}, distinct {distinct_complete_svgs})"
        )
    if int(metrics["visual_v2_excessively_long_h1_count"]):
        errors.append(
            "visual-v2 display H1 must be at most "
            f"{VISUAL_V2_MAX_DISPLAY_H1_CHARS} characters"
        )
    if int(metrics["visual_v2_excessively_short_h1_count"]):
        errors.append(
            "visual-v2 display H1 must be at least "
            f"{VISUAL_V2_MIN_DISPLAY_H1_CHARS} characters"
        )
    if int(metrics["visible_text_char_count"]) < VISUAL_V2_MIN_VISIBLE_TEXT_CHARS:
        errors.append(
            "visual-v2 requires at least "
            f"{VISUAL_V2_MIN_VISIBLE_TEXT_CHARS} visible text characters "
            f"(found {metrics['visible_text_char_count']})"
        )
    if int(metrics["official_title_count"]) != 1:
        errors.append("visual-v2 requires exactly one visible .official-title element")
    parser = _DocumentParser()
    parser.feed(source)
    parser.close()
    rendered_text = _node_text(parser.root)
    visible_headings = [
        node
        for node in _walk(parser.root)
        if (
            node.tag in {"h2", "h3", "h4", "h5", "h6"}
            and not _is_effectively_hidden(node)
            and _node_text(node)
        )
    ]

    def has_substantive_section(pattern: str) -> bool:
        matcher = re.compile(pattern)
        for heading in visible_headings:
            if matcher.search(_node_text(heading)) is None or heading.parent is None:
                continue
            container = heading.parent
            while (
                container.tag not in {"section", "article", "main", "body", "#document"}
                and container.parent is not None
            ):
                container = container.parent
            heading_level = int(heading.tag[1])

            def content_stream(current: _Node) -> Iterator[tuple[str, _Node | None, str]]:
                if current.tag in _NON_RENDERED_ELEMENTS or _is_hidden(current):
                    return
                if current.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                    yield "heading", current, _node_text(current)
                    return
                for item in current.content:
                    if isinstance(item, str):
                        normalized = " ".join(item.split())
                        if normalized:
                            yield "text", None, normalized
                    else:
                        yield from content_stream(item)

            following: list[str] = []
            found_heading = False
            for kind, stream_node, text in content_stream(container):
                if kind == "heading" and stream_node is heading:
                    found_heading = True
                    continue
                if not found_heading:
                    continue
                if (
                    kind == "heading"
                    and stream_node is not None
                    and int(stream_node.tag[1]) <= heading_level
                ):
                    break
                following.append(text)
            if len(" ".join(" ".join(following).split())) >= 20:
                return True
        return False

    required_sections = (
        (r"확인\s*문제", "확인 문제"),
        (r"(?:정답|해설)", "정답 또는 해설"),
        (r"요약", "요약"),
    )
    for pattern, label in required_sections:
        if not has_substantive_section(pattern):
            errors.append(
                "visual-v2 requires a visible heading and substantive content "
                f"for {label}"
            )
    official_titles = [
        _node_text(node)
        for node in _walk(parser.root)
        if "official-title" in _classes(node) and _node_text(node)
    ]
    if expected_official_title is not None and official_titles != [expected_official_title]:
        errors.append(
            "visual-v2 .official-title must exactly equal the curriculum title "
            f"{expected_official_title!r}"
        )
    missing_visible = [
        value for value in required_visible_values if value not in rendered_text
    ]
    if missing_visible:
        errors.append(
            "visual-v2 rendered body is missing exact identity/topic text: "
            f"{missing_visible}"
        )
    if int(metrics["lesson_style_block_count"]) != 1:
        errors.append("visual-v2 requires exactly one sanitized lesson CSS block")
    if int(metrics["lesson_style_char_count"]) < 600:
        errors.append("visual-v2 lesson CSS must contain at least 600 characters")
    if int(metrics["lesson_style_max_width_media_count"]) < 1:
        errors.append("visual-v2 lesson CSS must include a max-width responsive @media rule")
    if int(metrics["lesson_style_print_media_count"]) < 1:
        errors.append("visual-v2 lesson CSS must include an @media print rule")
    if int(metrics["lesson_style_reduced_motion_media_count"]) < 1:
        errors.append(
            "visual-v2 lesson CSS must include a prefers-reduced-motion: reduce rule"
        )
    if int(metrics["lesson_style_svg_min_width_rule_count"]):
        errors.append(
            "visual-v2 forbids CSS min-width on SVG because diagrams must scale "
            "within the mobile viewport"
        )
    if int(metrics["table_count"]) > VISUAL_V2_MAX_TABLES:
        errors.append(
            "visual-v2 permits at most "
            f"{VISUAL_V2_MAX_TABLES} tables (found {metrics['table_count']})"
        )
    return list(dict.fromkeys(errors))


def required_visual_v2_svg_count(lesson: Mapping[str, Any]) -> int:
    """Return the visual-v2 SVG floor for one curriculum lesson."""

    topics = lesson.get("topics")
    normalized_topics = topics if isinstance(topics, list) else []
    title = lesson.get("title") if isinstance(lesson.get("title"), str) else ""
    text = " ".join([title, *(str(topic) for topic in normalized_topics)])
    complex_keywords = (
        "절차", "계산", "공정", "흐름", "위험", "재해", "사고", "고장",
        "분포", "회귀", "분산", "관리도", "검정", "구조", "시스템",
    )
    return 2 if (
        len(normalized_topics) > 1
        or lesson.get("lesson_type") in {"calculation", "comparison", "analysis"}
        or any(keyword in text for keyword in complex_keywords)
    ) else 1


def visual_v2_style_diversity_errors(
    lesson_style_hashes: Mapping[str, str],
    *,
    expected_lesson_count: int,
) -> list[str]:
    """Reject a fully migrated course that collapsed back to one CSS shell."""

    if expected_lesson_count < 3 or len(lesson_style_hashes) != expected_lesson_count:
        return []
    counts = Counter(lesson_style_hashes.values())
    unique_count = len(counts)
    minimum_unique = (3 * expected_lesson_count + 3) // 4
    largest_duplicate_cluster = max(counts.values(), default=0)
    maximum_cluster = max(2, (3 * expected_lesson_count + 99) // 100)
    errors: list[str] = []
    if unique_count < minimum_unique:
        errors.append(
            "visual-v2 course requires lesson-scoped CSS diversity: at least "
            f"{minimum_unique}/{expected_lesson_count} distinct style hashes "
            f"(found {unique_count})"
        )
    if largest_duplicate_cluster > maximum_cluster:
        errors.append(
            "visual-v2 course repeats one lesson CSS shell too often: maximum "
            f"allowed cluster {maximum_cluster}, found {largest_duplicate_cluster}"
        )
    return errors


__all__ = [
    "MAX_DISPLAY_H1_CHARS",
    "VISUAL_V2_MIN_DISPLAY_H1_CHARS",
    "VISUAL_V2_MAX_DISPLAY_H1_CHARS",
    "VISUAL_V2_MIN_VISIBLE_TEXT_CHARS",
    "VISUAL_V2_MAX_TABLES",
    "TABLE_HEAVY_MIN_ROWS",
    "TABLE_HEAVY_MIN_TABLES",
    "VisualCCQualityResult",
    "analyze_visual_cc_quality",
    "visual_cc_quality_errors",
    "visual_cc_quality_metrics",
    "css_svg_min_width_rule_count",
    "required_visual_v2_svg_count",
    "visual_v2_style_diversity_errors",
    "visual_v2_contract_errors",
]
