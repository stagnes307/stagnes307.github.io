🧩 [모형이 먹을 수 있는 데이터 만들기] 3-2-2-1. 학습 가능한 데이터 구성

#빅데이터분석기사 #실기 #분석모형구축 #모형용데이터조작 #학습데이터검증

이번 단원의 핵심은 단순해. 전처리가 끝난 데이터를 “모형이 실제로 학습할 수 있는 형태”로 바꾸고, 그 데이터가 제대로 만들어졌는지 검증하는 것이야.

흐름은 세 단계로 잡으면 돼.

모형 입력 형태 확인 → 데이터 조작 → 학습 데이터 검증

이 순서를 이해하면 X, y, train_test_split, 범주형 변수 처리, 결측치 확인 같은 코드가 왜 등장하는지 한 덩어리로 연결돼.

🎯 1. 먼저 구분해야 할 것: 데이터가 있다고 바로 학습되는 건 아니야

예를 들어 이런 데이터가 있다고 해보자.

나이	소득	직업	구매여부
31	4200	사무직	1
45	6500	전문직	0
27	3800	사무직	1

사람에게는 별문제 없는 표야. 하지만 모델 입장에서는 세 가지를 확인해야 해.

무엇을 이용해 무엇을 예측할까?

구매여부를 예측한다면,

독립변수 / 설명변수 / 특징(feature): 나이, 소득, 직업

종속변수 / 목표변수 / 타깃(target): 구매여부

따라서 개념적으로 데이터를 이렇게 나눠.

Python
실행됨
X = df.drop(columns='구매여부')
y = df['구매여부']

여기서 중요한 시험 포인트가 하나 있어.

X는 모델이 정답을 맞히는 데 사용할 정보이고, y는 모델이 맞혀야 할 정답이다.

타깃 변수가 X 안에 들어가면 정답을 미리 알려주는 꼴이 돼. 이건 데이터 누수(data leakage)의 대표적인 형태야.

🔍 2. 모형 입력 형태 확인

모델마다 받아들일 수 있는 데이터 구조가 달라.

가장 먼저 보는 건 차원(shape), 자료형(dtype), 결측값, 범주형 변수야.

차원부터 보자
Python
실행됨
X.shape
y.shape

예를 들어 결과가

X.shape → (1000, 10)
y.shape → (1000,)

라면,

관측치: 1,000개

입력 변수: 10개

타깃: 1,000개

라는 뜻이야.

특히 머신러닝에서 X는 일반적으로 2차원, y는 1차원 형태가 많이 사용돼.

자료형도 중요해
Python
실행됨
X.dtypes

예를 들어 이런 결과가 나올 수 있어.

age        int64
income     float64
job        object

job이 문자열이라면 많은 머신러닝 모델에 그대로 넣을 수 없어.

그래서 범주형 값을 숫자로 표현하는 과정이 필요해.

Python
실행됨
X = pd.get_dummies(X, columns=['job'])

그러면

job_사무직
job_전문직
job_학생

같은 새로운 변수가 만들어질 수 있어.

이게 원-핫 인코딩(one-hot encoding)이야.

결측값도 확인해야 해
Python
실행됨
X.isnull().sum()

결측값이 남아 있으면 사용하는 모델에 따라 학습 자체가 실패하거나 결과가 왜곡될 수 있어.

여기서 사고 순서를 기억해.

데이터 존재 → 입력 구조 확인 → 자료형 확인 → 결측 여부 확인 → 모델이 처리 가능한 형태인지 확인

🛠️ 3. 데이터 조작

입력 형태를 확인했다면 이제 실제 학습에 맞게 데이터를 바꿔.

빅데이터분석기사 실기에서 특히 자주 연결되는 조작은 다음과 같아.

특징과 타깃 분리
Python
실행됨
X = df.drop('target', axis=1)
y = df['target']

axis=1은 열을 제거한다는 뜻이야.

범주형 변수 변환
Python
실행됨
X = pd.get_dummies(X)

간단한 실기 문제에서는 상당히 편리해.

다만 학습 데이터와 평가 데이터를 따로 변환할 때는 두 데이터에서 생성되는 열이 달라질 가능성도 생각해야 해.

예를 들어 학습 데이터에는

서울, 부산, 대구

가 있는데 평가 데이터에는

서울, 부산

만 있다면 각각 따로 get_dummies()를 했을 때 열 구조가 달라질 수 있어.

모델은 학습할 때와 예측할 때 동일한 특징 구조를 요구해.

이게 바로 단순 암기보다 중요한 원리야.

모델에 들어가는 학습 데이터와 예측 데이터의 열 구조가 일치해야 한다.

✂️ 4. 학습용과 검증용 데이터를 나눈다

하나의 데이터를 전부 학습에 써버리면 문제가 생겨.

왜냐하면 우리가 알고 싶은 건

모델이 처음 보는 데이터에서도 잘 작동하는가?

