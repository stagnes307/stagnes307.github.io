#!/usr/bin/env python3
"""Validate one canonical question bank without generating artifacts."""

from __future__ import annotations

import argparse
import sys

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
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    print(
        f"Validated question bank {args.course_id}: "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
