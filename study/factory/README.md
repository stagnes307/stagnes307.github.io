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
- `cc-view.html`: 원본 CC를 보존한 채 화살표 이전·다음, 돌아가기·목차, 본문 위의 다음 화살표를 제공하는 전체 화면 iframe viewer. 스마트폰에서는 아래로 스크롤하면 도구 모음이 완전히 사라지고, 어느 위치에서든 위로 스크롤하면 다시 나타난다.
- `index.html`: FF 보기, 한 번에 `cc-view.html`로 진입하는 CC 버튼, 빈 sandbox의 fallback iframe, 앞뒤 Lesson 탐색을 제공하는 shell
- `meta.json`: Lesson 정보와 FF·CC 각각의 producer, prompt profile, 생성 시각, SHA-256

CC viewer의 원본 iframe은 스크롤 위치 확인에 필요한 `allow-same-origin`만 허용하며 `allow-scripts`는 허용하지 않는다. 따라서 자동 축소 기능을 제공하면서도 원본 CC의 스크립트 실행은 계속 차단된다.

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

## 고정 공개 Ailey 프로필

공개 프롬프트를 문자 그대로 적용해야 하는 작업은 기본 `codex-study-v1`과 분리된 다음 프로필을 사용한다.

- FF: `ailey-bailey-public-8a36e77d-ff-literal-v1`
- CC: `ailey-bailey-public-8a36e77d-cc-safe-v1`

두 프로필은 고정 공개 프롬프트의 출력 계약을 구현한 `deterministic-study-factory-compatibility` 생성 규격이다. 프로필을 사용했다는 기록은 upstream Custom GPT 또는 별도 upstream LLM을 실제 호출했다는 뜻이 아니다. `scripts/ailey_public_profile.py`의 `public_profile_fingerprint()`는 고정 upstream bundle과 로컬 overlay를 조립한 system spec의 SHA-256을 반환하며, 실행 서비스나 생성 응답의 식별자는 아니다.

고정 커밋 `8a36e77d025bb9c258bfeaf8587424783140b185`의 `prompt_src/**/*.prompt.txt` 16개와 `LICENSE`는 `vendor/ailey-bailey-canvas/8a36e77d/`에 원본 Git blob과 byte-identical하게 포함된다. `manifest.json`의 사전순 `assembly_order`와 SHA-256이 조립 순서와 무결성을 결정한다. 프로필 registry와 snapshot은 다음 명령으로 독립 검증할 수 있다.

```powershell
python study/factory/scripts/validate_prompt_profiles.py
python study/factory/scripts/validate_all.py
```

Lesson별 system spec과 user message는 다음처럼 조립한다. positional course/lesson 인자도 호환되지만 자동화에서는 named flag를 권장한다.

```powershell
python study/factory/scripts/assemble_ailey_prompt.py --course-id adsp --lesson-id 1-1-1-1
```

응답에서는 FF Markdown 본문만 `ff.md`로 저장한다. FF는 H2 5개와 각 H2 아래 H3 3개, 20개 제목의 단일 코드포인트 이모지 유일성, 각 H3 첫 단일 문단 15~20문장, 모든 topic literal, 마지막 H2의 `통합 적용 / 확인 문제와 정답·해설 / 요약` 역할을 모두 충족해야 한다.

공개 원문의 `.cc`·`.ccc` 출력은 script, remote asset, 숨겨진 본문과 잘못된 `lang="KR"` 계약을 포함하므로 저장하거나 게시하지 않는다. 검증된 FF만 안전 렌더러에 전달한다. 안전 렌더러는 현재 Lesson의 `source_refs`가 선택한 curriculum 출처명, authority, 공식 URL, 확인일, 적용 기간을 보이는 `공식 출처` 패널로 만든다. curriculum에 정확히 등록된 `http`/`https` URL만 새 탭 이동 링크로 허용하며 `target="_blank"`와 `rel="noopener noreferrer"`를 강제한다. 외부 asset·script와 임의 URL은 계속 거부한다.

```powershell
python study/factory/scripts/render_ailey_public_cc.py adsp 1-1-1-1
python study/factory/scripts/render_ailey_public_cc.py --course-id adsp --lesson-id 1-1-1-1 --ff path/to/ff.md --out path/to/cc.html
```

안전 렌더러는 기존 Codex Markdown 변환기를 재사용해 실행 가능한 HTML을 만들지 않고, 결과 화면에 원작자·`adapted by OpenAI Codex`·`CC BY-NC-SA 4.0` 귀속을 표시한다. provenance 기록에는 FF와 CC의 서로 다른 profile ID를 사용한다.

```powershell
python study/factory/scripts/record_artifact.py adsp 1-1-1-1 ff --producer openai-codex --prompt-profile ailey-bailey-public-8a36e77d-ff-literal-v1
python study/factory/scripts/record_artifact.py adsp 1-1-1-1 cc --producer openai-codex --prompt-profile ailey-bailey-public-8a36e77d-cc-safe-v1
```

