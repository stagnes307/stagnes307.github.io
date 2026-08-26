#!/usr/bin/env python3
import argparse
import sys
from validation import validate_curriculum, validate_coverage

parser = argparse.ArgumentParser()
parser.add_argument("course_id")
args = parser.parse_args()
report = validate_curriculum(args.course_id)
report.extend(validate_coverage(args.course_id))
for message in report.warnings:
    print(f"WARNING: {message}")
for message in report.errors:
    print(f"ERROR: {message}")
sys.exit(1 if report.errors else 0)
