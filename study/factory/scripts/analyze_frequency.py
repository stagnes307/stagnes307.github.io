#!/usr/bin/env python3
"""Print evidence-qualified observed topic frequencies and importance scores."""

from __future__ import annotations

import argparse
import sys

from build_question_bank import analyze_topics
from question_bank_common import load_question_bank
from question_bank_validation import validate_question_bank_data


DEFAULT_COURSE = "big-data-analysis-engineer-written"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("course_id", nargs="?", default=DEFAULT_COURSE)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    report = validate_question_bank_data(args.course_id)
    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}")
        return 1
    topics, _, summary = analyze_topics(args.course_id, load_question_bank(args.course_id))
    print(
        f"Evidence: {summary['evidence_level']} "
        f"({summary['eligible_rounds']} frequency-eligible rounds)"
    )
    for item in topics[: max(args.limit, 0)]:
        score = item["importance_score"]
        rendered_score = f"{score:.1f}" if isinstance(score, (int, float)) else "withheld"
        print(
            f"{item['code']} {item['title']}: observed={item['observed_questions']}, "
            f"rounds={item['distinct_rounds']}, score={rendered_score}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
