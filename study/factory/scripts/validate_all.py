#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from common import CURRICULA_DIR, coverage_path, curriculum_path, load_json
from validation import (
    Report,
    validate_catalog,
    validate_course,
    validate_prompt_infrastructure,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the complete Study Factory data set.")
    parser.add_argument("course_ids", nargs="*")
    args = parser.parse_args()
    course_ids = args.course_ids
    if not course_ids:
        index_path = CURRICULA_DIR / "index.json"
        if index_path.exists():
            index = load_json(index_path)
            entries = index.get("courses", [])
            course_ids = [item["id"] for item in entries]
            if len(course_ids) != len(set(course_ids)):
                print("ERROR: curricula index contains duplicate course ids")
                return 1
            for item in entries:
                expected_path = f"./{item['id']}.json"
                if item.get("path") != expected_path:
                    print(f"ERROR: {item['id']} index path must be {expected_path}")
                    return 1
                for required_path in (curriculum_path(item["id"]), coverage_path(item["id"]), CURRICULA_DIR / f"{item['id']}.md"):
                    if not required_path.exists():
                        print(f"ERROR: curricula index target missing: {required_path}")
                        return 1

    report = Report()
    report.extend(validate_prompt_infrastructure())
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
