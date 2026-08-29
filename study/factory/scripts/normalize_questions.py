#!/usr/bin/env python3
"""Audit normalized hashes while preserving every source variant verbatim."""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from question_bank_common import load_question_bank, question_content_hash
from question_bank_validation import validate_question_bank_data


DEFAULT_COURSE = "big-data-analysis-engineer-written"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("course_id", nargs="?", default=DEFAULT_COURSE)
    args = parser.parse_args()
    report = validate_question_bank_data(args.course_id)
    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1

    variants = load_question_bank(args.course_id)["variants"].get("variants", [])
    modes = Counter(item.get("content_mode") for item in variants)
    full = [item for item in variants if item.get("content_mode") == "full"]
    mismatches = [
        item["variant_id"]
        for item in full
        if item.get("content_hash")
        != question_content_hash(item.get("question_text"), item.get("choices", []))
    ]
    print(f"Variants audited: {len(variants)}")
    for mode, count in sorted(modes.items()):
        print(f"  {mode}: {count}")
    print(f"Normalized hash mismatches: {len(mismatches)}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
