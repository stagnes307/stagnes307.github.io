# 1-8-2-1. 윈도우·그룹함수로 순위와 집계 DML 작성 · 특정 업무 기능 SQL 작성

## 수행 범위와 학습 목표

이 레슨은 조회 결과의 행 단위를 정확히 정한 뒤 **윈도우·그룹함수로 순위와 집계 DML 작성**을 수행하고, 요구사항의 업무 규칙을 관계 연산으로 바꾸어 **특정 업무 기능 SQL 작성**을 완성하는 실무를 다룬다. 여기서 DML은 데이터 조회·조작 문장을 뜻하지만, 예시는 분석과 업무 조회에 집중한다. 사용자·권한 DCL은 다음 레슨의 주범위이므로 다루지 않는다.

학습 후에는 다음을 할 수 있어야 한다.

- 원천 행, 그룹 결과 행, 윈도우 계산 행의 차이를 설명한다.
- GROUP BY·집계함수·HAVING으로 업무 단위 집계를 작성한다.
- PARTITION BY·ORDER BY·frame을 명시해 순위·누계·이동값을 계산한다.
- ROW_NUMBER, RANK, DENSE_RANK를 동률 정책에 맞게 선택한다.
- 조인 증폭, NULL, 중복, 결정적 정렬, 날짜 경계를 고려해 SQL을 작성한다.
- 요구–예상 결과–SQL–검증 결과를 추적하고 성능·보안 기준으로 완료를 판단한다.

## 첫 판단: 결과의 한 행은 무엇인가

SQL을 쓰기 전에 결과 한 행의 의미, 즉 결과 grain을 문장으로 적는다. “월별·상품군별 판매 한 행”, “직원별 최신 평가 한 행”, “주문 한 행과 고객 누적금액”처럼 정한다. grain이 없으면 GROUP BY 열을 무작정 늘리거나 조인으로 행이 증식해도 오류를 알아채기 어렵다.

다음 질문에 답한 뒤 작성한다.

- 기준 모집단은 주문, 주문항목, 고객 중 무엇인가?
- 취소·삭제·미확정 자료를 포함하는가?
- 기간의 시작과 끝, 시간대, 기준일은 무엇인가?
- 금액은 원화 환산 전후 중 무엇이며 세금·할인을 포함하는가?
- NULL은 미입력, 해당 없음, 0 중 무엇을 뜻하는가?
- 동률 순위와 동일 시각 자료의 우선순위는 무엇인가?

예를 들어 주문 한 건에 항목 세 건과 결제 두 건을 동시에 조인하면 3×2인 여섯 행이 생길 수 있다. 그 상태에서 주문금액을 합하면 과대 집계된다. 각 다대일 관계를 요구 grain으로 먼저 집계하거나 존재 여부만 필요하면 EXISTS를 사용한다.

## 그룹함수와 GROUP BY

그룹함수는 여러 입력 행을 그룹별 한 행으로 줄인다. COUNT, SUM, AVG, MIN, MAX가 대표적이다. 비집계 선택 열은 원칙적으로 GROUP BY의 그룹 키여야 한다. 제품의 느슨한 동작에 기대어 그룹에 속하지 않은 열을 선택하면 임의 값이 나오거나 다른 DBMS에서 오류가 난다.

```sql
SELECT
    store_id,
    business_date,
    COUNT(*)                 AS order_count,
    SUM(net_amount)          AS net_total,
    AVG(net_amount)          AS average_order_amount
FROM confirmed_orders
WHERE business_date >= :from_date
  AND business_date <  :to_date
GROUP BY store_id, business_date;
```

WHERE는 그룹 전의 원천 행을 거르고 HAVING은 집계 뒤 그룹을 거른다. “확정 주문만 대상으로 월 매출이 일정 기준 이상인 상점”이라면 확정 조건은 WHERE, `SUM(net_amount) >= :threshold`는 HAVING에 둔다. 집계 결과 별칭을 HAVING에서 사용할 수 있는지는 제품에 따라 다르므로 이식성이 필요하면 집계식을 명시하거나 한 단계 바깥 쿼리로 감싼다.

