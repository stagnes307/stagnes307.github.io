#!/usr/bin/env python3
"""Rebuild the question-bank reports and web dataset without lesson shells."""

from __future__ import annotations

import argparse
import sys

from build_question_bank import _write_outputs
from question_bank_common import load_question_bank
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
    outputs = _write_outputs(
        args.course_id,
        load_question_bank(args.course_id),
        integrate_lessons=False,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
