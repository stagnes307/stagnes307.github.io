#!/usr/bin/env python3
"""Resolve a section/unit/group/lesson selector to ordered leaf lessons."""

import argparse
import json
from common import iter_lessons, load_curriculum, load_or_create_progress

parser = argparse.ArgumentParser()
parser.add_argument("course_id")
parser.add_argument("selector", help="all, 2, 2-3, 2-3-1, or 2-3-1-1")
parser.add_argument("--include-published", action="store_true")
args = parser.parse_args()
curriculum = load_curriculum(args.course_id)
progress = load_or_create_progress(args.course_id)
selector = args.selector.lower().replace("전체", "").strip()
selected = []
for lesson in iter_lessons(curriculum):
    matches = selector in {"", "all"} or lesson["id"] == selector or lesson["id"].startswith(selector + "-")
    if matches and (args.include_published or progress["lessons"][lesson["id"]]["status"] != "published"):
        selected.append(lesson)
print(json.dumps(selected, ensure_ascii=False, indent=2))