COUNT의 의미도 구분한다. `COUNT(*)`는 그룹의 행 수, `COUNT(column)`은 NULL이 아닌 값 수, `COUNT(DISTINCT column)`은 NULL을 제외한 서로 다른 값 수다. AVG와 SUM은 일반적으로 NULL을 계산에서 제외한다. 미입력 금액을 0으로 간주할 업무 근거가 있을 때만 COALESCE를 적용한다.

## 조건부 집계

한 번의 그룹 스캔으로 상태별 건수를 구할 때 CASE를 사용한다.

```sql
SELECT customer_id,
       SUM(CASE WHEN status = 'PAID'      THEN 1 ELSE 0 END) AS paid_count,
       SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_count,
       SUM(CASE WHEN status = 'PAID'      THEN net_amount ELSE 0 END) AS paid_total
FROM orders
WHERE ordered_at >= :start_at
  AND ordered_at <  :end_at
GROUP BY customer_id;
```

`ELSE 0`을 생략하면 조건에 맞는 행이 전혀 없는 그룹에서 SUM 결과가 NULL일 수 있다. 반대로 NULL과 0을 구분해야 하는 지표에는 무조건 0을 넣으면 안 된다. 조건별 모집단이 배타적인지, 합계가 전체 건수와 맞는지 통제합계로 검증한다.

## 윈도우 함수의 원리

윈도우 함수는 입력 행을 유지한 채 관련 행 집합에서 값을 계산한다. 기본 형태는 `함수() OVER (PARTITION BY ... ORDER BY ... frame)`이다.

- PARTITION BY: 계산을 다시 시작하는 업무 집단이다.
- ORDER BY: 집단 안의 순서이며, 순위·누계·선후값 의미를 정한다.
- frame: 현재 행을 기준으로 계산에 포함할 행 범위다.

GROUP BY는 고객별 한 행으로 축약하지만, `SUM(amount) OVER (PARTITION BY customer_id)`는 주문 각 행을 유지하면서 고객 합계를 붙인다. 최종 결과 grain을 보고 어느 방식을 쓸지 정한다.

```sql
SELECT order_id,
       customer_id,
       ordered_at,
       net_amount,
       SUM(net_amount) OVER (
           PARTITION BY customer_id
       ) AS customer_total,
       SUM(net_amount) OVER (
           PARTITION BY customer_id
           ORDER BY ordered_at, order_id
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_total
FROM confirmed_orders;
```

누계에서는 frame을 명시한다. 일부 DBMS의 기본 frame은 같은 정렬값을 동료 행으로 묶어 예상과 다른 누계를 만들 수 있다. 행 단위 누계라면 `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`를 명시하고, 업무상 같은 날짜의 모든 행을 한꺼번에 포함해야 한다면 그 의미에 맞는 frame을 선택한다.

## 순위 함수 선택

ROW_NUMBER는 동률이어도 1, 2, 3처럼 서로 다른 번호를 준다. RANK는 동률 다음 순위를 건너뛰고, DENSE_RANK는 건너뛰지 않는다.

| 점수 | ROW_NUMBER | RANK | DENSE_RANK |
|---:|---:|---:|---:|
| 95 | 1 | 1 | 1 |
| 95 | 2 | 1 | 1 |
| 90 | 3 | 3 | 2 |

“고객별 최근 주소 한 건”은 반드시 한 행을 골라야 하므로 ROW_NUMBER가 적합하다. 이때 `ORDER BY changed_at DESC`만 쓰면 같은 시각에서 결과가 실행마다 달라질 수 있다. 변경 순번이나 기본키 같은 고유한 보조 정렬키를 추가한다.

```sql
WITH ranked_address AS (
  SELECT a.*,
         ROW_NUMBER() OVER (
           PARTITION BY customer_id
           ORDER BY changed_at DESC, address_id DESC
         ) AS rn
  FROM customer_address a
)
SELECT customer_id, postal_code, address_line
FROM ranked_address
WHERE rn = 1;
```

