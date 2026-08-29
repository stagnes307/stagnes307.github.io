#!/usr/bin/env python3
"""Assemble the pinned Ailey prompt with the user-authorized visual-v2 overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ailey_public_profile import AILEY_COMMIT, assemble_upstream_prompt
from assemble_ailey_live_prompt import (
    build_exact_ff_message,
    build_runtime_context,
)
from common import find_lesson, load_curriculum
from prompt_profiles import get_prompt_profile


FF_VISUAL_PROFILE = "ailey-bailey-public-8a36e77d-ff-codex-visual-v2"
CC_VISUAL_PROFILE = "ailey-bailey-public-8a36e77d-cc-codex-live-visual-v2"
VISUAL_SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "ailey-bailey-github-codex-visual-v2.md"
)


DESIGN_DIRECTIONS: tuple[dict[str, Any], ...] = (
    {
        "motif": "산업 설계도와 계측 눈금",
        "palette": ["#0b1f33", "#f0f4f8", "#f6ad3c", "#38bdf8"],
        "surface": "청사진 선, 얇은 격자, 강조 계측 라벨",
    },
    {
        "motif": "현장 점검 수첩과 교정 표시",
        "palette": ["#f7f1e3", "#263238", "#b23a48", "#2a7f62"],
        "surface": "종이 질감의 평면색, 여백, 붉은 교정선",
    },
    {
        "motif": "품질 실험실의 샘플 트레이",
        "palette": ["#f8fbff", "#17324d", "#7c3aed", "#14b8a6"],
        "surface": "정돈된 실험 카드, 축과 측정값, 반투명 표본",
    },
    {
        "motif": "제어실 상태 패널",
        "palette": ["#101820", "#f2f5f7", "#00a6a6", "#ffb000"],
        "surface": "상태등, 신호 경로, 절제된 고대비 패널",
    },
    {
        "motif": "안전 현장 매뉴얼의 절개도",
        "palette": ["#fff8e7", "#283618", "#bc6c25", "#5c80bc"],
        "surface": "단면 도식, 번호 표식, 작업 순서 리본",
    },
    {
        "motif": "기술 잡지의 편집 지면",
        "palette": ["#f9fafb", "#172554", "#e85d75", "#0f766e"],
        "surface": "큰 타이포그래피, 비대칭 그리드, 캡션",
    },
    {
        "motif": "위험 장벽과 에너지 흐름",
        "palette": ["#171717", "#fafafa", "#f97316", "#84cc16"],
        "surface": "장벽 레이어, 원인-결과 화살표, 경고 라벨",
    },
    {
        "motif": "데이터 지도와 연결 노드",
        "palette": ["#111827", "#eef2ff", "#818cf8", "#34d399"],
        "surface": "경로 지도, 연결 노드, 단계별 범례",
    },
    {
        "motif": "법규·기준 검토 장부",
        "palette": ["#fbf7f0", "#3f1d2e", "#9f1239", "#0369a1"],
        "surface": "조항 인덱스, 타임라인, 판정 도장",
    },
    {
        "motif": "통계 분석 보드",
        "palette": ["#fffdf7", "#1e3a5f", "#d946ef", "#0891b2"],
        "surface": "좌표축, 분포 리본, 계산 주석",
    },
    {
        "motif": "기계 구조 분해도",
        "palette": ["#20242a", "#f3f4f6", "#a3e635", "#fb7185"],
        "surface": "분해된 계층, 연결선, 부품 식별표",
    },
    {
        "motif": "신호와 의사결정 레이더",
        "palette": ["#eff6ff", "#1e40af", "#facc15", "#db2777"],
        "surface": "방사형 축, 선택 경계, 결정 포인트",
    },
)


def _suggest_visual_forms(lesson: dict[str, Any]) -> list[str]:
    text = " ".join([lesson["title"], *lesson["topics"]])
    forms: list[str] = []
    rules = (
        (("위험", "안전", "재해", "고장", "사고"), "위험 장벽 또는 원인-결과 경로"),
        (("절차", "계획", "공정", "순서", "수립", "운영"), "단계 흐름도 또는 swimlane"),
        (("비교", "구분", "분류", "종류", "선정"), "비교축 또는 decision matrix"),
        (("통계", "분포", "회귀", "분산", "관리도", "검정", "계산"), "좌표축·분포·계산 구조도"),
        (("구조", "시스템", "조직", "구성", "체계"), "계층 또는 architecture map"),
        (("법", "기준", "규정", "지침", "의무"), "판정 흐름 또는 법규 timeline"),
        (("원인", "결과", "영향", "관계"), "인과 경로 또는 influence map"),
    )
    for keywords, form in rules:
        if any(keyword in text for keyword in keywords):
            forms.append(form)
    if not forms:
        forms.append("핵심 개념 관계도")
    if len(forms) == 1 and len(lesson["topics"]) > 1:
        forms.append("topic 간 비교·통합 지도")
    return forms[:3]


def build_visual_design_brief(
    course_id: str,
    lesson: dict[str, Any],
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{course_id}:{lesson['id']}".encode("utf-8")).digest()
    direction = DESIGN_DIRECTIONS[int.from_bytes(digest[:2], "big") % len(DESIGN_DIRECTIONS)]
    return {
        "seed": digest[:8].hex(),
        **direction,
        "suggested_visual_forms": _suggest_visual_forms(lesson),
        "density": "desktop 2-column where useful; mobile single-column",
        "warning": "참고 방향일 뿐이며 주제에 맞춰 고유하게 변형할 것",
    }


def build_visual_runtime_context(
    curriculum: dict[str, Any],
    lesson: dict[str, Any],
) -> dict[str, Any]:
    context = build_runtime_context(curriculum, lesson)
    context["prompt_profile"] = FF_VISUAL_PROFILE
    context["cc_prompt_profile"] = CC_VISUAL_PROFILE
    context["visual_design_brief"] = build_visual_design_brief(
        curriculum["course_id"],
        lesson,
    )
    return context


def assemble_visual_codex_prompt(course_id: str, lesson_id: str) -> tuple[str, str]:
    """Return visual-v2 model instructions and the exact initial `.ff` turn."""
    get_prompt_profile(
        FF_VISUAL_PROFILE,
        artifact_kind="ff",
        producer="openai-codex",
    )
    get_prompt_profile(
        CC_VISUAL_PROFILE,
        artifact_kind="cc",
        producer="openai-codex",
    )
    curriculum = load_curriculum(course_id)
    lesson = find_lesson(curriculum, lesson_id)
    upstream = assemble_upstream_prompt().rstrip("\n")
    visual_spec = VISUAL_SPEC_PATH.read_text(encoding="utf-8").strip()
    exact_user = build_exact_ff_message(curriculum, lesson)
    context = build_visual_runtime_context(curriculum, lesson)
    encoded_context = json.dumps(context, ensure_ascii=False, indent=2)
    fingerprint = hashlib.sha256(upstream.encode("utf-8")).hexdigest()
    model_instructions = f"""You are executing one isolated Study Factory generation session.