이기 때문이야.

그래서 데이터를 보통 분리해.

Python
실행됨
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

구조를 눈으로 보면 이렇다.

전체 데이터
   │
   ├── X : 입력 변수
   │
   └── y : 타깃
        │
        ▼
train_test_split
        │
        ├── X_train ── 모델 학습 입력
        ├── y_train ── 모델 학습 정답
        │
        ├── X_test  ── 모델 평가 입력
        └── y_test  ── 모델 평가 정답

test_size=0.2라면 전체 데이터 중 약 20%를 테스트 데이터로 사용하는 거야.

random_state는 왜 넣을까?

데이터를 무작위로 나누기 때문에 실행할 때마다 결과가 달라질 수 있어.

Python
실행됨
random_state=42

처럼 고정하면 같은 방식으로 분할된 결과를 재현할 수 있어.

숫자 42 자체에 특별한 통계적 의미가 있는 건 아니야.

⚖️ 5. 분류에서는 stratify가 중요할 수 있다

예를 들어 타깃 비율이

정상 95%
이상  5%

라고 해보자.

무작위로 그냥 나누면 학습·검증 데이터의 클래스 비율이 상당히 달라질 수도 있어.

이때 사용할 수 있는 게 stratify야.

Python
실행됨
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

stratify=y는 타깃 클래스의 비율을 고려해 데이터를 분할하도록 하는 거야.

따라서 이건 특히 분류 문제와 연결해서 기억하면 좋아.

🧪 6. 학습 데이터 검증

여기까지 왔다고 바로 모델을 학습시키면 안 돼.

조작 과정에서 문제가 생기지 않았는지 마지막으로 확인해.

X와 y의 행 수가 맞는가?
Python
실행됨
X_train.shape
y_train.shape

예를 들어

X_train : (800, 12)
y_train : (800,)

라면 행의 수 800이 일치해야 해.

결측값이 남아 있는가?
Python
실행됨
X_train.isnull().sum()

또는 전체 개수를 빠르게 확인하려면

Python
실행됨
X_train.isnull().sum().sum()

결과가 0이면 결측값이 없다는 뜻이야.

자료형은 학습 가능한가?
Python
실행됨
X_train.dtypes

의도하지 않은 object형 문자열 변수가 남아 있지는 않은지 확인해.

범주형 변환 결과가 맞는가?
Python
실행됨
X_train.columns

원-핫 인코딩이나 변수 제거 후 예상한 열이 만들어졌는지 확인할 수 있어.

분류라면 클래스 분포도 확인한다
Python
실행됨
y_train.value_counts()

비율까지 보고 싶으면

Python
실행됨
y_train.value_counts(normalize=True)

를 사용할 수 있어.

⚠️ 7. 실기에서 특히 조심해야 하는 함정: 데이터 누수

여기부터가 단순 코딩과 분석 절차 이해를 가르는 부분이야.

전체 데이터에 어떤 변환을 먼저 적용하고 그 뒤에 train/test를 분리했다고 해보자.

예를 들어 평균과 표준편차를 이용해 데이터를 표준화한다면, 테스트 데이터의 정보까지 변환 과정에 들어갈 수 있어.

좋은 원칙은 이거야.

전체 데이터
      ↓
train / test 분리
      ↓
train에서 변환 규칙 학습
      ↓
train 변환
      ↓
같은 규칙으로 test 변환

예를 들어 StandardScaler라면,

Python
실행됨
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()

X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

야.

차이에 주목해.

훈련 데이터 → fit_transform()
테스트 데이터 → transform()

fit은 변환에 필요한 규칙을 학습하는 과정이기 때문이야.

테스트 데이터에는 fit()을 하지 않는다는 게 핵심이야.

🧠 8. fit, transform, fit_transform의 관계

이 세 개가 헷갈리면 전처리 코드를 외우게 돼. 관계로 이해하면 쉬워.

fit
Python
실행됨
scaler.fit(X_train)

훈련 데이터에서 변환에 필요한 기준을 알아낸다.

표준화라면 평균과 표준편차 같은 정보를 구하는 과정이야.

transform
Python
실행됨
scaler.transform(X_train)

앞서 얻은 기준으로 실제 데이터를 변환한다.

fit_transform
Python
실행됨
scaler.fit_transform(X_train)

fit과 transform을 연달아 수행하는 거야.

그래서 전형적인 패턴은 이렇게 돼.

Python
실행됨
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

시험장에서 이 코드를 보자마자 이렇게 읽으면 돼.

훈련 데이터에서 기준을 만들고, 그 기준을 테스트 데이터에 그대로 적용한다.

🔗 9. 전체 코드를 하나의 흐름으로 연결해보자

예를 들어 target을 예측하는 문제라면 기본적인 학습 데이터 구성은 이런 구조를 가질 수 있어.