“공동 1위를 모두 선발”이면 RANK 또는 DENSE_RANK를 쓰고 다음 등수의 간격을 업무 규칙으로 확인한다. 결과 건수를 고정해야 하는데 동률을 모두 포함하면 상위 N건보다 많아질 수 있다.

## 선후값·구간·이동 계산

LAG는 현재 행 이전 값, LEAD는 다음 값을 가져온다. 상태 변경 간격, 전월 대비, 연속 구간을 구할 때 자체 조인보다 의도가 명확할 수 있다.

```sql
WITH monthly AS (
  SELECT customer_id, sales_month, SUM(net_amount) AS month_total
  FROM monthly_order_source
  GROUP BY customer_id, sales_month
)
SELECT customer_id,
       sales_month,
       month_total,
       LAG(month_total) OVER (
         PARTITION BY customer_id ORDER BY sales_month
       ) AS previous_total
FROM monthly;
```

월이 빠져 있으면 LAG는 “직전 행”이지 반드시 “직전 달”이 아니다. 달력 테이블과 고객 집합을 결합해 빈 달을 만들 것인지, 존재하는 직전 거래월과 비교할 것인지 요구를 확인한다. 이동평균도 `ROWS 2 PRECEDING`이 세 행인지 세 달인지 구분한다.

첫 행의 LAG와 마지막 행의 LEAD는 기본적으로 NULL이다. 이를 0이나 현재값으로 바꾸기 전에 업무 의미를 정한다. 날짜 차이 계산 문법과 월말 규칙은 DBMS에 따라 달라질 수 있으므로 대상 제품의 함수와 시간대 정책을 확인한다.

## 특정 업무 기능 SQL 작성 절차

**특정 업무 기능 SQL 작성**은 단순 문법 조합이 아니라 요구를 검증 가능한 관계 연산으로 바꾸는 과정이다.

1. 요구 문장에서 행위자, 기준 모집단, 출력 항목, 조건, 정렬, 예외를 표시한다.
2. 결과 한 행의 grain과 후보키를 정의한다.
3. 원천 테이블의 키·관계·NULL·유효기간·상태 코드를 확인한다.
4. 작은 예시 데이터와 기대 결과를 손으로 먼저 작성한다.
5. 필터, 조인, 그룹, 윈도우, 최종 필터 순서로 쿼리를 단계화한다.
6. 각 단계의 건수·합계·키 유일성을 확인한다.
7. 경계일, NULL, 동률, 중복, 빈 그룹, 다대다 조인을 시험한다.
8. 바인드 변수와 허용목록을 사용하고 민감 열의 최소 조회 권한을 확인한다.
9. 실제에 가까운 분포·량에서 실행 계획과 시간을 측정한다.
10. 요구–SQL–시험–실행 계획을 추적하고 변경·되돌리기 절차를 남긴다.

복잡한 SQL은 공통 테이블 식이나 뷰로 논리 단계를 나눌 수 있지만, 이름만 늘린다고 이해하기 쉬워지는 것은 아니다. 각 단계가 “확정 주문”, “고객별 월 합계”, “월 순위”처럼 업무 의미를 가져야 한다. 중간 결과를 확인할 수 있어야 결함 위치도 좁힐 수 있다.

## 실무 판단 기준

정확성 판단은 다음 불변식으로 한다.

- 결과 키가 요구한 grain에서 유일하다.
- 상태별 건수의 합이 전체 건수와 일치한다.
- 조인 전후의 기준 모집단 건수와 금액 차이를 설명할 수 있다.
- 기간 경계가 겹치거나 빠지지 않는다.
- 동률과 NULL 처리 결과가 예시 기대값과 일치한다.
- 같은 입력과 기준시점이면 결정적인 순서와 결과를 낸다.

