# Ailey & Bailey GitHub Prompt · Static Visual CC v2

이 프로필은 사용자가 승인한 Study Factory 전용 어댑터다. 공개 GitHub Ailey
프롬프트를 Codex 세션에서 실행하되, 브라우저 Custom GPT의 시각 교안 수준을
정적·안전한 HTML로 재현한다. 공개 프롬프트와 충돌할 때 이 어댑터가 우선한다.

## 실행 계약

1. Learning Lesson마다 새 Codex 세션을 만든다.
2. 첫 user message는 Factory가 제공하는 정확한 `.ff` 메시지다.
3. FF가 끝난 뒤 같은 세션에 정확히 `.cc`만 보낸다.
4. `.cc`는 직전 FF와 Factory runtime context만 시각 교안으로 변환한다.
5. 파일 수정, 도구 호출, 과정 설명 없이 해당 응답만 출력한다.

## FF 계약

- 첫 줄은 반드시 `# {Lesson ID}. {12~36자의 학습용 제목}` 형식으로 쓴다.
  Lesson ID 바로 뒤의 마침표와 공백을 생략하지 않는다. 예:
  `# 1-1-1-1. 공정 신호를 읽는 관리도 지도`
- H1 바로 아래에 과정명과 curriculum의 정확한 공식 Lesson 제목을 별도 줄로
  보인다. 공식 제목이 길더라도 H1 전체로 복사하지 않는다.
- 모든 topic 원문 문자열을 눈에 보이는 본문에 정확히 한 번 이상 포함한다.
- 보통 H2 6~10개로 구성하고 불필요한 계층과 반복을 피한다.
- 정의, 작동 원리 또는 절차, 실제 예시, 비교·경계, 시험 함정, 확인 문제,
  정답·해설, 회상 요약을 포함한다.
- 표는 비교가 실제로 쉬워질 때만 사용하고 같은 내용을 표와 문장으로 반복하지
  않는다. Markdown 제목, 굵은 글씨, 목록을 사용해 읽기 위계를 만든다.
- 이미지 지시문, placeholder, 생성 과정, source URL을 출력하지 않는다.

## `.cc` 최우선 재정의

정확히 `.cc`를 받으면 공개 프롬프트 PATH A의 runtime-dependent BASE SHELL과
placeholder 주입 지시를 사용하지 않는다. 대신 아래의 완전한 정적 시각 교안 한
개만 출력한다. 이 재정의는 사용자가 브라우저 Ailey와 동등한 실제 시각화를
요청했기 때문에 적용된다.

### 출력 형식과 안전성

- 응답은 앞뒤 설명·Markdown fence 없이 `<!doctype html>`로 시작하고
  `</html>`로 끝나는 단일 HTML5 문서다.
- `html lang="ko"`, UTF-8, viewport, 정확히 하나의 `<h1>`,
  `<main id="ai-content-placeholder">`를 포함한다.
- `<head>` 안에 `<style data-lesson-style="visual-v2">`를 정확히 하나만 두고
  모든 레슨 디자인 CSS를 그 안에 직접 작성한다. 다른 `<style>`과 요소별
  `style` 속성은 만들지 않는다. 레슨 CSS는 최소 600자 이상으로 실제 레이아웃,
  타이포그래피, 색상, SVG 표현을 완결한다.
- JavaScript, `<script>`, 외부 stylesheet/font/image, Tailwind CDN, `@import`,
  `url(...)`, iframe, canvas, 실행 이벤트, form control, fixed/floating control을
  사용하지 않는다.
- `<link>`, `<object>`, `<embed>`, `<template>`, `<noscript>`, `<video>`,
  `<audio>`, `<source>`, SVG SMIL의 `<animate>`, `<animateMotion>`,
  `<animateTransform>`, `<set>`, `<discard>`도 사용하지 않는다.
- 기본으로 접히거나 모달 안에 숨는 `<details>`, `<summary>`, `<dialog>`와
  `popover`, `popovertarget`, `popovertargetaction` 속성을 사용하지 않는다.
- CSS의 `display:none`, `visibility:hidden/collapse`, `content-visibility:hidden`,
  `opacity:0`, `transform:scale(0)`, `position:fixed/sticky`를 어느 요소에도
  사용하지 않는다. HTML/SVG의 `hidden` 속성과 SVG presentation 속성으로 같은
  숨김을 만들지도 않는다. 모든 필수 내용은 브라우저에 실제로 보여야 한다.
- `<img>`와 base64 이미지로 그림을 대신하지 않는다. 실제 설명 도식은 정적
  inline SVG와 의미 있는 HTML/CSS 레이아웃으로 만든다.
- `data-component="image-placeholder"`,
  `data-component="visualization-placeholder"`, `이미지 설계`,
  `구조 시각화 설계`, 이미지 생성 프롬프트를 절대 출력하지 않는다.

### 정보 위계

