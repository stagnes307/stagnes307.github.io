"""Shared filesystem and curriculum helpers for Study Factory scripts."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


STUDY_ROOT = Path(__file__).resolve().parents[2]
FACTORY_ROOT = STUDY_ROOT / "factory"
CURRICULA_DIR = STUDY_ROOT / "curricula"
COURSES_DIR = STUDY_ROOT / "courses"
CATALOG_PATH = STUDY_ROOT / "catalog.json"
STATUSES = {
    "pending",
    "ff-running",
    "ff-complete",
    "cc-running",
    "cc-complete",
    "publishing",
    "published",
    "failed",
}


def now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def today_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def curriculum_path(course_id: str) -> Path:
    return CURRICULA_DIR / f"{course_id}.json"


def coverage_path(course_id: str) -> Path:
    return CURRICULA_DIR / "coverage" / f"{course_id}.json"


def course_dir(course_id: str) -> Path:
    return COURSES_DIR / course_id


def progress_path(course_id: str) -> Path:
    return course_dir(course_id) / "progress.json"


def lesson_url(course_id: str, lesson: dict[str, Any]) -> str:
    return f"/study/courses/{course_id}/lessons/{lesson['id']}-{lesson['slug']}/"


def lesson_dir(course_id: str, lesson: dict[str, Any]) -> Path:
    return course_dir(course_id) / "lessons" / f"{lesson['id']}-{lesson['slug']}"


def iter_lessons(curriculum: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield flattened, contextualized four-part learning lessons in display order."""
    for section in curriculum.get("sections", []):
        for unit in section.get("units", []):
            for group in unit.get("lessons", []):
                for lesson in group.get("sublessons", []):
                    yield {
                        **lesson,
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "unit_id": unit["id"],
                        "unit_title": unit["title"],
                        "lesson_group_id": group["id"],
                        "lesson_group_title": group["title"],
                    }


def lesson_list(curriculum: dict[str, Any]) -> list[dict[str, Any]]:
    return list(iter_lessons(curriculum))


def find_lesson(curriculum: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    for lesson in iter_lessons(curriculum):
        if lesson["id"] == lesson_id:
            return lesson
    raise KeyError(f"unknown lesson id: {lesson_id}")


def new_progress(curriculum: dict[str, Any]) -> dict[str, Any]:
    course_id = curriculum["course_id"]
    return {
        "version": 1,
        "course_id": course_id,
        "updated": now_kst(),
        "lessons": {
            lesson["id"]: {
                "status": "pending",
                "ff": False,
                "cc": False,
                "url": None,
                "last_error": None,
            }
            for lesson in iter_lessons(curriculum)
        },
    }


def load_curriculum(course_id: str) -> dict[str, Any]:
    return load_json(curriculum_path(course_id))


def load_or_create_progress(course_id: str) -> dict[str, Any]:
    path = progress_path(course_id)
    curriculum = load_curriculum(course_id)
    if not path.exists():
        progress = new_progress(curriculum)
        write_json(path, progress)
        return progress

    progress = load_json(path)
    changed = False
    for lesson in iter_lessons(curriculum):
        if lesson["id"] not in progress.setdefault("lessons", {}):
            progress["lessons"][lesson["id"]] = {
                "status": "pending",
                "ff": False,
                "cc": False,
                "url": None,
                "last_error": None,
            }
            changed = True
    if changed:
        progress["updated"] = now_kst()
        write_json(path, progress)
    return progress


def render_template(name: str, values: dict[str, str]) -> str:
    text = (FACTORY_ROOT / "templates" / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    unresolved = [part.split("}}", 1)[0] for part in text.split("{{")[1:] if "}}" in part]
    if unresolved:
        raise ValueError(f"unresolved template values in {name}: {', '.join(unresolved)}")
    return text