성능 판단은 실행 계획에서 전체 스캔 여부만 보는 것이 아니다. 반환 행 수, 선택도, 조인 순서, 정렬·해시 메모리, 임시 영역, 인덱스 활용, 반복 호출 횟수를 함께 본다. 윈도우 함수의 PARTITION BY와 ORDER BY는 큰 정렬을 요구할 수 있다. 먼저 불필요한 행과 열을 줄이되 결과 의미를 바꾸지 않아야 한다.

보안 판단에서는 사용자 입력을 SQL 문자열에 연결하지 않고 값은 바인드한다. 동적 정렬 열처럼 식별자를 선택해야 하면 승인된 이름의 허용목록으로 매핑한다. 조회 열과 행 범위는 호출자의 권한·목적에 맞게 최소화하고, 실행 계획이나 오류에 내부 구조와 민감값을 과도하게 노출하지 않는다.

## 구체 업무 시나리오

영업팀이 “월별 상품군 매출과 상품군 안의 상점 순위, 전월 대비 증감”을 요청했다고 하자. 결과 한 행은 `월+상품군+상점`이다. 먼저 확정 주문항목을 기간·상태로 거르고, 주문항목 grain에서 순매출을 계산한다. 상품과 상점 차원은 유효한 키로 한 번씩만 조인한다. 그런 다음 월·상품군·상점별 SUM을 구한다.

두 번째 단계에서 상품군·월을 PARTITION으로, 매출 내림차순과 상점 ID를 정렬 기준으로 하여 순위를 계산한다. “공동 순위” 요구라면 RANK를, 보고서 행마다 고유 번호가 필요하면 ROW_NUMBER를 쓴다. 전월 비교는 상점·상품군을 PARTITION으로 한 LAG를 사용하되 달이 빠질 수 있으면 달력 집합을 먼저 만든다.

검증 데이터에는 동률 상점, 주문 없는 달, 취소 주문, NULL 할인, 주문 한 건의 여러 항목을 포함한다. 월 합계가 원천 확정 주문항목 합계와 일치하고, 순위별 건수·전월 기준이 요구와 맞을 때 완료한다.

## 산출물과 체크리스트

산출물은 업무 SQL 요구 명세, 결과 grain·키 정의, 원천–결과 매핑표, 예시 데이터·기대 결과, 단계별 SQL, 건수·합계 검증표, 실행 계획·성능 결과, 권한 검토표, 형상·배포 기록이다.

- [ ] 결과 한 행의 의미와 후보키가 명확하다.
- [ ] WHERE와 HAVING의 적용 시점을 구분했다.
- [ ] COUNT(*)·COUNT(열)·COUNT(DISTINCT)의 의미가 요구와 맞다.
- [ ] NULL을 0으로 바꾸는 업무 근거가 있다.
- [ ] 다대다 조인과 조인 증폭을 건수·합계로 확인했다.
- [ ] PARTITION BY·ORDER BY·frame을 명시적으로 검토했다.
- [ ] 동률 순위와 결정적 보조 정렬키를 합의했다.
- [ ] 날짜·시간대·빈 기간의 의미가 정의되었다.
- [ ] 경계·중복·동률·빈 결과 시험이 기대값과 일치한다.
- [ ] 바인드·최소 권한·실행 계획·운영 추적을 확인했다.

## 자주 틀리는 포인트

- 결과 grain을 정하지 않고 SELECT 열부터 나열한다.
- WHERE와 HAVING을 바꾸어 모집단 자체를 잘못 집계한다.
- `COUNT(column)`이 NULL을 세지 않는다는 점을 놓친다.
- 주문·항목·결제를 한꺼번에 조인해 금액을 중복 합산한다.
- ROW_NUMBER, RANK, DENSE_RANK의 동률 정책을 구분하지 않는다.
- 윈도우 ORDER BY에 고유 보조키가 없어 결과가 비결정적이다.
- 누계 frame을 생략하고 기본 동작이 항상 행 단위라고 생각한다.
- LAG의 직전 행을 달력상 직전 월로 오해한다.
- 모든 NULL을 0으로 바꾸어 미측정과 실제 0을 합친다.
- 작은 예시만 확인하고 실제 분포의 정렬·조인 비용을 측정하지 않는다.

