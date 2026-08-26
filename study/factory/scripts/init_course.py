#!/usr/bin/env python3
import argparse
from build_course import build_course
from common import load_or_create_progress, progress_path

parser = argparse.ArgumentParser()
parser.add_argument("course_id")
args = parser.parse_args()
load_or_create_progress(args.course_id)
build_course(args.course_id)
print(progress_path(args.course_id))
