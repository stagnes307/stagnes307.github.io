"""Small dependency-free validator for the JSON Schema features used by Study."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"only local JSON Schema references are supported: {reference}")
    current: Any = root
    for component in reference[2:].split("/"):
        key = component.replace("~1", "/").replace("~0", "~")
        current = current[key]
    if not isinstance(current, dict):
        raise ValueError(f"JSON Schema reference is not an object: {reference}")
    return current


def _format_is_valid(value: str, format_name: str) -> bool:
    try:
        if format_name == "date":
            date.fromisoformat(value)
        elif format_name == "date-time":
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return False
        elif format_name == "uri":
            parsed = urlparse(value)
            return bool(parsed.scheme and (parsed.netloc or parsed.path))
    except (TypeError, ValueError):
        return False
    return True


def json_schema_errors(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Validate the subset of Draft 2020-12 used by the project schemas."""
    root = root_schema or schema
    if "$ref" in schema:
        return json_schema_errors(
            value,
            _resolve_ref(root, schema["$ref"]),
            root_schema=root,
            path=path,
        )

    errors: list[str] = []
    if "oneOf" in schema:
        alternatives = [
            json_schema_errors(value, item, root_schema=root, path=path)
            for item in schema["oneOf"]
        ]
        matches = [item for item in alternatives if not item]
        if len(matches) != 1:
            errors.append(
                f"{path}: must match exactly one schema alternative (matched {len(matches)})"
            )
            if not matches and alternatives:
                # Surface the closest branch so a root-level oneOf still gives
                # an actionable property/type error.
                errors.extend(min(alternatives, key=len))
        return errors

    for item in schema.get("allOf", []):
        errors.extend(
            json_schema_errors(value, item, root_schema=root, path=path)
        )
    if "if" in schema:
        condition_errors = json_schema_errors(
            value, schema["if"], root_schema=root, path=path
        )
        branch = "then" if not condition_errors else "else"
        if branch in schema:
            errors.extend(
                json_schema_errors(
                    value, schema[branch], root_schema=root, path=path
                )
            )

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in the allowed set")

    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )
        if not any(_matches_type(value, item) for item in allowed_types):
            errors.append(
                f"{path}: must have type {' or '.join(str(item) for item in allowed_types)}"
            )
            return errors

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is shorter than minLength")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            errors.append(f"{path}: string does not match {pattern}")
        format_name = schema.get("format")
        if format_name and not _format_is_valid(value, format_name):
            errors.append(f"{path}: invalid {format_name} value")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value is above maximum")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: array is shorter than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: array is longer than maxItems")
        if schema.get("uniqueItems"):
            serialized = [
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in value
            ]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    json_schema_errors(
                        item,
                        item_schema,
                        root_schema=root,
                        path=f"{path}[{index}]",
                    )
                )

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(
                    json_schema_errors(
                        item,
                        properties[key],
                        root_schema=root,
                        path=child_path,
                    )
                )
                continue
            matched_patterns = [
                item_schema
                for pattern, item_schema in patterns.items()
                if re.search(pattern, key)
            ]
            if matched_patterns:
                for item_schema in matched_patterns:
                    errors.extend(
                        json_schema_errors(
                            item,
                            item_schema,
                            root_schema=root,
                            path=child_path,
                        )
                    )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{child_path}: additional property is not allowed")
    return errors
