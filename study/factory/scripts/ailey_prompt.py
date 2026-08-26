#!/usr/bin/env python3
import argparse
from common import find_lesson, load_curriculum

parser = argparse.ArgumentParser()
parser.add_argument("course_id")
parser.add_argument("lesson_id")
args = parser.parse_args()
curriculum = load_curriculum(args.course_id)
lesson = find_lesson(curriculum, args.lesson_id)
print(f".ff {curriculum['title']}")
print(f"{lesson['unit_id']}. {lesson['unit_title']}")
print(f"{lesson['lesson_group_id']}. {lesson['lesson_group_title']}")
print(f"{lesson['id']}. {lesson['title']}")
for topic in lesson["topics"]:
    print(f"- {topic}")
