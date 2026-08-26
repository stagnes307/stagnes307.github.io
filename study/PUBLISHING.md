# Study Publisher Guide

이 문서는 `stagnes307.github.io`의 개인 Study Library에 새 학습용 HTML을 게시할 때 사용하는 규칙이다.

## 목표

사용자가 완전한 HTML 문서를 붙여넣고 "스터디에 추가", "게시", "올려줘"와 같이 요청하면, 별도의 분류 지시가 없어도 적절한 위치와 메타데이터를 판단해 게시한다.

콘텐츠 생성기(Ailey 등)와 Publisher 역할은 분리한다. Publisher는 원본 HTML의 내용과 디자인을 불필요하게 다시 작성하지 않는다.

## 게시 절차

1. 사용자가 제공한 HTML의 `<title>`, `<h1>`, 본문, 키워드를 읽는다.
2. `study/catalog.json`의 기존 항목을 확인해 동일하거나 매우 유사한 주제가 있는지 검사한다.
3. 중복이 아니면 category와 subcategory를 결정한다.
4. 사람이 읽을 수 있는 영문 `kebab-case` slug를 만든다.
5. 신규 HTML은 원칙적으로 `study/pages/<category>/<subcategory>/<slug>.html`에 저장한다.
6. `study/catalog.json`의 `items` 배열에 메타데이터를 한 건 추가한다.
7. 기존 `study/index.html`은 직접 수정하지 않는다. Study 화면은 catalog를 읽어 자동 렌더링한다.
8. 변경사항을 검토 가능한 브랜치/PR에 반영한다. 사용자가 명시적으로 main 직접 반영을 요청하지 않는 한 기존 GitHub 작업 관례를 따른다.
9. 완료 후 최종 페이지 URL과 분류만 간단히 알려준다.

## 대분류 taxonomy

### `battery`
배터리 및 소재 관련 학습자료.

권장 subcategory 예시:
- `cathode/lfp`
- `cathode/ncm-nca`
- `cathode/precursor`
- `anode/graphite`
- `anode/silicon`
- `analysis/xrd`
- `analysis/psd-bet`
- `analysis/sem`
- `quality`

### `computer-science`
컴퓨터공학 전공 학습자료.

권장 subcategory:
- `algorithm`
- `data-structure`
- `operating-system`
- `network`
- `database`
- `computer-architecture`
- `software-engineering`
- `programming-language`

### `data-ai`
데이터·AI 학습자료.

권장 subcategory:
- `statistics`
- `machine-learning`
- `data-analysis`
- `data-engineering`
- `sql`
- `big-data`

### `certification`
자격증 시험 중심 학습자료.

권장 subcategory:
- `information-processing-engineer`
- `big-data-analysis-engineer`
- `adsp`
- `adp`

시험용으로 생성된 페이지는 해당 기술이 Computer Science/Data & AI에도 해당하더라도, 시험 문맥이 중심이면 `certification`을 우선한다.

### `language`
어학 학습자료.

권장 subcategory:
- `toeic-speaking`
- `opic`
- `english`

### `general`
위 분류에 자연스럽게 들어가지 않는 개인 학습자료.

## 경로 규칙

기본 형식:

```text
study/pages/<category>/<subcategory>/<slug>.html
```

예시:

```text
study/pages/computer-science/network/tcp-three-way-handshake.html
study/pages/computer-science/operating-system/process-vs-thread.html
study/pages/certification/information-processing-engineer/database-normalization.html
study/pages/data-ai/statistics/skewness-and-kurtosis.html
study/pages/battery/cathode/lfp/calcination-atmosphere.html
```

기존 레거시 페이지의 URL은 링크 깨짐 방지를 위해 강제로 이동하지 않는다.

## slug 규칙

- 영문 소문자 사용
- 단어 구분은 `-`
- 짧고 의미가 분명해야 함
- 날짜나 임의 숫자는 원칙적으로 넣지 않음
- 동일 slug가 이미 있으면 주제를 더 구체화

좋음:
- `tcp-three-way-handshake`
- `database-normalization`
- `lfp-calcination-atmosphere`

피함:
- `study1`
- `new-page-final`
- `20260826-note`

## catalog.json item schema

모든 게시 페이지는 아래 필드를 가진다.

```json
{
  "id": "database-normalization",
  "title": "데이터베이스 정규화",
  "description": "1NF부터 BCNF까지 정규화 목적과 함수 종속을 설명하는 학습자료.",
  "category": "computer-science",
  "subcategory": "database",
  "tags": ["DB", "정규화", "1NF", "2NF", "3NF", "BCNF"],
  "level": "intermediate",
  "url": "/study/pages/computer-science/database/database-normalization.html",
  "created": "YYYY-MM-DD",
  "updated": "YYYY-MM-DD"
}
```

### 필드 규칙

- `id`: 기본적으로 slug와 동일
- `title`: 원문 `<title>`/`<h1>`을 참고하되 목록에서 읽기 좋은 제목
- `description`: 1~2문장, 검색 결과에서 주제를 판단할 수 있게 작성
- `category`: taxonomy의 대분류 중 하나
- `subcategory`: 필요한 만큼 `/`로 계층 표현 가능
- `tags`: 검색에 유용한 한국어·영문 핵심 키워드 3~8개
- `level`: `beginner`, `intermediate`, `advanced` 중 하나
- `url`: `/study/...`로 시작하는 절대 경로
- `created`: 최초 게시일
- `updated`: 마지막 내용 수정일

## 중복 처리

기존 catalog에 같은 주제가 있으면 새 파일을 무조건 만들지 않는다.

- 사실상 같은 내용의 최신판이면 기존 페이지 업데이트를 우선한다.
- 관점이 다르거나 범위가 명확히 다르면 별도 페이지로 분리한다.
- 판단이 애매하면 기존 페이지와 새 페이지를 모두 유지하는 방향보다 기존 페이지를 확장하는 쪽을 우선한다.

## HTML 처리 원칙

- 사용자가 붙여넣은 HTML 디자인과 설명 방식은 최대한 유지한다.
- 외부 CDN, Google Fonts, Tailwind, SVG, JS 사용은 허용한다.
- 깨진 상대경로가 있으면 GitHub Pages에서 작동하도록 수정할 수 있다.
- 특정 ChatGPT 전용 shell/render 함수에 강하게 의존해 일반 웹에서 표시되지 않는 경우에는 필요한 최소 수정만 한다.
- 임의로 콘텐츠를 축약하거나 시험답안 형태로 다시 쓰지 않는다.

## 공개 저장소 주의

이 저장소는 public이다. 개인 스터디용 공개 자료만 게시한다.

다음과 같은 비공개/회사 고유 데이터가 포함된 HTML은 게시하지 않는다.
- 실제 회사 공정조건 또는 Spec
- 고객사/라인/제품 식별정보
- 실제 품질·생산 데이터
- 사내 회의/보고 내용
- 공개되지 않은 설비 Capacity 또는 공정 레시피

이런 내용이 발견되면 공개 Study Library에 그대로 게시하지 않는다.

## Publisher에게 주는 짧은 명령 예시

HTML을 붙인 뒤 다음 정도면 충분하다.

```text
스터디에 추가해줘
```

또는:

```text
이 HTML 게시해줘
```

Publisher는 이 문서와 `catalog.json`을 읽은 뒤 분류, 경로, 메타데이터, GitHub 반영을 알아서 처리한다.
