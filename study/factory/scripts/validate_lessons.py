#!/usr/bin/env python3
import argparse
import sys
from validation import validate_lessons

parser = argparse.ArgumentParser()
parser.add_argument("course_id")
args = parser.parse_args()
report = validate_lessons(args.course_id)
for message in report.errors:
    print(f"ERROR: {message}")
sys.exit(1 if report.errors else 0)
