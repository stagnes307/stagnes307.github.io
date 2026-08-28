# Study Factory

이 디렉터리는 공식 커리큘럼을 상세 FF 교안과 안전한 정적 CC 페이지로 만들어 검증 가능한 Study Course로 게시한다. 신규 Lesson의 기본 생성 경로는 계정이나 브라우저 세션에 의존하지 않는 **Codex direct**다.

- 제작 명세: [`prompts/codex-study-v1.md`](prompts/codex-study-v1.md)
- 제3자 고지: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- 일반 페이지 및 Course 게시 정책: [`../PUBLISHING.md`](../PUBLISHING.md)

기존 Ailey 생성물과 브라우저 절차는 이력 재현을 위해 보존하지만 신규 제작의 기본값이 아니다.

## 데이터 계층

```text
Course → Section(2) → Unit(2-3) → Lesson Group(2-3-1) → Learning Lesson(2-3-1-1)
```

최하위 Learning Lesson만 FF/CC 생성, progress, provenance, URL, 이전/다음 탐색의 단위다. 한 Lesson은 밀접한 토픽 2~3개가 원칙이며 validator는 4개 이상을 거부한다. 여러 토픽의 양이 많아 세부 설명이 빠질 우려가 있으면 `1-1-1-1`, `1-1-1-2`처럼 먼저 Lesson을 나눈다.

## 산출물

각 Lesson 디렉터리는 게시 시 다음 파일을 가진다.

```text
study/courses/<course-id>/lessons/<lesson-id>-<slug>/
├── ff.md
├── cc.html
├── cc-view.html
├── index.html
└── meta.json
```

- `ff.md`: 토픽별 정의·원리·예시·비교·시험 함정·확인 문제를 포함하는 상세 교안
- `cc.html`: FF 내용을 빠뜨리지 않고 재구성한 self-contained 정적 HTML
- `cc-view.html`: 원본 CC를 보존한 채 이전·다음 CC와 FF·목차 이동을 제공하는 전체 화면 iframe viewer
- `index.html`: FF 보기, 한 번에 `cc-view.html`로 진입하는 CC 버튼, 빈 sandbox의 fallback iframe, 앞뒤 Lesson 탐색을 제공하는 shell
- `meta.json`: Lesson 정보와 FF·CC 각각의 producer, prompt profile, 생성 시각, SHA-256

## 기본 명령

저장소 루트에서 실행한다.

```powershell
python study/factory/scripts/validate_curriculum.py big-data-analysis-engineer-written
python study/factory/scripts/init_course.py big-data-analysis-engineer-written
python study/factory/scripts/select_lessons.py big-data-analysis-engineer-written 2-3-1
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 ff-running
python study/factory/scripts/record_artifact.py big-data-analysis-engineer-written 2-3-1-1 ff --producer openai-codex --prompt-profile codex-study-v1
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 ff-complete
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 cc-running
python study/factory/scripts/render_codex_cc.py big-data-analysis-engineer-written 2-3-1-1
python study/factory/scripts/record_artifact.py big-data-analysis-engineer-written 2-3-1-1 cc --producer openai-codex --prompt-profile codex-study-v1
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 cc-complete
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 publishing
python study/factory/scripts/update_progress.py big-data-analysis-engineer-written 2-3-1-1 published
python study/factory/scripts/validate_all.py
```

`record_artifact.py`는 파일을 만든 뒤 실행한다. 기록된 파일과 현재 파일의 해시가 다르면 이후 상태 전환과 게시가 거부된다. 다른 provenance를 교체하는 `--force`는 명시적인 재생성 때만 사용한다.

## 기본 생성 프로토콜: Codex direct

