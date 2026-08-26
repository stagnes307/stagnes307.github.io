#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import CURRICULA_DIR, load_json
from validation import Report, validate_catalog, validate_course


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the complete Study Factory data set.")
    parser.add_argument("course_ids", nargs="*")
    args = parser.parse_args()
    course_ids = args.course_ids
    if not course_ids:
        index_path = CURRICULA_DIR / "index.json"
        if index_path.exists():
            course_ids = [item["id"] for item in load_json(index_path).get("courses", [])]

    report = Report()
    report.extend(validate_catalog())
    for course_id in course_ids:
        report.extend(validate_course(course_id))
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    print(f"Validated catalog and {len(course_ids)} course(s): {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