## 확인 문제

1. 결과 grain을 SQL 작성 전에 정의해야 하는 이유를 쓰시오.
2. WHERE와 HAVING의 처리 대상 차이를 설명하시오.
3. COUNT(*), COUNT(column), COUNT(DISTINCT column)의 차이를 쓰시오.
4. GROUP BY와 윈도우 SUM이 결과 행 수에 미치는 차이를 설명하시오.
5. ROW_NUMBER, RANK, DENSE_RANK의 동률 처리 결과를 비교하시오.
6. 고객별 최신 행 한 건을 안정적으로 고를 때 정렬 기준에 필요한 조건은 무엇인가?
7. 누적합에서 window frame을 명시해야 하는 이유를 쓰시오.
8. LAG가 직전 달을 항상 의미하지 않는 이유와 해결 방향을 쓰시오.
9. 다대다 조인으로 집계가 부풀어 오르는 문제를 예방하는 방법을 쓰시오.
10. 특정 업무 기능 SQL의 완료를 판단할 검증 항목 다섯 가지를 쓰시오.

## 정답과 해설

1. 한 행의 의미와 키가 정해져야 그룹·조인·중복을 판단할 수 있다. grain이 없으면 결과 건수는 맞아 보여도 업무 의미가 어긋날 수 있다.
2. WHERE는 그룹 전에 원천 행을 제외하고 HAVING은 GROUP BY 뒤 집계된 그룹을 제외한다. 위치를 바꾸면 집계 모집단이 달라진다.
3. COUNT(*)는 행 수, COUNT(column)은 해당 열이 NULL이 아닌 행 수, DISTINCT 형식은 NULL을 제외한 서로 다른 값 수다.
4. GROUP BY는 그룹마다 한 행으로 축약하지만 윈도우 SUM은 원래 행을 유지하고 각 행에 집계값을 붙인다.
5. ROW_NUMBER는 동률에도 고유 번호, RANK는 같은 순위 뒤 번호를 건너뜀, DENSE_RANK는 같은 순위 뒤 번호를 연속 부여한다.
6. 업무상 최신 시각과 함께 기본키·변경 순번처럼 결과를 하나로 정하는 고유 보조키가 필요하다.
7. 기본 frame은 제품과 정렬값의 동률에 따라 같은 값의 행을 함께 포함할 수 있다. 행 단위 누계인지 값 범위 누계인지 의도를 고정해야 한다.
8. LAG는 정렬 결과의 직전 행을 반환하므로 거래 없는 달은 행 자체가 없다. 달력 집합으로 빠진 달을 보완하거나 직전 거래월 비교임을 명시한다.
9. 각 다측 테이블을 목표 grain으로 먼저 집계하고 조인하거나, 존재 확인만 필요하면 EXISTS를 사용한다. 조인 단계마다 건수와 합계를 비교한다.
10. 결과 키 유일성, 건수·합계 균형, 경계·NULL·동률 결과, 결정적 정렬, 실제량 성능, 최소 권한 중 다섯 가지 이상을 확인한다.

## 핵심 요약

- SQL 작성의 출발점은 결과 한 행의 의미와 후보키 정의다.
- GROUP BY는 행을 축약하고 윈도우 함수는 행을 유지한 채 관련 집합을 계산한다.
- PARTITION BY·ORDER BY·frame과 동률 정책을 업무 의미에 맞게 명시한다.
- NULL·빈 기간·날짜 경계·조인 증폭은 예시 데이터와 통제합계로 확인한다.
- 특정 업무 기능은 요구를 단계별 관계 연산으로 바꾸고 중간 건수·합계를 검증한다.
- 완성된 SQL은 정확성뿐 아니라 결정성·성능·바인드·최소 권한·추적성을 충족해야 한다.
