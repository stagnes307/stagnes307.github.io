🧩 [새 열을 설계하는 기술] 빅데이터분석기사 실기 · 2-2-3-1. 파생변수 생성

#빅데이터분석기사 #실기 #데이터변환 #파생변수 #pandas #변수생성

🎯 먼저 잡을 핵심 — 파생변수는 왜 만들까?

파생변수(derived variable)는 이미 존재하는 변수들을 계산·결합·변환해서 새롭게 만든 변수야.

예를 들어 이런 데이터가 있다고 해보자.

Python
실행됨
import pandas as pd

df = pd.DataFrame({
    'price': [10000, 15000, 20000],
    'quantity': [2, 3, 1],
    'height': [170, 165, 180],
    'weight': [65, 55, 80]
})

print(df)
   price  quantity  height  weight
0  10000         2     170      65
1  15000         3     165      55
2  20000         1     180      80

여기에는 price, quantity가 있지만 총구매금액이라는 변수는 없어.

그런데

총구매금액 = 가격 × 수량

이라는 관계를 이용하면 새 변수를 만들 수 있지.

Python
실행됨
df['total_price'] = df['price'] * df['quantity']

이때 total_price가 바로 파생변수야.

핵심 구조는 이것뿐이야.

기존 변수 → 의미 있는 연산 → 새로운 변수

🔗 1. 기존 변수 조합 — 어떤 식으로 합칠까?

실기에서 가장 먼저 익혀야 하는 건 열끼리 직접 계산할 수 있다는 점이야.

산술 연산으로 생성
Python
실행됨
df['total_price'] = df['price'] * df['quantity']

결과:

   price  quantity  total_price
0  10000         2        20000
1  15000         3        45000
2  20000         1        20000

pandas에서는 같은 행에 있는 값끼리 자동으로 연산돼.

즉,

Python
실행됨
df['A'] + df['B']

는 개념적으로

1행의 A + 1행의 B
2행의 A + 2행의 B
3행의 A + 3행의 B
...

라는 뜻이야.

자주 쓰는 형태
Python
실행됨
df['sum'] = df['A'] + df['B']
df['diff'] = df['A'] - df['B']
df['product'] = df['A'] * df['B']
df['ratio'] = df['A'] / df['B']

여기서 중요한 실기 감각 하나.

Python
실행됨
df['A'] / df['B']

처럼 나눗셈이 나오면 B에 0이 있는지 생각해야 해.

파생변수는 그냥 “계산하는 것”이 아니라, 계산 결과가 정상적인지도 확인하는 것까지 한 세트야.

🛠️ 2. 파생변수 구현 — 시험에서 많이 쓰는 패턴

파생변수는 크게 몇 가지 패턴으로 정리할 수 있어.

두 변수의 연산

가장 기본형이야.

Python
실행됨
df['total_price'] = df['price'] * df['quantity']

기억할 문법은:

Python
실행됨
df['새변수'] = 연산식

이 형태야.

비율 변수 만들기
Python
실행됨
df['price_per_quantity'] = df['price'] / df['quantity']

이런 변수는 절대적인 크기보다 상대적인 관계를 보고 싶을 때 유용해.

예를 들면:

매출 / 고객 수 → 고객당 매출

총금액 / 수량 → 단가

구매 횟수 / 가입 기간 → 기간당 구매 빈도

여러 열을 이용한 합계·평균

예를 들어 시험 점수 데이터가 있다고 해보자.

Python
실행됨
score = pd.DataFrame({
    'kor': [80, 90, 70],
    'eng': [90, 80, 60],
    'math': [100, 70, 80]
})

세 과목 합계는 직접 더해도 돼.

Python
실행됨
score['total'] = score['kor'] + score['eng'] + score['math']

하지만 여러 열을 한꺼번에 계산할 때는 이런 형태가 더 편해.

Python
실행됨
score['total'] = score[['kor', 'eng', 'math']].sum(axis=1)

여기서 axis=1이 중요해.

axis=1의 의미
행 방향으로 계산

즉 한 사람의

국어 + 영어 + 수학

을 계산한다는 뜻이야.

반대로

Python
실행됨
score[['kor', 'eng', 'math']].sum(axis=0)

이면 각 과목의 전체 학생 점수를 더하게 돼.

실기에서는 이 구분을 확실히 해두자.

표현	계산 방향
axis=0	열별 계산
axis=1	행별 계산

파생변수 생성은 보통 각 행마다 새로운 값을 만드는 경우가 많기 때문에 axis=1이 자주 등장해.

