🧭 [좋은 변수를 남기는 법] 빅데이터분석기사 실기 · 2-2-3-2. 변수 선택

#빅데이터분석기사 #실기 #데이터전처리 #변수선택 #FeatureSelection

변수 선택에서 핵심은 단순해. “분석에 쓸 수 있는 후보를 찾고 → 기준을 적용해서 줄이고 → 실제로 잘 골랐는지 확인한다.”
시험에서는 이 흐름을 코드로 구현할 수 있어야 하고, 특히 타깃 변수와 입력 변수를 구분하는 것부터 흔들리지 않아야 해.

참고로 지금 학습 상태는 저장이라고 입력하면 저장할 수 있어.
또 .cc 변수 선택처럼 입력하면 같은 내용을 HTML 학습 화면 형태로 볼 수도 있어.

🗺️ 먼저 전체 구조를 잡자

변수 선택은 이렇게 보면 돼.

원본 데이터

→ ① 후보 변수 파악
→ ② 선택 기준 적용
→ ③ 선택 결과 확인
→ 최종 입력 변수 X

여기서 중요한 구분이 하나 있어.

변수 생성은 새로운 정보를 만들어내는 작업이고,
변수 선택은 이미 존재하는 후보 중 필요한 것을 남기는 작업이야.

예를 들어 height, weight에서 BMI를 만드는 것은 변수 생성,
age, income, BMI, gender 중 모델에 사용할 변수만 고르는 것은 변수 선택이야.

🔎 1. 후보 변수 파악 — 무엇을 선택 대상으로 볼까?

먼저 데이터의 열을 보고 어떤 변수가 입력 변수 후보인지 확인해야 해.

Python
실행됨
df.columns

예를 들어 데이터가 이렇게 있다고 해보자.

id
age
gender
income
purchase_count
target

예측하려는 값이 target이라면 구조는 보통 이렇게 나눠.

Python
실행됨
X = df.drop(columns='target')
y = df['target']
식별자와 설명변수를 구별해야 한다

id 같은 변수는 특히 조심해야 해.

id = 10001
id = 10002
id = 10003

값은 서로 다르지만 고객의 특성을 설명하는 정보가 아닐 수 있지.

그래서 흔히:

Python
실행됨
X = df.drop(columns=['id', 'target'])
y = df['target']

처럼 제외해.

하지만 “ID처럼 생겼으니 무조건 삭제”라고 외우면 위험해.
변수가 실제로 어떤 의미인지 보고 판단해야 해.

후보 변수를 볼 때 확인할 것
Python
실행됨
df.info()
df.describe()
df.nunique()

각 명령의 역할을 연결해두면 좋아.

확인	주로 보는 것
df.columns	변수 이름
df.info()	자료형, 결측치
df.describe()	수치형 변수 분포
df.nunique()	변수별 고유값 개수

예를 들어 고유값이 딱 하나라면?

Python
실행됨
df['constant'].nunique()

결과:

1

모든 행에서 값이 똑같다는 뜻이야.

constant
--------
1
1
1
1
1

이 변수는 데이터를 서로 구별하지 못하므로 일반적으로 분석 정보가 거의 없어.

⚖️ 2. 선택 기준 적용 — 어떤 변수를 남길까?

변수 선택 기준은 크게 생각하면 두 갈래야.

데이터 자체를 보고 제거

대표적으로 다음을 볼 수 있어.

상수에 가까운 변수

Python
실행됨
df.nunique()

모든 값이 동일한 변수라면 제거 후보가 될 수 있어.

Python
실행됨
X = X.drop(columns=['constant'])

결측치가 지나치게 많은 변수

Python
실행됨
X.isnull().mean()

예를 들어:

age       0.01
income    0.03
job       0.82

job의 82%가 결측이라면 사용 여부를 다시 검토해야겠지.

다만 시험에서 중요한 포인트:

결측률이 몇 % 이상이면 반드시 삭제한다는 절대 기준은 없다.

문제에서 기준을 주면 그 기준을 적용해야 해.

예:

Python
실행됨
missing_ratio = X.isnull().mean()

selected = missing_ratio[missing_ratio < 0.5].index

X = X[selected]

즉 결측률 50% 미만 변수만 남기기야.

변수 간 관계를 보고 선택