1. curriculum, coverage, progress에서 대상 Learning Lesson을 선택한다. 명시적인 재생성이 아니면 `published`를 건너뛴다.
2. Lesson ID·제목·토픽·`official_basis`·`source_refs`와 공식 출처 기준일을 확인한다.
3. progress를 `ff-running`으로 바꾼다.
4. [`codex-study-v1`](prompts/codex-study-v1.md)에 따라 `ff.md`를 직접 작성한다. 모든 토픽에 정의, 원리, 예시, 비교/경계, 시험 함정, 확인 문제와 해설이 있어야 한다.
5. FF를 검토한 즉시 `producer=openai-codex`, `prompt_profile=codex-study-v1`로 provenance를 기록하고 `ff-complete`로 전환한다.
6. progress를 `cc-running`으로 바꾼 뒤, 검증된 FF 전체를 기반으로 `cc.html`을 작성한다. 표준 변환에는 `render_codex_cc.py <course-id> <lesson-id>`를 사용한다. 이 렌더러는 기존 CC 덮어쓰기를 기본 거부하고, FF·CC 품질 gate를 모두 통과한 경우에만 정적 HTML을 저장한다. 수동 제작 CC도 같은 규격을 따라야 하며 CC를 독립 요약으로 다시 생성하지 않는다.
7. CC의 내용 동등성, CSP, script/remote asset 부재, 표와 SVG 접근성, 모바일 표시를 확인한다.
8. CC provenance를 별도로 기록하고 `cc-complete → publishing → published` 순서로 전환한다.
9. Course와 전체 validator를 실행하고 로컬 HTTP에서 FF 탭과 CC iframe을 확인한다.

Codex direct는 공개 프롬프트 원문을 복제하지 않고 이 저장소의 독자 명세를 따른다. 신규 산출물을 `Ailey & Bailey`가 직접 생성한 것처럼 표시하지 않는다.

## Provenance

`meta.json` version 2는 FF와 CC를 각각 기록한다.

```json
{
  "version": 2,
  "artifacts": {
    "ff": {
      "producer": "openai-codex",
      "prompt_profile": "codex-study-v1",
      "generated_at": "ISO-8601 with offset",
      "sha256": "64 lowercase hex characters"
    },
    "cc": {
      "producer": "openai-codex",
      "prompt_profile": "codex-study-v1",
      "generated_at": "ISO-8601 with offset",
      "sha256": "64 lowercase hex characters"
    }
  }
}
```

- 새 Codex artifact: `producer=openai-codex`, `prompt_profile=codex-study-v1`
- 기존 Ailey artifact: `producer=ailey-bailey-custom-gpt`, `prompt_profile=ailey-legacy-unknown`
- `ailey-legacy-unknown`은 당시 비공개 프롬프트의 정확한 버전을 알 수 없다는 뜻이며 추정값이 아니다.
- FF만 재생성하면 FF 기록만 교체하고 CC는 다시 생성하기 전까지 게시 상태로 진행하지 않는다.
- CC만 재생성하면 기존 FF 기록을 보존하고 CC 기록만 교체한다.
- producer는 진행 상태나 문체로 추론하지 않는다. artifact를 실제로 만든 경로를 명시적으로 기록한다.

기존 version 1 metadata는 먼저 점검한 뒤 마이그레이션한다.

```powershell
python study/factory/scripts/migrate_meta_v2.py --expect-published 78
python study/factory/scripts/migrate_meta_v2.py --expect-published 78 --write
python study/factory/scripts/validate_all.py
```

## Resume와 retry

- `published`: 명시적 재생성이 아니면 건너뜀
- 유효한 FF와 일치하는 provenance만 있음: CC부터 재개
- 유효한 FF·CC와 일치하는 provenance가 모두 있음: publishing부터 재개
- 파일은 있으나 provenance가 없음: 생성자를 추정하지 말고 확인 또는 명시적 재생성
- provenance SHA-256과 파일이 다름: 변경 경위를 확인하고 해당 artifact를 다시 검토·기록
- 개별 생성 실패: `failed`와 구체적인 `last_error`를 기록하고 다른 Lesson 진행 가능
- 인증·사용량 제한은 Codex direct와 무관하다. legacy Ailey 경로에서 발생하면 해당 브라우저 작업만 일시정지한다.

여러 작업자가 병렬 생성할 때는 Lesson 디렉터리의 소유 범위를 겹치지 않게 나눈다. 같은 Course의 `progress.json`, Course index, catalog 갱신은 충돌하지 않도록 직렬화하고 각 batch 뒤 validator를 실행한다.

## CC 보안·접근성 필수 조건

- 완전한 HTML5 문서, `<html lang="ko">`, 올바른 Lesson title/H1
- `default-src 'none'`, `script-src 'none'`, `connect-src 'none'` 등을 포함한 제한적 CSP
- `<script>`, 인라인 이벤트 핸들러, `javascript:` URL, 외부 CDN과 원격 asset 금지
- 최초 렌더링부터 보이는 본문과 빈 sandbox iframe에서의 정상 표시
- 논리적인 heading 순서, 본문 바로가기, 보이는 keyboard focus
- 표마다 `<caption>`, 머리글마다 올바른 `scope="col"` 또는 `scope="row"`
- 정보성 SVG마다 `role="img"`, 구체적인 `aria-label`, `<title>`, `<desc>`
- 색에만 의존하지 않는 의미, 읽을 수 있는 대비, 320px 반응형, 인쇄 대응