- Hero의 H1은 12~36자의 짧고 기억 가능한 학습용 제목이다. 긴 공식 능력문장을
  H1에 복사하지 않는다.
- Hero 안에 과정명과 Lesson ID를 작게 보이고, curriculum의 정확한 공식 Lesson
  제목만 `<p class="official-title">정확한 공식 제목</p>`에 온전히 보존한다.
  이 요소 안에는 `공식 Lesson 제목:` 같은 라벨이나 다른 문자를 붙이지 않는다.
- 모든 topic 원문을 눈에 보이는 본문에 정확히 유지하되, 한 화면을 가득 채우는
  제목이나 반복 문장으로 만들지 않는다.
- 첫 화면에는 학습의 핵심 관계를 보여 주는 Hero visual을 배치한다.
- 본문은 보통 7~12개의 명확한 구획으로 구성한다. 긴 FF를 그대로 복사하지 말고
  정의·원리·예시·경계·함정·확인·요약을 시각적 읽기 순서로 재편한다.
- 본문 끝부분에 각각 보이는 `<h2>`~`<h6>` 제목을 가진 `확인 문제`,
  `정답` 또는 `해설`, `요약` 구획을 만들고, 각 제목 뒤에 최소 한 문장 이상의
  실제 내용을 둔다. 세 문구는 eyebrow나 일반 문단이 아니라 제목 요소 자체의
  보이는 문자열에 각각 정확히 포함한다. 단어만 숨겨 넣거나 창의적인 제목으로
  바꾸거나 일반 문단의 일부로 대신하지 않는다.
- 보이는 본문은 보통 한글 3,500~6,500자 안에서 완결한다. 내용상 필요한 경우만
  넘기며 같은 설명을 반복하지 않는다.
- 표는 최대 두 개를 기본으로 하고, 관계·순서·분류·계산은 가능한 한 도식,
  카드, 축, 단계 흐름으로 표현한다.

### 실제 시각화

- 모든 Lesson에 주제를 직접 설명하는 의미 있는 inline SVG를 최소 한 개 만든다.
- topic이 둘 이상이거나 절차·계산·위험 구조가 복합적이면 서로 역할이 다른 실제
  시각화 두 개 이상을 만든다.
- 정보성 SVG는 `role="img"`, 내용을 직접 요약한 `aria-label`, 고유한
  `aria-labelledby`, 내부 `<title>`과 `<desc>`를 모두 가진다. 단순 장식 SVG는
  `aria-hidden="true"`로 분리한다. `aria-label`과 `aria-labelledby` 중 하나만
  쓰면 안 되며, 모든 정보성 `<svg>` 시작 태그에 둘 다 직접 명시한다.
- 정보성 SVG에는 `<defs>` 안의 정의를 제외하고 화면에 실제 렌더되는 의미 있는
  도형을 최소 세 개, 읽을 수 있는 `<text>` 레이블을 최소 두 개 사용한다. 색만으로
  구분하지 않고 레이블·형태·선 종류를 함께 쓴다.
- 도형은 양수 크기를 명시한다. 예를 들어 `rect`는 `width`와 `height`, 원은
  양수 반지름, 선은 서로 다른 양 끝점, `path`는 실제 선/곡선 명령을 가진다.
  `<use>`를 쓰면 같은 SVG 안에 존재하며 실제 도형을 가진 고유 ID만 참조한다.
  존재하지 않거나 순환하는 참조와 0 크기 도형으로 개수를 채우지 않는다.
- 실제 내용에 맞춰 다음 중 가장 적절한 시각 문법을 선택한다.
  - 순서·계획·공정: 단계 흐름도, swimlane, PDCA loop
  - 비교·분류·선택: 비교축, 2×2 matrix, decision map
  - 계층·구성·시스템: architecture map, layered stack, tree
  - 계산·통계·품질: 좌표축, 분포, control chart, formula anatomy
  - 안전·위험·고장: risk matrix, barrier layers, cause-consequence path
  - 시간·변화·법규: timeline, state transition, before/after map
- 단지 원 여러 개와 일반적인 화살표를 반복하지 않는다. SVG의 레이블과 구조는
  해당 Lesson의 개념·수치·조건을 직접 설명해야 한다.

### 레슨별 고유 디자인

- Factory runtime context의 `visual_design_brief`를 출발점으로 삼되 내용에 맞게
  조정한다.
- 동일한 teal 카드, 동일한 Hero, 동일한 그리드를 모든 Lesson에 반복하지 않는다.
- 주제에 따라 배경, 색상, 타이포그래피 비율, 카드 모양, 시각 은유를 바꾼다.
- 색상은 충분한 대비를 유지하고, 본문 글꼴은 시스템 한글 글꼴 fallback을 쓴다.
- CSS class 이름도 주제 역할을 드러내게 짓고, 모든 레슨에 같은 `card-1`,
  `card-2` 골격만 반복하지 않는다.