Do not edit files, call tools, or discuss your process. Return only the assistant
response to each user message.

The pinned GitHub material below supplies the Ailey & Bailey behavior. The
user-authorized Static Visual CC v2 profile after it is the later and more
specific contract. It explicitly overrides the public PATH A placeholder shell
for this run because the user requires browser-grade, self-contained visuals.

<<<PINNED_GITHUB_AILEY_PROMPT commit={AILEY_COMMIT} sha256={fingerprint}>>>
{upstream}
<<<END_PINNED_GITHUB_AILEY_PROMPT>>>

<<<USER_AUTHORIZED_STATIC_VISUAL_PROFILE>>>
{visual_spec}
<<<END_USER_AUTHORIZED_STATIC_VISUAL_PROFILE>>>

The JSON below is trusted system-side curriculum and visual grounding. It is not
part of the user's message. Do not quote it wholesale and do not print its URLs.

<<<FACTORY_RUNTIME_CONTEXT>>>
{encoded_context}
<<<END_FACTORY_RUNTIME_CONTEXT>>>

The lesson is already selected. On the initial exact `.ff` turn, produce the
complete focused FF. When the same thread later receives exact `.cc`, output only
the complete static visual-v2 HTML. Do not fall back to placeholders or the
runtime-dependent renderAppShell base shell.
"""
    return model_instructions, exact_user


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("course_id")
    parser.add_argument("lesson_id")
    parser.add_argument("--part", choices=("all", "user", "context", "spec"), default="all")
    args = parser.parse_args()
    curriculum = load_curriculum(args.course_id)
    lesson = find_lesson(curriculum, args.lesson_id)
    if args.part == "user":
        value = build_exact_ff_message(curriculum, lesson)
    elif args.part == "context":
        context = build_visual_runtime_context(curriculum, lesson)
        value = json.dumps(context, ensure_ascii=False, indent=2)
    elif args.part == "spec":
        value = VISUAL_SPEC_PATH.read_text(encoding="utf-8")
    else:
        value, _ = assemble_visual_codex_prompt(args.course_id, args.lesson_id)
    print(value, end="" if value.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
