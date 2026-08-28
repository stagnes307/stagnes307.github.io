#!/usr/bin/env python3
"""Validate the checked-in prompt-profile registry."""

from __future__ import annotations

from prompt_profiles import prompt_profile_registry_errors


def main() -> int:
    errors = prompt_profile_registry_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Prompt profile registry is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
