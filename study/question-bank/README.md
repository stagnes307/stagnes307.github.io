# 기출문제 아카이브 운영 가이드

이 디렉터리는 빅데이터분석기사 필기시험에 관해 **출처가 확인된 관측 사실**과 독자 작성 메타데이터를 보관한다. 시험 원문을 확보하거나 재배포하는 저장소가 아니다. 공개·복원 문제라고 불리는 자료도 이용 허락이 확인되지 않으면 링크와 독자적인 개념 요약만 저장한다.

## 권리 모델

각 출처의 `rights.status`가 저장·배포 경계를 결정한다.

| 상태 | canonical 저장 | 공개 JSON | 용도 |
| --- | --- | --- | --- |
| `public_fulltext` | 검토된 문제·선택지 허용 | 문제·선택지 허용 | 명시적인 공개 재배포 근거가 있는 자료 |
| `private_only` | 로컬의 ignored `private/` 또는 로컬 빌드에서만 허용 | 해당 출처의 appearance 제외 | 사용자가 정당하게 보유하지만 공개할 수 없는 자료 |
| `link_only` | URL, 위치, 독자 요약만 허용 | 링크와 독자 요약만 허용 | 재배포 허락이 확인되지 않은 웹·도서 자료 |
| `blocked` | 문제 원문 수집 금지 | 출처 정책 메타데이터만 허용 | 운영기관 정책 등으로 수집이 금지된 자료 |

`link_only` 또는 `blocked` 출처의 `question_text`와 `choices`는 validation 오류다. 공개 exporter는 `public_fulltext`가 아닌 원문을 선택하지 않으며, 최종 공개 JSON도 별도의 fail-closed 검사를 통과해야 한다. 출처 링크와 `source_locator`는 원자료의 위치를 가리킬 뿐, 해당 문항이나 정답이 공식임을 뜻하지 않는다.

## 디렉터리와 데이터 흐름

과정별 canonical 입력은 `study/question-bank/<course-id>/` 아래에 둔다.

- `sources.json`: 출처, 신뢰도, 권리 근거
- `rounds.json`: 시험 회차와 검증 상태
- `question-groups.json`: 동일 문항군과 회차별 appearance, 현행 범위 분류
- `question-variants.json`: 출처별 표현·정답 주장·독자 요약
- `annotations.json`: 검토된 키워드, 해설, 난이도
- `analysis-sets.json`: 재현 가능한 분석 포함 집합
- `generated_questions.json`: 기출과 분리된 자체 생성 연습문제

다음 경로는 공개 저장소에 포함하지 않는다.

- `study/question-bank/<course-id>/private/`
- `study/question-bank/<course-id>/build/`
- `study/courses/<course-id>/questions/data/questions.local.json`

로컬 자료는 `private/` 아래에 canonical과 같은 파일명·문서 헤더를 사용한 **부분 overlay**로 둔다. 필요한 파일만 만들 수 있으며, 새 ID는 추가하고 기존 ID는 key-aware merge한다. 따라서 기존 회차의 `source_ids`와 기존 appearance의 `variant_ids`에는 비공개 출처·variant만 적은 부분 레코드로 값을 보탤 수 있다. 배열은 canonical 순서를 유지하면서 중복 없이 합쳐지고, 나머지 필드는 overlay 값이 우선한다.

예를 들어 공개 appearance에 로컬 전문을 연결하려면 `private/sources.json`과 `private/question-variants.json`에 새 레코드를 두고, `private/rounds.json`에는 `round_id`와 추가할 `source_ids`만, `private/question-groups.json`에는 `question_id`, `appearance_id`, 추가할 `variant_ids`만 둔다. 병합된 전체 문서는 validation을 통과해야 하며 로컬 JSON·SQLite에만 반영된다. 추적되는 canonical 문서는 private overlay에 의존할 수 없고, `private_only` 출처나 그 원문을 넣으면 validation이 실패한다.

빌드는 권리 검사를 거친 `questions.public.json`, 분석 보고서, 정적 페이지를 생성한다. 로컬에서만 허용된 전문이 있을 때에만 ignored `questions.local.json`을 별도로 만든다. 공개 페이지는 기본적으로 public 데이터만 읽으며, 로컬 데이터 사용은 명시적인 local scope에서만 가능하다.

## 갱신 절차

네트워크 크롤링은 빌드나 CI의 일부가 아니다. 출처를 사람이 확인한 뒤 canonical JSON에 URL, 확인일, 권리 근거, 원문 위치, 독자 작성 요약을 기록한다. 한 출처의 기억·복원만으로 공식 정답이나 정확한 문항 문구로 승격하지 않는다.

저장소 루트에서 다음 순서로 검증하고 빌드한다.

```powershell
python study/factory/scripts/validate_questions.py big-data-analysis-engineer-written
python study/factory/scripts/build_question_bank.py big-data-analysis-engineer-written
python study/factory/scripts/build_question_bank.py big-data-analysis-engineer-written --check
python -m unittest discover -s study/factory/tests -p "test_question_bank*.py" -v
```

`analysis_eligible`은 검토 완료, 현행 범위 포함, 검증된 실제 시행 회차라는 조건을 모두 만족해야 한다. 중복 후보와 정답 충돌은 자동 병합·채택하지 않고 보고서에서 사람이 검토한다.

생성된 `reports/analysis-set.json`에는 데이터셋 버전에 묶인 `analysis_set_id`, 검토를 통과한 후보, 회차 coverage까지 통과해 실제 빈도·점수에 포함된 appearance를 각각 기록한다.

## 중요도 계산과 해석 제한

세부항목 중요도는 다음 관측식으로 계산한다.

```text
50 × 회차 출현률 + 30 × 최근 3개 적격 회차 출현률 + 20 × 정규화 관측량
```

문항의 주 분류(`primary_topic_code`)만 점수에 반영한다. 한 회차가 빈도 분모에 들어가려면 분석 가능한 관측 문항이 예상 문항 수의 50% 이상이어야 한다. 적격 회차가 3개 미만이면 점수를 표시하지 않고 `근거 부족`으로 처리한다. 적격 회차가 5개 이상이고 coverage 중앙값이 75% 이상일 때만 근거 수준을 `sufficient`로 표시하며, 그 전에는 `provisional`이다.

이 점수는 저장소에 관측된 자료의 분포이지 공식 출제확률, 배점 예측, 합격 보장이 아니다. 특히 현재의 링크 기반 초기 자료처럼 회차 coverage가 낮거나 과거 교육과정의 복기만 있는 경우에는 “많이 언급된 주제” 이상으로 해석하지 않는다. 새 출처나 분류 변경으로 순위가 달라질 수 있으므로 데이터셋 버전과 coverage 보고서를 함께 확인한다.
