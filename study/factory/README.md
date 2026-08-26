# Ailey Study Factory

이 디렉터리는 curriculum과 Ailey 원본을 검증 가능한 정적 Study 페이지로 게시한다. 저장소 스크립트는 ChatGPT를 조작하지 않는다. Ailey 브라우저 조작은 Codex Browser Agent가 담당한다.

## 데이터 계층

```text
Course → Section(2) → Unit(2-3) → Lesson Group(2-3-1) → Learning Lesson(2-3-1-1)
```

최하위 Learning Lesson만 FF/CC 생성, progress, URL, 이전/다음 탐색의 단위다. 토픽은 2~3개가 원칙이며 4개 이상은 validator가 거부한다.

## 기본 명령

저장소 루트에서 실행한다.

```powershell
python study/factory/scripts/validate_curriculum.py big-data-analysis-engineer-written
python study/factory/scripts/init_course.py big-data-analysis-engineer-written
python study/factory/scripts/select_lessons.py big-data-analysis-engineer-written 2-3-1
python study/factory/scripts/ailey_prompt.py big-data-analysis-engineer-written 2-3-1-1
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 ff-running
python study/factory/scripts/build_lesson.py big-data-analysis-engineer-written 2-3-1-1
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 published
python study/factory/scripts/validate_all.py
```

## Browser protocol

1. curriculum과 progress에서 대상 Learning Lesson을 선택한다. `published`는 명시적 재생성이 아니면 건너뛴다.
2. Lesson마다 새 Ailey 대화를 연다.
3. `ailey_prompt.py` 출력 그대로 전송한다. 임의 지시문을 붙이지 않는다.
4. streaming, send/stop 버튼, 메시지 DOM 안정화로 완료를 확인한다.
5. Copy 기능을 우선 사용해 응답을 `ff.md`로 저장한다.
6. 같은 대화에 정확히 `.cc`만 전송한다.
7. 완전한 HTML을 `cc.html`로 저장하고 바깥쪽 Markdown fence만 제거한다.
8. Lesson shell을 생성하고 `published` 전환을 요청한다. 게이트 실패 시 전환이 거부된다.

정확한 프롬프트 형식:

```text
.ff {course title}
{unit id}. {unit title}
{lesson-group id}. {lesson-group title}
{learning-lesson id}. {learning-lesson title}
- {topic 1}
- {topic 2}
- {topic 3}
```

## Resume와 retry

- `published`: 건너뜀
- FF만 유효: CC부터 재개
- FF와 CC 모두 유효: publishing부터 재개
- 파일이 유효하지 않음: FF부터 재개
- FF, CC, HTML 추출은 각 최대 2회 재시도
- 개별 실패는 `failed`와 `last_error`를 기록하고 다음 Lesson 진행
- Course 말미에 failed Lesson을 한 번 더 재시도
- 인증 만료, 전역 사용량 제한, Ailey 전체 장애는 대량 failed 처리하지 않고 즉시 일시정지

재생성 시 기존 published 상태를 명시적으로 실행 대상으로 포함하고 해당 단계의 파일과 생성 시각을 교체한다. `CC만 다시 생성`은 기존 FF를 보존하고 같은 Lesson의 새 대화에서 FF context를 다시 확보한 뒤 `.cc` 결과만 교체한다.

## 자연어 운영 예

- `빅데이터분석기사 필기 2-3 전체 제작해`
- `정보처리기사 필기 이어서 진행해`
- `ADsP 전체 진행상태 보여줘`
- `2-3-1 전체 제작해`
- `2-3-1-2 다시 만들어`
- `2-3-1-2 CC만 다시 만들어`

## Publication gates

- FF: `ff.md`가 있고 공백 제외 200자 이상
- CC: `cc.html`이 300바이트 이상이고 doctype 또는 `<html` 포함, Markdown fence 없음
- Meta: course/lesson/status 일치
- Lesson: index, FF/CC 탭, hash, iframe, navigation 존재
- Course: curriculum과 progress의 Lesson ID가 정확히 일치
- Coverage: 모든 공식 항목이 유효한 Learning Lesson에 매핑
- Global: catalog parse 및 기존 page 호환성

모든 로컬 확인은 `python -m http.server`로 수행하고 `file://`는 사용하지 않는다. 브라우저 프로필, cookie, session, token은 저장소에 저장하지 않는다.