Python
실행됨
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# 1. 특징과 타깃 분리
X = df.drop(columns='target')
y = df['target']

# 2. 범주형 변수 변환
X = pd.get_dummies(X)

# 3. 학습/검증 데이터 분리
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# 4. 스케일링
scaler = StandardScaler()

X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

이걸 코드가 아니라 의미로 읽으면 이렇게 돼.

예측에 사용할 변수와
예측할 변수를 구분한다
        ↓
모델이 처리할 수 없는 자료형을 바꾼다
        ↓
학습할 데이터와 평가할 데이터를 분리한다
        ↓
훈련 데이터로 변환 기준을 학습한다
        ↓
동일한 기준으로 평가 데이터도 변환한다
        ↓
모델 학습 가능 여부를 최종 확인한다

이 흐름이 학습 가능한 데이터 구성의 뼈대야.

📌 10. 시험장에서 바로 꺼내야 할 구분
상황	확인할 것
모델 입력 변수 만들기	X와 y 분리
문자열 범주형 데이터 존재	인코딩 필요 여부 확인
데이터 크기 확인	.shape
자료형 확인	.dtypes
결측값 확인	.isnull().sum()
학습/검증 분리	train_test_split()
분류 비율 유지	stratify=y
분할 재현	random_state
변환 기준 학습	fit()
실제 변환	transform()
훈련 데이터 변환	fit_transform() 가능
테스트 데이터 변환	transform()
클래스 분포 확인	value_counts()

여기서 가장 중요한 한 줄은 이거야.

학습 데이터에는 fit할 수 있지만, 검증·테스트 데이터는 학습 과정에 참여시키지 않는다.

🧭 11. 이번 단원의 개념 구조

이 단원에서 실제로 연결되어야 하는 개념은 세 묶음이야.

입력 적합성

shape → dtype → 결측값 → 범주형 변수

즉, 모델이 데이터를 받아들일 수 있는지 본다.

학습 구조

X/y 분리 → train/test 분리 → 필요한 변환

즉, 어떤 정보를 가지고 무엇을 학습시킬지 구성한다.

검증 가능성

열 구조 일치 → 행 수 확인 → 결측 확인 → 분포 확인 → 누수 방지

즉, 만들어진 데이터가 정말 공정하게 모델 학습과 평가에 사용될 수 있는지 확인한다.

따라서 3-2-2-1. 학습 가능한 데이터 구성을 한 문장으로 압축하면,

모델 입력 조건에 맞게 특징과 타깃을 구성하고, 데이터를 적절히 변환·분할한 뒤, 형태·결측·분포·누수 여부를 점검하는 과정

이라고 정리할 수 있어.

🧱 학습 경로

이번 주제는 다음처럼 깊게 들어가면 실기 대응력이 좋아져.

3-2. 분석모형 구축하기
└─ 3-2-2. 모형용 데이터 조작
   └─ 3-2-2-1. 학습 가능한 데이터 구성
      ├─ 3-2-2-1-1. 모형 입력 형태 확인
      │  ├─ X와 y
      │  ├─ shape와 차원
      │  ├─ dtype
      │  └─ 결측·범주형 변수
      ├─ 3-2-2-1-2. 데이터 조작
      │  ├─ 변수 선택·제거
      │  ├─ 인코딩
      │  ├─ train/test 분할
      │  ├─ stratify
      │  └─ scaling과 fit/transform
      └─ 3-2-2-1-3. 학습 데이터 검증
         ├─ 입력·타깃 정합성
         ├─ 결측·자료형 검사
         ├─ 데이터 분포 검사
         └─ 데이터 누수 방지

다음 학습에서는 train_test_split → 인코딩/스케일링 → fit/transform → 누수 방지를 실제 실기 코드 판단 문제로 연결하는 것이 가장 효율적이야.

그리고 이번 학습 상태는 이후 정확히 이어서 공부할 수 있게 **저장**이라고 입력하면 저장할 수 있어.

╭─ 🧭 빅데이터분석기사 실기 학습 대시보드
📍 현재 단원 · 3-2-2-1. 학습 가능한 데이터 구성
🧠 학습 상태 · 핵심 구조 학습 완료, 코드 적용 단계
➡️ 주 경로 · 3-2-2-1-1. 모형 입력 형태 확인

[학습 가능한 데이터 구성 · 다음 학습]
a. 🎯 3-2-2-1-1. 모형 입력 형태 확인
b. 🔬 fit / transform / fit_transform과 데이터 누수 깊게 보기
c. 🔗 원-핫 인코딩과 학습·평가 데이터 열 불일치 연결하기
d. 🧪 실기 코드 전체 흐름을 하나의 예제로 추적하기

[교육과정 · 탐색]
e. 🗺️ 3-2-2-1 전체 학습지도 보기
f. 🛠️ 이 단원의 학습 경로 다시 설계하기
╰─

KST [2026.08.26 (Wed) 18:31:00]