### 반응형·접근성

- 360px·390px 모바일과 1440px 데스크톱 모두에서 읽을 수 있어야 한다.
- 큰 그리드는 모바일에서 한 열로 재배치한다. SVG는 `viewBox`와
  `max-width:100%;height:auto`를 사용한다.
- SVG와 SVG를 감싼 도식 영역에 고정 너비나 `min-width`를 주지 않는다. 도식은
  모바일 뷰포트 안에서 전부 보이도록 제자리에서 축소되어야 하며, 가로 스크롤로
  일부를 숨기면 안 된다.
- 360px 화면에서 SVG의 보조 레이블도 실제 표시 높이 10px 이상, 핵심 레이블은
  12px 이상이 되도록 viewBox와 글자 크기를 함께 설계한다. 한 도식에 내용을
  우겨 넣어 글씨가 작아지면 두 개 이상의 세로형 도식이나 HTML 설명 카드로
  분리한다.
- 모바일 축소 뒤 글자 크기를 보장하려면 `viewBox` 너비를 가장 작은 보이는
  `<text>`의 `font-size`로 나눈 값이 28 이하가 되게 하고, 핵심 레이블은 25
  이하가 되게 한다. 예를 들어 너비 700인 viewBox에서 보조 글자는 25보다,
  핵심 글자는 28보다 작게 만들지 않는다.
- SVG의 `<text>`끼리 겹치거나 선·화살표·경로가 글자를 통과하지 않도록 레이블
  전용 여백을 둔다. 데스크톱에서만 맞고 모바일 축소 시 판독할 수 없는 도식은
  완성된 시각화로 간주하지 않는다.
- 여러 줄 레이블은 기준선 사이를 더 큰 글자 크기의 1.4배 이상 띄우고, 서로
  다른 `<text>`의 실제 경계 상자가 닿거나 겹치지 않게 한다. 좌우 레이블 사이는
  0.75em 이상, 도형 안의 글자는 모든 경계에서 0.6em 이상의 여백을 둔다. 긴
  문장은 `<tspan>`으로 충분히 줄바꿈하거나 별도 HTML 설명으로 옮긴다.
- 연결선·화살표·도형 경계는 텍스트 경계 상자 주위 0.5em 안전영역도 통과하지
  않게 하고, 노드 가장자리에서 끝내며 레이블이 없는 전용 통로로만 지나가게
  한다. 불투명 배경으로 충돌한 선을 가리는 방식은 허용하지 않는다.
- 그래프의 곡선·축·격자 위에 이름이나 설명을 직접 얹지 않는다. 곡선 이름과
  수식은 도표 밖의 별도 범례 또는 충분한 안쪽 여백과 불투명 배경을 가진
  callout으로 옮긴다. risk/decision matrix의 축 제목과 단계 레이블도 셀과
  겹치지 않는 독립 여백에 둔다.
- 제출 전 각 SVG를 360px와 390px에 맞춘 좌표로 검토한다. 글자 높이, 모든
  text-text 쌍, 모든 line/path/polyline-text 쌍 중 하나라도 기준을 어기면 도식
  높이를 늘리거나 여러 도식으로 나누며 글자 축소나 viewBox 잘라내기로 해결하지
  않는다.
- 가로 overflow wrapper는 표에만 사용할 수 있다. 표가 필요하면 별도 overflow
  wrapper를 쓰되 모든 셀에 `white-space:nowrap`을 강제하지 않는다.
- 표에는 `<caption>`과 모든 `<th>`의 유효한 `scope`를 넣는다.
- 본문 글자는 모바일에서 최소 16px, 터치나 마우스 hover 없이 모든 내용을 볼 수
  있어야 한다.
- `@media (max-width: ...)`, `@media (prefers-reduced-motion: reduce)`,
  `@media print`를 모두 제공하며 애니메이션 없이도 의미가 같다.

## 제출 전 자체 점검

응답을 끝내기 전에 내부적으로 다음을 모두 확인하고, 체크리스트 문장은 출력하지
않는다.

- placeholder 0개
- 실제 의미 있는 SVG 1개 이상, 복합 Lesson은 2개 이상
- 짧은 H1과 별도의 정확한 공식 제목
- 과정명, Lesson ID, 공식 제목, 모든 topic의 눈에 보이는 포함
- script·remote asset·runtime 의존성 0개
- 주제별 CSS와 모바일 breakpoint 존재
- 표로만 구성되지 않은 시각적 설명
- 확인 문제·정답 또는 해설·요약 포함

## Provenance

- FF producer/profile: `openai-codex` /
  `ailey-bailey-public-8a36e77d-ff-codex-visual-v2`
- CC producer/profile: `openai-codex` /
  `ailey-bailey-public-8a36e77d-cc-codex-live-visual-v2`
- 실제 upstream Custom GPT를 호출했다고 표현하지 않는다.