`record_artifact.py`와 validator는 registry에 없는 profile, artifact kind가 맞지 않는 profile, producer가 다른 profile을 거부한다.

### GitHub 프롬프트를 적용한 Codex live `.ff → .cc`

사용자가 공개 Ailey 프롬프트를 **실제 모델 실행에 주입한 응답**을 요구하면 위의 결정적 compatibility profile을 사용하지 않는다. 다음 live profile을 사용한다.

- FF: `ailey-bailey-public-8a36e77d-ff-codex-live-v1`
- CC: `ailey-bailey-public-8a36e77d-cc-codex-live-static-v1`

이 경로는 Lesson마다 새 Codex 세션을 만들고, pinned GitHub prompt와 사용자 승인 예외를 `model_instructions_file`로 주입한 뒤 별도의 첫 user turn으로 정확한 `.ff` 입력만 실행한다. FF 완료 후 같은 thread ID를 `codex exec resume`으로 재개해 두 번째 user turn으로 정확히 `.cc`만 보낸다. Custom GPT는 호출하지 않으며 producer는 두 artifact 모두 `openai-codex`다. CC는 실제 `.cc` 응답의 교육 본문을 보존하고 실행 shell만 정적화한다. FF에서 CC를 다시 결정적으로 렌더링하지 않는다.

한 Lesson의 조립 입력과 정확한 user turn은 다음처럼 확인한다.

```powershell
python study/factory/scripts/assemble_ailey_live_prompt.py quality-management-engineer-written 1-1-1-1 --part user
python study/factory/scripts/assemble_ailey_live_prompt.py quality-management-engineer-written 1-1-1-1 --part all
```

네 과정의 교체 대상과 최대 4개 병렬 실행을 먼저 확인한 뒤 실행한다.

```powershell
python study/factory/scripts/run_ailey_github_codex.py --dry-run
python study/factory/scripts/run_ailey_github_codex.py --workers 4 --attempts 2 --timeout 1200
```

runner는 Codex JSONL의 thread ID, `turn.completed`, `output-last-message` 일치를 검증한다. raw FF·CC, 전송 로그, thread ID와 raw CC SHA-256은 시스템 Temp의 `ailey-github-codex-live-study-factory`에 남긴다. 게시 파일은 FF와 같은 context의 CC가 모두 콘텐츠 gate를 통과한 Lesson만 교체한다. 모델 사용량 또는 전역 rate limit은 대량 failed로 바꾸지 않고 새 작업 시작을 멈춘다.

#### Static Visual CC v2

브라우저 Ailey 수준의 실제 도식과 레슨별 디자인이 필요하면 visual-v2 pair profile을 사용한다.

- FF: `ailey-bailey-public-8a36e77d-ff-codex-visual-v2`
- CC: `ailey-bailey-public-8a36e77d-cc-codex-live-visual-v2`

이 경로도 첫 turn에 정확한 `.ff`, 같은 thread의 둘째 turn에 정확한 `.cc`만 보낸다. 새 FF를 버리지 않고 그 FF와 CC를 `ff.md`·`cc.html`·`meta.json` 세 파일로 한 번에 교체하므로 게시된 두 화면은 같은 모델 문맥의 한 쌍이다. 생성 중인 임시 FF, pinned model instructions, Codex thread는 SHA-256 audit meta로 CC에 연결한다.

visual-v2는 공개 prompt의 placeholder/runtime shell을 명시적으로 재정의한다. 결과는 레슨 고유 CSS와 실제 inline SVG를 가진 self-contained HTML이어야 하며, strict staticizer는 앞뒤 설명, script·remote asset·inline event/style·hidden content·SVG SMIL·위험 CSS를 발견하면 고쳐서 게시하지 않고 해당 시도를 실패시킨다. 복합 Lesson은 서로 다른 SVG 두 개가 필요하다. H1 12~36자, 정확한 공식 제목, 보이는 본문 3,500자 이상, 모바일·reduced-motion·print CSS, 표 최대 두 개도 profile gate에서 검사한다.

```powershell
python study/factory/scripts/assemble_ailey_visual_prompt.py quality-management-engineer-written 1-1-1-1 --part user
python study/factory/scripts/run_ailey_visual_cc.py --dry-run --target quality-management-engineer-written:1-1-1-1
python study/factory/scripts/run_ailey_visual_cc.py --workers 4 --attempts 3 --timeout 1800
```

여러 runner가 같은 Lesson을 동시에 교체하지 못하도록 모든 Codex live runner는 공통 OS artifact lock을 사용한다. visual-v2는 성공·실패 여부와 관계없이 선택 Course validator를 실행하고 마지막 summary에 결과를 기록한다.

