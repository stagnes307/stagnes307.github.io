#!/usr/bin/env python3
import sys
from validation import validate_catalog

report = validate_catalog()
for message in report.warnings:
    print(f"WARNING: {message}")
for message in report.errors:
    print(f"ERROR: {message}")
sys.exit(1 if report.errors else 0)