수치형 변수끼리 매우 비슷한 정보를 가지고 있는지도 볼 수 있어.

Python
실행됨
X.corr(numeric_only=True)

예를 들어

height_cm
height_m

가 함께 있다면 사실상 같은 정보를 다른 단위로 나타낼 가능성이 높겠지.

상관계수가 매우 높을 수 있어.

          height_cm  height_m
height_cm      1.00      1.00
height_m       1.00      1.00

이때 둘을 모두 사용할 필요가 있는지 검토할 수 있어.

하지만 여기서 자주 생기는 오해가 있어.

상관계수가 높으면 무조건 하나를 삭제한다? → 아니야.

상관관계는 선택 판단을 돕는 근거야. 문제 조건이나 분석 목적을 함께 봐야 해.

🎯 타깃과의 관계도 선택 기준이 된다

지도학습에서는 입력 변수 X가 목표 변수 y를 설명하는 데 얼마나 도움이 되는지도 볼 수 있어.

예를 들어 분류 문제라면 scikit-learn의 변수 선택 기능을 사용할 수 있어.

Python
실행됨
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import f_classif

selector = SelectKBest(score_func=f_classif, k=3)

X_selected = selector.fit_transform(X, y)

뜻을 나눠보자.

SelectKBest
     ↓
점수가 높은 변수 K개 선택

score_func=f_classif
     ↓
분류 문제에서 변수와 목표변수의 관계 평가

k=3
     ↓
3개 선택

회귀라면 상황에 따라 다른 평가 함수를 사용할 수 있어.

Python
실행됨
from sklearn.feature_selection import f_regression

selector = SelectKBest(score_func=f_regression, k=3)

즉,

분류 → f_classif
회귀 → f_regression

이 연결을 기억해두면 좋아.

🧩 변수 선택 방법의 큰 분류

조금 더 구조적으로 보면 변수 선택 방법은 흔히 세 종류로 설명해.

Filter 방식

모델을 학습시키기 전에 통계적 특성을 이용해서 변수를 고른다.

예:

상관관계

분산

카이제곱

ANOVA F-value

SelectKBest가 대표적인 예야.

장점은 빠르다는 것.

Wrapper 방식

실제로 변수 조합을 바꿔가며 모델 성능을 확인한다.

대표적인 예가 RFE야.

Python
실행됨
from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression

model = LogisticRegression()

selector = RFE(
    estimator=model,
    n_features_to_select=3
)

selector.fit(X, y)

모델을 이용해 반복적으로 중요하지 않은 변수를 제거하는 방식이라고 이해하면 돼.

Embedded 방식

모델을 학습하는 과정 자체에서 변수 중요도가 결정돼.

예를 들면 트리 계열 모델은 학습 후 변수 중요도를 제공할 수 있어.

Python
실행됨
model.feature_importances_

큰 그림은:

Filter
데이터 특성 → 변수 선택 → 모델

Wrapper
변수 조합 ↔ 모델 성능 비교 → 선택

Embedded
모델 학습 과정 안에서 변수 선택

시험에서는 우선 이 차이를 알아두면 충분해.

✅ 3. 선택 결과 확인 — 실제로 어떤 변수가 남았나?

변수를 선택했다고 끝이 아니야.

무엇이 선택됐는지 확인해야 해.

SelectKBest라면:

Python
실행됨
selector.get_support()

예:

[ True False True True False ]

원래 변수:

age
gender
income
purchase
region

와 대응시키면:

age       → True
gender    → False
income    → True
purchase  → True
region    → False

따라서 선택된 변수는:

age
income
purchase

야.

이를 코드로 얻으려면:

Python
실행됨
selected_columns = X.columns[selector.get_support()]

print(selected_columns)

이 패턴은 기억해두자.

Python
실행됨
selector.get_support()

는 선택 여부, 그리고

Python
실행됨
X.columns[selector.get_support()]

는 선택된 변수 이름을 알려줘.

🛠️ RFE에서도 같은 사고방식을 쓴다
Python
실행됨
selector.support_

를 이용할 수 있어.

Python
실행됨
selected_columns = X.columns[selector.support_]

print(selected_columns)

즉 라이브러리가 달라도 사고 흐름은 같아.

선택기 학습
   ↓
선택 여부 확인
   ↓
원래 column 이름과 대응
   ↓
