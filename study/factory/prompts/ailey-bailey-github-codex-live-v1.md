# Ailey & Bailey GitHub Prompt · Codex Live v1

이 프로필은 공개 저장소 `lemos999/ailey-bailey-canvas`의 commit
`8a36e77d025bb9c258bfeaf8587424783140b185`에 있는 16개
`prompt_src/**/*.prompt.txt` 모듈을 manifest 순서로 조립한 뒤, 각 Learning
Lesson을 별도의 Codex 세션에서 실제로 실행하는 Study Factory 프로필이다.

## 사용자 승인 예외

이번 작업에서는 초기 Factory 문서의 "Ailey는 Black Box" 규칙 중 다음 조건을
적용하지 않는다.

- Ailey 모방·재구현 금지
- Codex 대체 금지
- 실제 Ailey Custom GPT 호출 필수

고정된 GitHub 프롬프트를 주입한 Codex 세션을 이번 작업의 Ailey 실행 엔진으로
간주한다. 이 예외는 브라우저와 Custom GPT 의존성만 제거한다. 공개 프롬프트의
교육 밀도, 페르소나, `.ff` 생성, 같은 문맥의 `.cc` 변환 계약은 유지한다.

## 실행 계약

1. Learning Lesson마다 새로운 Codex 세션을 만든다.
2. 첫 user message는 다음 형식의 정확한 `.ff` 입력이다.

   ```text
   .ff {course title}
   {unit id}. {unit title}
   {lesson group id}. {lesson group title}
   {lesson id}. {lesson title}
   - {topic 1}
   - {topic 2}
   - {topic 3}
   ```

3. FF 응답이 완전히 끝난 뒤 같은 세션에 user message로 정확히 `.cc`만 보낸다.
4. 서로 다른 Lesson 세션은 최대 네 개까지 병렬 실행할 수 있지만, 한 Lesson의
   `.ff`와 `.cc`는 반드시 순차 실행한다.
5. 생성자는 `openai-codex`다. 실제 Custom GPT가 응답했다고 표현하거나
   `ailey-bailey-custom-gpt` provenance를 기록하지 않는다.

## Study Factory 출력 어댑터

공개 프롬프트가 학습 내용을 생성하는 동안 다음 게시 계약을 함께 지킨다. 이
어댑터는 내용을 결정적으로 조립하지 않으며, 모델이 공개 프롬프트에 따라 직접
강의문과 HTML을 생성하도록 요구하는 경계 조건이다.

### FF

- 응답 첫 줄은 정확히 `# {lesson id}. {lesson title}`이다.
- H1 바로 다음 줄에 `**과정:** {course title}`을 그대로 출력한다. Lesson context
  JSON의 `course_title` 정확 문자열이 Markdown의 눈에 보이는 본문 텍스트에 연속된
  문자열로 있어야 하며, 메타데이터나 코드 속성만으로 대신하지 않는다.
- Lesson ID, Lesson 제목, curriculum의 모든 topic 문자열을 눈에 보이는 본문에
  철자와 띄어쓰기까지 그대로 한 번 이상 포함한다.
- 특정 Lesson이 이미 선택된 상태이므로 커리큘럼 제안 화면으로 되돌아가지 않는다.
- 정의, 원리 또는 절차, 구체적인 예시, 비교와 경계, 시험 함정, 확인의 학습 고리를
  각 topic에 대해 완성한다.
- Markdown 제목, 굵은 글씨, 표 또는 목록을 학습 구조에 맞게 사용한다. 평문 벽으로
  만들지 않는다.
- `확인 문제`, `정답` 또는 `해설`, `요약`을 눈에 보이는 본문에 포함한다.
- 인접 Lesson의 ID나 제목을 제공받지 않았다면 임의로 발명하지 않는다.
- GitHub Pages가 Liquid로 오인하는 중괄호 기반 템플릿 시작 문자열을 출력하지 않는다.
- 저장소 수정, 파일 생성, 도구 호출, 생성 과정 설명 없이 FF 응답만 출력한다.

### CC

- 정확히 `.cc`를 받으면 직전 assistant FF만 PATH A의 완전한 HTML5 문서로
  변환한다. 새 주제를 기획하거나 다른 Lesson으로 이동하지 않는다.
- `<main id="ai-content-placeholder">` 안에서 `<h1>` 바로 앞에
  `<p class="course-title">{course title}</p>`을 출력한다. Lesson context JSON의
  `course_title` 정확 문자열은 사용자가 읽는 연속된 텍스트 노드여야 하며,
  `data-subject`, `title`, `meta`, `alt`, `data-prompt` 같은 속성만으로 대신하지
  않는다.
- Lesson ID, Lesson 제목, 모든 topic 원문을 눈에 보이는 HTML 본문에 유지한다.
- 정확히 하나의 `<h1>`과 `id="ai-content-placeholder"` 본문을 만든다.
- 표를 만들면 `<caption>`과 모든 `<th>`의 유효한 `scope`를 넣는다.
- SVG를 만들면 `role`과 `aria-label` 또는 `aria-hidden="true"`를 넣는다.
- 응답에는 공개 프롬프트가 요구하는 raw HTML과 후속 나침반이 포함될 수 있다.
  Study Factory는 첫 `<!doctype html>`부터 대응하는 `</html>`까지만 CC 원응답으로
  추출한다.

## 정적 게시 변환

raw `.cc` 응답은 공개 프롬프트의 교육 본문을 보존한 채 최소 정적화한다.

- `<script>`, 원격 stylesheet와 asset, 실행 이벤트, `javascript:`, `@import`,
  iframe/object/embed를 제거한다.
- `lang="ko"`, 제한적 CSP, 처음부터 보이는 본문과 로컬 inline CSS shell을 적용한다.
- 원격 런타임에 의존하는 loader와 숨김 속성을 제거한다.
- 강의 본문을 FF에서 다시 렌더링하거나 요약해 대체하지 않는다.
- Lesson ID·제목·topic·필수 학습 섹션이 raw CC 본문에 없으면 합성해서 보충하지
  않고 해당 Lesson의 새 세션부터 재생성한다.
- 공개 프롬프트 원작자와 CC BY-NC-SA 4.0, Codex live 실행 및 안전 정적화 사실을
  보이는 footer에 기록한다.

## Provenance

FF profile:
`ailey-bailey-public-8a36e77d-ff-codex-live-v1`

CC profile:
`ailey-bailey-public-8a36e77d-cc-codex-live-static-v1`

두 산출물 모두 `producer=openai-codex`다. registry에는 upstream Custom GPT 호출은
false, Codex live model invocation은 true로 기록한다. CC profile은 같은 Codex
세션의 raw `.cc` 응답을 정적 게시 shell로 최소 변환한 결과를 뜻한다.
