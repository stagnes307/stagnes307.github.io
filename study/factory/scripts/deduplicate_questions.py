#!/usr/bin/env python3
"""Report exact duplicate candidates without automatically merging evidence."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

from question_bank_common import fuzzy_duplicate_pairs, load_question_bank
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
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for variant in variants:
        if variant.get("content_hash"):
            by_hash[variant["content_hash"]].append(variant)
    candidates = [
        items
        for items in by_hash.values()
        if len({item.get("question_id") for item in items}) > 1
    ]
    print(f"Exact duplicate candidate clusters: {len(candidates)}")
    for items in candidates:
        ids = ", ".join(item["variant_id"] for item in items)
        print(f"  review: {ids}")
    fuzzy = fuzzy_duplicate_pairs(variants)
    print(f"Text-similarity candidates: {len(fuzzy)}")
    for left_id, right_id, ratio in fuzzy:
        print(f"  review: {left_id}, {right_id} ({ratio:.3f})")
    print("No records were merged; every merge requires human review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
