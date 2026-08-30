#!/usr/bin/env python3
"""Audit reviewed curriculum mappings without inventing classifications."""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from question_bank_common import flatten_appearances, load_question_bank
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

    groups = load_question_bank(args.course_id)["groups"].get("groups", [])
    appearances = list(flatten_appearances(groups))
    reviews = Counter(item.get("review_status") for item in appearances)
    mapped = sum(bool(item.get("primary_topic_code")) for item in appearances)
    print(f"Appearances: {len(appearances)}")
    print(f"Mapped to a primary curriculum topic: {mapped}")
    for status, count in sorted(reviews.items()):
        print(f"  {status}: {count}")
    print("This audit never assigns a topic automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