정확한 생성·검토 계약은 [`codex-study-v1`](prompts/codex-study-v1.md)을 기준으로 한다.

## Publication gates

- FF: `ff.md`가 있고 공백 제외 200자 이상이며 정확한 Lesson 제목 또는 ID 포함
- CC: `cc.html`이 300바이트 이상인 완전한 HTML, Markdown fence/script/remote asset/숨겨진 content root 없음, `lang="ko"`
- Codex direct FF: 4,000자 이상, 모든 curriculum 토픽의 정확한 문자열, 균형 잡힌 Markdown fence, 확인 문제·정답/해설·요약 포함
- Codex direct CC: UTF-8 8KiB 이상, 모든 토픽, doctype/CSP/canvas ID/content root/H1, 표·SVG 접근성 포함
- Integrity: FF·CC가 현재 Lesson 제목 또는 ID를 포함하고 FF끼리 완전히 중복되지 않음
- Provenance: FF·CC 각각 producer/profile/generated_at/SHA-256이 있고 실제 파일과 해시 일치
- Meta: course/lesson/status와 artifact 기록 일치
- Lesson: index, FF/CC 탭, hash, 빈 sandbox iframe, navigation 존재
- Course: curriculum과 progress의 Lesson ID가 정확히 일치
- Coverage: 모든 공식 항목이 유효한 Learning Lesson에 매핑
- Global: catalog parse 및 기존 page 호환성

모든 로컬 확인은 `python -m http.server`로 수행하고 `file://`는 사용하지 않는다. 브라우저 프로필, cookie, session, token은 저장소에 저장하지 않는다.

## Legacy: Ailey 브라우저 프로토콜

이 절은 기존 생성 이력의 재현과 명시적인 legacy 요청을 위해 보존한다. 신규 Course의 기본 절차가 아니며, 계정 전환이나 사용량 제한 우회를 위해 사용하지 않는다.

1. curriculum과 progress에서 대상 Learning Lesson을 선택한다. `published`는 명시적 재생성이 아니면 건너뛴다.
2. Lesson마다 새 Ailey 대화를 연다.
3. 아래 형식의 `.ff` 프롬프트만 전송하고 임의 지시문을 붙이지 않는다.
4. streaming, send/stop 버튼, 메시지 DOM 안정화로 완료를 확인한다.
5. 응답을 `ff.md`로 저장한다.
6. 같은 대화에 정확히 `.cc`만 전송한다.
7. 완전한 HTML을 `cc.html`로 저장하고 바깥쪽 Markdown fence만 제거한다.
8. 각 artifact를 `producer=ailey-bailey-custom-gpt`, `prompt_profile=ailey-legacy-unknown`으로 명시해 기록한다.
9. Lesson shell을 생성하고 `published` 전환을 요청한다. 게이트 실패 시 전환이 거부된다.

Legacy 프롬프트 형식:

```text
.ff {course title}
{unit id}. {unit title}
{lesson-group id}. {lesson-group title}
{learning-lesson id}. {learning-lesson title}
- {topic 1}
- {topic 2}
- {topic 3}
```

Legacy resume 규칙:

- FF만 유효하고 provenance가 있음: 같은 Lesson의 새 대화에서 FF 맥락을 다시 확보한 뒤 CC만 교체 가능
- FF와 CC 모두 유효하고 provenance가 있음: publishing부터 재개
- 인증 만료, 전역 사용량 제한, Ailey 전체 장애: 대량 failed 처리하거나 반복 요청하지 않고 즉시 중단
- 정확한 Custom GPT 프롬프트 버전은 추정하지 않고 `ailey-legacy-unknown`으로 남김

## 자연어 운영 예

- `빅데이터분석기사 실기 남은 Lesson을 Codex direct로 제작해`
- `정보처리기사 필기 이어서 진행해`
- `ADsP 전체 진행상태와 provenance 오류를 보여줘`
- `2-3-1 전체 제작해`
- `2-3-1-2 다시 만들어`
- `2-3-1-2 CC만 다시 만들어`
