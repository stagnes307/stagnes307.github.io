#!/usr/bin/env python3
"""Inspect the curated source registry; this command never crawls the web."""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from question_bank_common import load_question_bank
from question_bank_validation import validate_question_bank_data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "course_id",
        nargs="?",
        default="big-data-analysis-engineer-written",
    )
    args = parser.parse_args()
    report = validate_question_bank_data(args.course_id)
    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1
    sources = load_question_bank(args.course_id)["sources"].get("sources", [])
    counts = Counter(item["rights"]["status"] for item in sources)
    print(f"Registered sources: {len(sources)}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    print("Network collection is intentionally disabled; update the reviewed registry instead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