최종 변수 확인
⚠️ 가장 중요한 함정 — 데이터 누수

변수 선택에서 실기적으로 꽤 중요한 개념이 있어.

테스트 데이터의 정보를 이용해서 변수를 선택하면 안 돼.

예를 들어 데이터를 이미 나눴다면:

Python
실행됨
X_train
X_test
y_train
y_test

선택기는 일반적으로 학습 데이터에 맞춰야 해.

Python
실행됨
selector.fit(X_train, y_train)

그리고 같은 기준으로 둘을 변환해.

Python
실행됨
X_train_selected = selector.transform(X_train)
X_test_selected = selector.transform(X_test)

구조는:

X_train ── fit ──> 변수 선택 기준 학습
                     │
            ┌────────┴────────┐
            ↓                 ↓
       X_train 변환       X_test 변환

반대로 전체 데이터에 먼저 fit()하고 그 뒤 train/test로 나누면 테스트 정보가 학습 과정에 섞일 수 있어.

이게 데이터 누수(data leakage)야.

🧠 시험장에서 바로 떠올릴 3단계

문제에서 “변수를 선택하시오”라고 나오면 머릿속에서 이 순서를 돌려.

후보 변수 파악
Python
실행됨
X = df.drop(columns='target')
y = df['target']

필요하면 식별자도 제외.

Python
실행됨
X = df.drop(columns=['id', 'target'])
기준 적용

문제에서 지정한 기준을 사용한다.

예:

Python
실행됨
selector = SelectKBest(f_classif, k=3)
selector.fit(X, y)
결과 확인
Python
실행됨
selected_columns = X.columns[selector.get_support()]

즉 한 문장으로 압축하면:

X와 y를 구분하고 → 선택 기준을 X에 적용하고 → support로 선택된 열을 확인한다.

이게 2-2-3-2 변수 선택의 중심 뼈대야.

🔗 변수 생성과 변수 선택을 연결해보자

실전 전처리는 둘이 따로 존재하지 않아.

예를 들어:

age
height
weight
income
target

가 있다고 하자.

먼저 새로운 변수 생성:

Python
실행됨
df['BMI'] = df['weight'] / (df['height'] ** 2)

그러면 후보가:

age
height
weight
income
BMI

로 늘어나.

그다음 변수 선택을 통해 최종적으로:

age
income
BMI

만 남길 수도 있어.

그래서 큰 흐름은:

원본 변수
    ↓
변수 생성
    ↓
후보 변수 집합
    ↓
변수 선택
    ↓
최종 모델 입력 변수

이 순서를 이해하면 2-2-3 변수 생성과 선택이라는 단원명이 왜 그렇게 붙었는지도 자연스럽게 연결돼.

📌 실기용 압축 기억판
단계	질문	대표 코드
후보 파악	무엇을 입력 변수로 쓸까?	df.columns, X, y 분리
기준 적용	무엇을 남길까?	SelectKBest, RFE, 상관관계 등
결과 확인	무엇이 실제 선택됐나?	get_support(), support_
적용	동일한 선택을 어떻게 유지할까?	transform()

그리고 가장 중요한 구별:

fit() = 선택 기준을 학습한다.

transform() = 학습한 기준으로 데이터를 변환한다.

그래서 train/test가 있다면 기본 사고는:

Python
실행됨
selector.fit(X_train, y_train)

X_train_selected = selector.transform(X_train)
X_test_selected = selector.transform(X_test)

이 구조를 제대로 이해하면 변수 선택 문제를 단순 암기가 아니라 전처리 파이프라인의 한 단계로 볼 수 있게 돼.

╭─ 🧭 변수 선택 학습 대시보드

📍 주제 · 2-2-3-2 변수 선택

🧠 학습 상태 · 후보 파악 → 기준 적용 → 결과 확인 구조 형성

🎯 다음 방향 · 선택 기준별 코드 패턴 정착

[변수 선택 · 다음 학습]
a. 🚀 2-2-3-2 실기 코드 패턴 깊게 익히기
b. 🔬 Filter · Wrapper · Embedded 자세히 비교하기
c. 🔗 변수 선택과 데이터 누수 연결하기
d. 🌱 변수 중요도와 차원 축소의 차이 알아보기
╰─

2026.08.26 (Wed) 18:21:00