평균 변수
Python
실행됨
score['mean'] = score[['kor', 'eng', 'math']].mean(axis=1)

이제 한 학생의 세 과목 평균이 새로운 변수가 돼.

kor, eng, math
      ↓
   mean

이런 식으로 여러 정보를 하나의 요약된 특징으로 압축하는 것도 파생변수 생성이야.

⚖️ 3. 조건에 따라 변수 만들기

산술 계산뿐 아니라 조건을 기준으로 새로운 범주형 변수를 만들 수도 있어.

예를 들어 평균이 80 이상이면 "high", 아니면 "low"라고 만들고 싶다고 하자.

Python
실행됨
import numpy as np

score['level'] = np.where(
    score['mean'] >= 80,
    'high',
    'low'
)

구조를 읽으면:

Python
실행됨
np.where(
    조건,
    조건이 참일 때 값,
    조건이 거짓일 때 값
)

이야.

즉,

Python
실행됨
np.where(score['mean'] >= 80, 'high', 'low')

는

평균이 80 이상인가?
맞으면 high, 아니면 low

라는 뜻이야.

파생변수는 따라서 두 종류로 생각하면 편해.

기존 변수
   │
   ├─ 숫자 연산 ──→ 새로운 수치형 변수
   │
   └─ 조건 판단 ──→ 새로운 범주형 변수
📐 4. 대표적인 파생변수 예 — BMI

height와 weight라는 두 변수가 있다고 하자.

BMI는 다음 관계를 이용해 만들 수 있어.

체중(kg) ÷ 키(m)²

데이터에서 키가 cm 단위라면 먼저 m로 바꿔야 하지.

Python
실행됨
df['height_m'] = df['height'] / 100
df['bmi'] = df['weight'] / (df['height_m'] ** 2)

혹은 중간 변수를 만들지 않고 한 번에 쓸 수도 있어.

Python
실행됨
df['bmi'] = df['weight'] / ((df['height'] / 100) ** 2)

여기서 중요한 건 코드 암기가 아니야.

파생변수 사고 순서
원래 변수
height(cm), weight(kg)
        ↓
필요한 단위 확인
cm → m
        ↓
관계식 적용
weight / height²
        ↓
새로운 변수
BMI

시험에서 처음 보는 변수를 만들라고 해도 문제에 주어진 관계를 이 흐름대로 코드로 옮기면 돼.

🔍 5. 생성 결과 확인 — 여기까지 해야 완성

파생변수를 만든 뒤 바로 다음 문제로 넘어가면 위험해.

반드시 생성 결과 확인을 해야 해.

가장 기본적인 방법은:

Python
실행됨
df.head()

또는 생성한 열만 확인:

Python
실행됨
df[['price', 'quantity', 'total_price']].head()

이 방식이 더 좋아.

왜냐하면 원래 변수와 파생변수를 나란히 비교할 수 있기 때문이야.

예를 들어:

Python
실행됨
df[['price', 'quantity', 'total_price']]

결과가

   price  quantity  total_price
0  10000         2        20000
1  15000         3        45000
2  20000         1        20000

라면 계산 관계가 맞는지 눈으로 바로 검증할 수 있지.

🧪 6. 값뿐 아니라 자료형도 확인하자

새로운 변수를 만들면 자료형도 바뀔 수 있어.

Python
실행됨
df.dtypes

예를 들어:

price            int64
quantity         int64
total_price      int64
bmi            float64

처럼 나올 수 있어.

특히 나눗셈을 하면 결과가 float가 되는 경우가 흔해.

필요하면 자료형을 변환할 수도 있어.

Python
실행됨
df['total_price'] = df['total_price'].astype(int)

다만 무조건 int로 바꾸는 습관은 좋지 않아.

소수점 자체가 의미 있는 변수라면 그대로 float로 두어야 해.

🚨 7. 파생변수에서 자주 발생하는 실수
열 이름을 문자열로 쓰지 않는 경우

잘못된 코드:

Python
실행됨
df[total] = df['price'] * df['quantity']

total이라는 Python 변수를 찾게 되니까 오류가 날 수 있어.

올바른 형태:

Python
실행됨
df['total'] = df['price'] * df['quantity']
여러 열 평균에서 axis를 빼먹는 경우
Python
실행됨
score[['kor', 'eng', 'math']].mean()

이렇게 하면 학생별 평균이 아니라 열별 평균을 계산해.

학생별 평균을 파생변수로 만들려면:

Python
실행됨
score['mean'] = score[['kor', 'eng', 'math']].mean(axis=1)
괄호를 잘못 쓰는 경우

예를 들어 BMI:

