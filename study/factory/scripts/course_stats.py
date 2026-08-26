#!/usr/bin/env python3
import argparse
import json
from common import iter_lessons, load_curriculum

parser = argparse.ArgumentParser()
parser.add_argument("course_ids", nargs="+")
args = parser.parse_args()
for course_id in args.course_ids:
    data = load_curriculum(course_id)
    units = [unit for section in data["sections"] for unit in section["units"]]
    groups = [group for unit in units for group in unit["lessons"]]
    lessons = list(iter_lessons(data))
    print(json.dumps({
        "course_id": course_id,
        "sections": len(data["sections"]),
        "units": len(units),
        "lesson_groups": len(groups),
        "learning_lessons": len(lessons),
        "topics": sum(len(item["topics"]) for item in lessons),
        "supplemental": sum(bool(item.get("supplemental")) for item in lessons),
    }, ensure_ascii=False))
