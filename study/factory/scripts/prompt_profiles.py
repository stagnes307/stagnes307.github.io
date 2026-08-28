#!/usr/bin/env python3
"""Load and validate the Study Factory prompt-profile registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import ACTIVE_PRODUCERS, FACTORY_ROOT


PROFILE_REGISTRY_PATH = FACTORY_ROOT / "prompts" / "profiles.json"
SUPPORTED_ARTIFACT_KINDS = {"ff", "cc"}
PINNED_PUBLIC_PROFILES = {
    "ailey-bailey-public-8a36e77d-ff-literal-v1": "ff",
    "ailey-bailey-public-8a36e77d-cc-safe-v1": "cc",
}
PINNED_AILEY_REPOSITORY = (
    "https://github.com/lemos999/ailey-bailey-canvas"
)
PINNED_AILEY_COMMIT = "8a36e77d025bb9c258bfeaf8587424783140b185"
PINNED_AILEY_MANIFEST = (
    "vendor/ailey-bailey-canvas/8a36e77d/manifest.json"
)


def load_prompt_registry(path: Path = PROFILE_REGISTRY_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    if not isinstance(registry, dict):
        raise ValueError(f"{path}: root must be an object")
    return registry


def _relative_factory_file(
    value: object,
    field: str,
    profile_id: str,
) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, f"{profile_id}: {field} must be a non-empty relative path"
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None, f"{profile_id}: {field} must stay inside study/factory"
    resolved = (FACTORY_ROOT / candidate).resolve()
    try:
        resolved.relative_to(FACTORY_ROOT.resolve())
    except ValueError:
        return None, f"{profile_id}: {field} escapes study/factory"
    return resolved, None


def prompt_profile_registry_errors(
    registry: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic registry errors without mutating repository state."""
    if registry is None:
        try:
            registry = load_prompt_registry()
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return [f"cannot load prompt profile registry: {exc}"]

    errors: list[str] = []
    if registry.get("version") != 1:
        errors.append("registry version must be 1")
    profiles = registry.get("profiles")
    if not isinstance(profiles, list):
        return errors + ["profiles must be an array"]

    seen_ids: set[str] = set()
    for index, profile in enumerate(profiles):
        label = f"profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{label}: must be an object")
            continue
        profile_id = profile.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            errors.append(f"{label}: id must be a non-empty string")
            profile_id = label
        elif profile_id in seen_ids:
            errors.append(f"{profile_id}: duplicate profile id")
        else:
            seen_ids.add(profile_id)

        if profile.get("producer") not in ACTIVE_PRODUCERS:
            errors.append(
                f"{profile_id}: producer must be one of {sorted(ACTIVE_PRODUCERS)}"
            )
        artifact_kinds = profile.get("artifact_kinds")
        if (
            not isinstance(artifact_kinds, list)
            or not artifact_kinds
            or any(kind not in SUPPORTED_ARTIFACT_KINDS for kind in artifact_kinds)
            or len(set(artifact_kinds)) != len(artifact_kinds)
        ):
            errors.append(
                f"{profile_id}: artifact_kinds must contain unique ff/cc values"
            )

        for field in ("spec", "vendor_manifest"):
            if field not in profile:
                continue
            path, error = _relative_factory_file(
                profile.get(field),
                field,
                str(profile_id),
            )
            if error:
                errors.append(error)
            elif path is not None and not path.is_file():
                errors.append(f"{profile_id}: {field} does not exist: {path}")

        upstream = profile.get("upstream")
        if upstream is not None:
            if not isinstance(upstream, dict):
                errors.append(f"{profile_id}: upstream must be an object")
            else:
                commit = upstream.get("commit")
                if (
                    not isinstance(commit, str)
                    or len(commit) != 40
                    or any(character not in "0123456789abcdef" for character in commit)
                ):
                    errors.append(
                        f"{profile_id}: upstream.commit must be a full lowercase Git SHA"
                    )
                repository = upstream.get("repository")
                if not isinstance(repository, str) or not repository.startswith(
                    "https://github.com/"
                ):
                    errors.append(
                        f"{profile_id}: upstream.repository must be a GitHub HTTPS URL"
                    )

        license_record = profile.get("license")
        if license_record is not None:
            if not isinstance(license_record, dict):
                errors.append(f"{profile_id}: license must be an object")
            elif license_record.get("spdx") != "CC-BY-NC-SA-4.0":
                errors.append(
                    f"{profile_id}: public Ailey profile license must be "
                    "CC-BY-NC-SA-4.0"
                )

        expected_kind = PINNED_PUBLIC_PROFILES.get(str(profile_id))
        if expected_kind is not None:
            if profile.get("producer") != "openai-codex":
                errors.append(
                    f"{profile_id}: producer must be openai-codex"
                )
            if artifact_kinds != [expected_kind]:
                errors.append(
                    f"{profile_id}: artifact_kinds must be [{expected_kind!r}]"
                )
            if profile.get("vendor_manifest") != PINNED_AILEY_MANIFEST:
                errors.append(
                    f"{profile_id}: vendor_manifest must identify the pinned snapshot"
                )
            if not isinstance(upstream, dict) or (
                upstream.get("repository") != PINNED_AILEY_REPOSITORY
                or upstream.get("commit") != PINNED_AILEY_COMMIT
            ):
                errors.append(
                    f"{profile_id}: upstream must identify the pinned repository "
                    "and full commit"
                )

    required = {
        "codex-study-v1",
        "ailey-legacy-unknown",
        "ailey-bailey-public-8a36e77d-ff-literal-v1",
        "ailey-bailey-public-8a36e77d-cc-safe-v1",
    }
    missing = sorted(required - seen_ids)
    if missing:
        errors.append(f"registry is missing required profiles: {missing}")
    return errors


def get_prompt_profile(
    profile_id: str,
    *,
    artifact_kind: str | None = None,
    producer: str | None = None,
) -> dict[str, Any]:
    """Return a validated profile and optionally enforce its intended use."""
    registry = load_prompt_registry()
    errors = prompt_profile_registry_errors(registry)
    if errors:
        raise ValueError("invalid prompt profile registry: " + "; ".join(errors))
    profile = next(
        (
            candidate
            for candidate in registry["profiles"]
            if candidate["id"] == profile_id
        ),
        None,
    )
    if profile is None:
        raise KeyError(f"unknown prompt profile: {profile_id}")
    if artifact_kind is not None and artifact_kind not in profile["artifact_kinds"]:
        raise ValueError(
            f"{profile_id} does not support artifact kind {artifact_kind!r}"
        )
    if producer is not None and profile["producer"] != producer:
        raise ValueError(
            f"{profile_id} requires producer {profile['producer']!r}, "
            f"not {producer!r}"
        )
    return profile
