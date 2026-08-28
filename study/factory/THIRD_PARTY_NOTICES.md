# Third-Party Notices

Study Factory의 `Codex direct` 제작 프로필은 아래 공개 프로젝트가 설명한 교육 프레임워크와 이 저장소에 이미 존재하는 관련 생성 결과의 품질 패턴을 참고한다.

## Ailey & Bailey Canvas

- 프로젝트: [lemos999/ailey-bailey-canvas](https://github.com/lemos999/ailey-bailey-canvas)
- 고정 참조 커밋: [`8a36e77d025bb9c258bfeaf8587424783140b185`](https://github.com/lemos999/ailey-bailey-canvas/tree/8a36e77d025bb9c258bfeaf8587424783140b185)
- 저작권 고지: `Copyright (c) 2025 fewweekslater(Ray You). All rights reserved.`
- 라이선스: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-nc-sa/4.0/) (`CC BY-NC-SA 4.0`)
- 고정 커밋의 라이선스 원문: [LICENSE](https://github.com/lemos999/ailey-bailey-canvas/blob/8a36e77d025bb9c258bfeaf8587424783140b185/LICENSE)
- 상업 이용 문의: 원 프로젝트의 LICENSE에 안내된 저작자 연락처를 따른다.

## 이 저장소에서의 사용과 변경

### 고정 공개 프롬프트 스냅샷

`vendor/ailey-bailey-canvas/8a36e77d/`에는 위 고정 커밋의 `prompt_src/**/*.prompt.txt` 16개와 `LICENSE`를 Git blob 바이트 그대로 포함한다. `manifest.json`은 전체 커밋 SHA, README가 지시한 전체 파일의 사전순 조립 순서, 각 파일의 byte 길이와 SHA-256, 적용 라이선스를 기록한다.

`ailey-bailey-public-8a36e77d-ff-literal-v1`은 이 공개 원문 뒤에 Study Factory의 범위·사실성·출력 계약 오버레이를 결합한 프로필이다. 다음 사항은 원본에서 변경되었다.

FF와 CC 공개 프로필은 고정 공개 프롬프트의 출력 계약을 구현한 결정적 Study Factory 호환 생성 규격이다. 해당 프로필 또는 조립된 프롬프트의 SHA-256은 upstream Custom GPT나 별도 upstream LLM을 실제 호출했다는 기록이 아니다.

- 공식 curriculum source packet을 사실과 Lesson 범위의 우선 기준으로 사용
- H2 5개와 각 H2별 H3 3개, 단일 문단 문장 수, 제목 이모지 유일성을 기계적으로 검증
- 원문의 timestamp와 compass navigation을 FF에서 제거
- 원문의 `.cc`·`.ccc` HTML 셸을 사용하지 않고, script와 remote asset이 없는 별도 안전 정적 렌더러로 교체
- 현재 Lesson의 `source_refs`가 고른 curriculum 출처명, authority, 공식 URL, 확인일, 적용 기간을 렌더링된 CC의 보이는 `공식 출처` 패널에 표시
- curriculum에 정확히 등록된 공식 `http`/`https` URL만 `target="_blank"`, `rel="noopener noreferrer"` 이동 링크로 허용하고 외부 asset·script와 임의 URL은 거부
- 렌더링된 CC 화면에 원작자, `adapted by OpenAI Codex`, `CC BY-NC-SA 4.0` 표시

공개 원문과 오버레이를 적용한 FF 및 그 FF에서 만든 CC는 저작자표시·비영리·동일조건변경허락 조건을 유지해야 한다. 안전 렌더러의 프로그램 코드 자체에 대한 고지는 아래의 포함되지 않는 범위를 따른다.

### GitHub prompt Codex live 프로필

`ailey-bailey-public-8a36e77d-ff-codex-live-v1`은 위 16개 공개 prompt 모듈을 Codex 세션에 실제로 주입한 뒤 정확한 `.ff` Lesson 입력으로 생성한 Markdown 응답이다. `ailey-bailey-public-8a36e77d-cc-codex-live-static-v1`은 같은 Codex context에 정확히 `.cc`를 보내 얻은 HTML의 교육 본문을 보존하고, 공개 게시에 부적합한 원격 runtime·script·숨김 shell만 제거한 정적본이다.

이 live 경로도 원작자·고정 커밋·`CC BY-NC-SA 4.0` 표시를 유지한다. 실제 Ailey Custom GPT나 원저자의 비공개 지시를 호출했다는 뜻은 아니며, 생성자는 `openai-codex`다. 원 프로젝트가 이 실행 결과를 보증하거나 공식 Ailey 산출물로 승인했다는 의미도 아니다.

### 독자 Codex Study 프로필

[`prompts/codex-study-v1.md`](prompts/codex-study-v1.md)는 공개 원본의 전체 프롬프트를 복제하거나 Custom GPT의 비공개 지시를 재구성한 파일이 아니다. 공개 프로젝트가 설명한 상세 학습, 비판적 판별, 시각 교안이라는 교육적 방향과 기존 Ailey 생성 결과 78개에서 관찰한 품질 패턴을 바탕으로 다음을 새로 설계하고 작성했다.

- 토픽별 정의·원리·예시·비교·시험 함정·확인 문제를 요구하는 FF 계약
- FF와 CC 사이의 내용 동등성 점검
- JavaScript와 원격 asset을 제거한 정적 HTML 보안 계약
- CSP, 의미 구조, 표 caption/scope, SVG ARIA, 키보드·모바일·인쇄 접근성 규칙
- artifact별 producer, prompt profile, 시각, SHA-256을 보존하는 provenance 절차

변경 작성일은 2026-08-28이다. 원 프로젝트가 이 변경이나 Study Factory를 보증하거나 후원한다는 뜻은 아니다.

권리 범위에 대한 오해를 피하기 위해, 공개 원본을 바탕으로 한 개작물로 평가될 수 있는 `codex-study-v1` 프로필과 그 프로필을 의도적으로 적용한 표현물은 `CC BY-NC-SA 4.0`의 저작자표시·비영리·동일조건변경허락 조건에 따라 배포한다. 공유하거나 수정할 때는 다음을 유지해야 한다.

1. 위 저작자·프로젝트·고정 커밋의 표시
2. `CC BY-NC-SA 4.0` 표시와 라이선스 링크
3. 원본에서 변경되었다는 표시
4. 비상업적 이용 조건
5. 개작물을 같은 라이선스 또는 호환 라이선스로 공유하는 조건

## 포함되지 않는 범위

위 제3자 라이선스 고지는 다음 자료의 권리 상태를 임의로 바꾸지 않는다.

- Study 사이트와 Factory의 독자적인 프로그램 코드, 스키마, 템플릿
- 공공기관이 제공한 시험 출제기준의 사실 정보와 개별 이용조건
- 이 프레임워크와 무관하게 별도 출처 또는 별도 라이선스로 작성된 페이지
- 제3자의 상표권, 특허권, 인격권 또는 개인정보

각 공식 커리큘럼 출처와 확인일은 과정별 `curriculum.json` 및 `coverage.json`에 별도로 기록한다. 이 문서는 법률 자문이 아니며, 상업적 이용이나 재배포가 필요한 경우 원 프로젝트의 라이선스 원문과 적용 가능한 법률을 직접 확인해야 한다.