### 결정적 공개 Ailey compatibility 일괄 생성

품질경영기사·산업안전기사 필기/실기는 curriculum의 각 공식 원자에 대응하는 `content/<course-id>.atom-facts.json` 지식 팩을 먼저 검증한 뒤 생성한다. 지식 팩은 Lesson과 정규화 topic의 순서를 그대로 보존하고, 각 atom에 정의·판별 기준·적용 또는 검증 사실 3개를 둔다. 렌더러는 이 사실을 한 번씩만 배치하고 공통 guide 사실도 teaching H3 전체에서 3회를 넘겨 반복하지 않는다. target 문구를 바꾼 것만으로 중복 검사를 피할 수 없도록 atom 사실의 교집합과 비율을 Course 전체에서 검사한다.

먼저 네 과정 모두 읽기 전용 preflight를 통과시킨다.

```powershell
python study/factory/scripts/generate_public_ailey_course.py --dry-run quality-management-engineer-practical quality-management-engineer-written industrial-safety-engineer-practical industrial-safety-engineer-written
```

실제 생성은 대상 Course 디렉터리가 없을 때만 허용된다. `--force` 옵션은 없으며, 한 Course를 메모리에서 전부 준비하고 짧은 staging 경로에서 FF·CC·meta·viewer·progress와 Course validator를 완성한 뒤 최종 디렉터리로 이동한다. catalog 또는 최종 이동이 실패하면 catalog는 같은 디렉터리의 임시 파일을 거쳐 원자적으로 복원된다. 여러 Course를 한 번에 게시하지 말고 작은 과정부터 하나씩 생성한 뒤 전체 테스트와 validator를 반복한다.

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
- 공개 Ailey literal FF: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-ff-literal-v1`
- 공개 Ailey safe CC: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-cc-safe-v1`
- 공개 GitHub prompt Codex live FF: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-ff-codex-live-v1`
- 같은 Codex context의 live `.cc` 정적본: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-cc-codex-live-static-v1`
- Static Visual v2 FF: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-ff-codex-visual-v2`
- 같은 Codex context의 Static Visual v2 CC: `producer=openai-codex`, `prompt_profile=ailey-bailey-public-8a36e77d-cc-codex-live-visual-v2`
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
- Codex live 경로의 사용량 또는 rate limit은 전역 중단 조건이다. legacy Ailey 경로의 인증·사용량 제한은 해당 브라우저 작업만 일시정지한다.

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
- 공개 Ailey literal FF: 정확히 H2 5×H3 3, H3 첫 문단 15~20문장, 20개 제목 이모지 중복 없음, topic literal과 고정된 마지막 세 H3 역할 포함
- 공개 Ailey safe CC: raw upstream wrapper/script/remote asset/숨김/lang 오류 없음, Codex CC 보안·접근성 gate와 보이는 `CC BY-NC-SA 4.0` 귀속 충족
- GitHub prompt Codex live FF: 정확한 Lesson H1·ID·제목·모든 topic 원문, 구조화된 Markdown, 확인 문제·정답/해설·요약 포함
- 같은 context의 live CC 정적본: raw `.cc` 본문에 정확한 Lesson identity·모든 topic·H1/content root가 먼저 존재하고, 정적화 뒤 script/remote/hidden/lang 오류 없이 Codex CC 보안·접근성 gate 충족
- Static Visual v2 pair: 실제 같은 thread의 FF/CC 해시 연결, 레슨 CSS 무결성, 1~2개 고유·접근 가능 SVG, 짧은 H1, 정확한 공식 제목, 3,500자 이상 보이는 본문, 모바일·인쇄·reduced-motion CSS, placeholder 0개
- Integrity: FF·CC가 현재 Lesson 제목 또는 ID를 포함하고 FF끼리 완전히 중복되지 않음
- Provenance: FF·CC 각각 producer/profile/generated_at/SHA-256이 있고 실제 파일과 해시 일치
- Meta: course/lesson/status와 artifact 기록 일치
- Lesson: index, FF/CC 탭, hash, 빈 sandbox iframe, navigation 존재
- Course: curriculum과 progress의 Lesson ID가 정확히 일치
- Coverage: 모든 공식 항목이 유효한 Learning Lesson에 매핑
- Global: catalog parse 및 기존 page 호환성

모든 로컬 확인은 `python -m http.server 8000 --bind 127.0.0.1`처럼 loopback에만 바인딩한 서버로 수행하고 `file://`는 사용하지 않는다. `0.0.0.0`이나 LAN 주소로 비공개 overlay를 제공하지 않으며, 브라우저 프로필, cookie, session, token은 저장소에 저장하지 않는다. 기출·출제분석의 전체 릴리스·복구 절차와 Node/Playwright 검증 명령은 [`study/question-bank/OPERATIONS.md`](../question-bank/OPERATIONS.md)를 따른다.

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