Python
실행됨
df['weight'] / (df['height'] / 100) ** 2

Python 연산 우선순위상 동작할 수 있어도, 실기에서는 의미를 명확하게 쓰는 게 좋아.

Python
실행됨
df['bmi'] = df['weight'] / ((df['height'] / 100) ** 2)

복잡한 파생식에서는 괄호를 충분히 쓰는 편이 안전해.

생성만 하고 검증하지 않는 경우
Python
실행됨
df['new'] = ...

만 하고 끝내지 말고 최소한:

Python
실행됨
df[['원본변수1', '원본변수2', 'new']].head()

정도는 확인하는 습관을 들이자.

🧠 8. 실기에서 읽어야 하는 문장 패턴

문제를 보면 먼저 자연어를 pandas 연산으로 번역해야 해.

문제 표현	떠올릴 코드
두 변수의 합	df['A'] + df['B']
두 변수의 차	df['A'] - df['B']
두 변수의 곱	df['A'] * df['B']
비율	df['A'] / df['B']
여러 변수의 합	.sum(axis=1)
여러 변수의 평균	.mean(axis=1)
조건에 따른 값	np.where()
새 변수 저장	df['새변수'] = ...
결과 확인	df.head() 또는 열 선택

시험에서는 이 한국어 → 코드 변환이 빨라져야 해.

🧭 9. 파생변수 문제를 풀 때의 고정 절차

문제를 만나면 다음 세 단계로 처리하면 돼.

기존 변수를 찾는다

예:

price
quantity
변수 사이의 관계를 코드로 만든다
Python
실행됨
df['total_price'] = df['price'] * df['quantity']
원본과 결과를 같이 검증한다
Python
실행됨
df[['price', 'quantity', 'total_price']].head()

그래서 실전용으로 압축하면:

① 무엇을 이용하지?
      ↓
② 어떻게 계산하지?
      ↓
③ 새 열에 어떻게 넣지?
      ↓
④ 결과가 맞나?

이 네 질문이면 대부분의 기본 파생변수 문제가 풀려.

📌 10. 이 단원에서 꼭 가져갈 코드
Python
실행됨
# 두 변수 계산
df['new'] = df['A'] + df['B']
df['new'] = df['A'] - df['B']
df['new'] = df['A'] * df['B']
df['new'] = df['A'] / df['B']

# 여러 열의 행별 합
df['total'] = df[['A', 'B', 'C']].sum(axis=1)

# 여러 열의 행별 평균
df['mean'] = df[['A', 'B', 'C']].mean(axis=1)

# 조건에 따른 파생변수
df['group'] = np.where(df['A'] >= 기준값, 'yes', 'no')

# 결과 확인
df.head()
df[['A', 'B', 'new']].head()

# 자료형 확인
df.dtypes

문법을 하나하나 외우기보다 가장 중요한 공통 틀을 기억해.

Python
실행됨
df['새로운_변수'] = 기존_변수를_이용한_계산

이게 파생변수 생성의 중심 문법이야.

🧩 이번 단원의 구조를 한 장으로 묶으면
[기존 데이터]
 A      B      C
 │      │      │
 └──┬───┘      │
    │          │
    ▼          │
 산술/비율/요약 │
    │          │
    └────┬─────┘
         ▼
     [파생변수 D]
         │
         ▼
  값·자료형·이상값 확인

파생변수 생성은 단순히 “새 열 추가”가 아니야.

기존 데이터가 가진 관계를 더 분석하기 좋은 형태로 표현하는 작업이라고 이해하면 이후 변수 선택, 모델링 단계까지 자연스럽게 연결돼.

첫 학습부터 현재 학습 상태는 저장이라고 입력하면 저장할 수 있어. 저장 패킷을 다시 붙여 넣으면 이어서 복원돼.
또 .cc를 붙이면 같은 학습 내용을 HTML 기반 학습 화면으로 볼 수 있어.

╭─ 📚 파생변수 생성 · 학습 대시보드
🎯 주제 · 2-2-3-1. 파생변수 생성
🧠 학습 상태 · 핵심 개념과 pandas 구현 연결 완료
➡️ 다음 방향 · 파생변수 생성 코드를 직접 읽고 구현하기

[파생변수 생성 · 다음 학습]
a. 🧪 파생변수 생성 실전 유형 익히기
b. 🔬 axis=0과 axis=1 더 깊게 이해하기
c. 🔗 파생변수와 변수 선택의 관계 보기
d. 🚀 np.where, cut, apply까지 확장하기
╰─

[2026.08.26 (Wed) 18:21:00]
