📏 [숫자의 체급을 맞추는 기술] 2-2-2-1. 표준화와 정규화

#빅데이터분석기사 #실기 #데이터변환 #표준화 #정규화 #StandardScaler #MinMaxScaler

🎯 먼저 잡을 핵심: 왜 범위를 바꾸는가?

데이터에는 단위가 서로 다른 변수가 자주 섞여 있어.

변수	값의 예
나이	20~60
연봉	30,000,000~150,000,000
구매횟수	0~30

이 상태에서 거리(distance)를 계산하면 연봉처럼 숫자가 큰 변수가 결과를 거의 지배할 수 있어.

예를 들어 나이가 1 차이 나는 것과 연봉이 1원 차이 나는 것을 숫자만 놓고 계산하면, 두 변수의 단위가 완전히 다르지. 그래서 모델이 변수들을 비교하기 전에 스케일(scale)을 비슷한 수준으로 변환하는 거야.

이때 대표적인 두 방법이:

표준화(Standardization) → 평균과 표준편차를 기준으로 변환

정규화(Normalization / Min-Max Scaling) → 최솟값과 최댓값을 기준으로 일정 범위로 변환

시험에서는 이 둘의 공식 → 코드 → 변환 결과 차이를 묶어서 이해하면 돼.

📐 표준화 적용: 평균을 0으로 옮긴다
표준화의 생각

표준화는 이렇게 묻는 변환이야.

“이 값이 평균으로부터 표준편차 몇 개만큼 떨어져 있지?”

그래서 원래 값 자체보다 평균에서 떨어진 상대적 위치를 표현해.

z=
σ
x−μ
	​

z=
1
(1.2)−(0)
	​

=1.2
Φ(z)≈88.5%
x
x
μ
μ
σ
σ
μ
x
Φ(z)
피드백 보내기

여기서

x: 원래 값

μ: 평균

σ: 표준편차

z: 표준화된 값

이야.

표준화 후 해석

대략 이렇게 읽으면 돼.

표준화 값	의미
0	평균과 같은 위치
1	평균보다 표준편차 1만큼 큼
-1	평균보다 표준편차 1만큼 작음
2	평균보다 상당히 큰 값

중요한 건 표준화했다고 값이 반드시 -1~1 사이에 들어가는 게 아니라는 것이야.

표준화 후에는 보통

평균 ≈ 0

표준편차 ≈ 1

이 되지만, 최솟값과 최댓값에는 제한이 없어.

그리고 하나 더.

표준화는 데이터를 정규분포로 만드는 과정이 아니야.

이름 때문에 자주 헷갈리는데, 원래 분포의 형태를 마법처럼 정규분포로 바꾸는 게 아니라 중심과 스케일을 변환하는 거야.

💻 StandardScaler로 표준화

실기에서는 sklearn.preprocessing.StandardScaler가 핵심이야.

Python
실행됨
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()

df[['x1_std', 'x2_std']] = scaler.fit_transform(
    df[['x1', 'x2']]
)

흐름을 뜯어보면:

원본 데이터
   ↓
StandardScaler()
   ↓
fit()       평균과 표준편차 계산
   ↓
transform() 계산된 기준으로 데이터 변환

fit_transform()은 두 작업을 한 번에 하는 거야.

Python
실행됨
scaler.fit_transform(X)

즉,

Python
실행됨
scaler.fit(X)
X_scaled = scaler.transform(X)

와 같은 흐름이지.

한 열만 변환할 때
Python
실행됨
df[['age_std']] = scaler.fit_transform(df[['age']])

여기서 [['age']]처럼 2차원 형태로 넣는 습관을 가지는 게 좋아.

Python
실행됨
df['age']

는 Series라서 sklearn 변환기에 바로 넣을 때 형태 문제가 생길 수 있어.

📏 정규화 적용: 최솟값을 0, 최댓값을 1로

빅데이터분석기사 실기에서 말하는 정규화는 보통 Min-Max Scaling을 가리켜.

원리는 아주 직관적이야.

가장 작은 값 → 0

가장 큰 값 → 1

나머지 값 → 그 사이의 상대적 위치

공식은

x
′
=
x
max
	​

−x
min
	​

x−x
min
	​

	​


이야.

값을 따라가 보자

원래 값이

10, 20, 30, 40, 50

이라면 최소값은 10, 최대값은 50이야.

30을 변환하면

50−10
30−10
	​

=
40
20
	​

=0.5

따라서 전체는 이렇게 돼.

원본	Min-Max 변환
10	0.00
20	0.25
30	0.50
40	0.75
50	1.00

원래 숫자가 얼마였든 현재 학습 데이터의 최소와 최대를 기준으로 0~1 범위에 배치하는 거야.

💻 MinMaxScaler로 정규화
Python
실행됨
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()

df[['x1_norm', 'x2_norm']] = scaler.fit_transform(
    df[['x1', 'x2']]
)

기본 범위는

0 ≤ x ≤ 1

이야.

다른 범위를 지정하는 것도 가능해.

Python
실행됨
scaler = MinMaxScaler(feature_range=(-1, 1))

그러면 최소값이 -1, 최대값이 1이 되도록 변환돼.

하지만 시험에서 별도 조건이 없다면 보통 기본적인 0~1 변환을 먼저 떠올리면 돼.

🔬 변환 결과 비교: 같은 데이터를 두 방식으로 보면

원본 데이터를 다음처럼 두자.

10, 20, 30, 40, 50

평균은 30이야.

표준화와 Min-Max 정규화를 나란히 보면 차이가 선명해져.

원본	표준화	Min-Max 정규화
10	약 -1.414	0.00
20	약 -0.707	0.25
30	0.000	0.50
40	약 0.707	0.75
50	약 1.414	1.00

여기서 봐야 할 건 숫자를 외우는 게 아니야.

표준화가 보존하는 관점

표준화에서는 30이 평균이니까

30 → 0

이 돼.

그리고 평균보다 작은 값은 음수, 큰 값은 양수가 돼.

즉 중심 질문은:

평균에서 얼마나 떨어져 있는가?

야.

정규화가 보존하는 관점

Min-Max에서는

10 → 0
50 → 1
30 → 0.5

가 돼.

중심 질문은:

최솟값과 최댓값 사이에서 어느 위치에 있는가?

야.

이 차이를 이해하면 두 공식을 억지로 외울 필요가 거의 없어.

⚖️ 표준화 vs 정규화

시험용으로는 이 표가 핵심이야.

구분	표준화	Min-Max 정규화
영어	Standardization	Normalization / Min-Max Scaling
기준	평균, 표준편차	최솟값, 최댓값
중심	평균 → 0	최소 → 0
스케일	표준편차 → 1	기본적으로 0~1
값 범위	제한 없음	기본적으로 0~1
음수 발생	가능	기본 설정에서는 없음
이상치 영향	있음	특히 큼
sklearn	StandardScaler	MinMaxScaler

한 문장으로 압축하면:

표준화는 평균을 중심으로 거리의 척도를 맞추고, 정규화는 최솟값과 최댓값 사이의 위치로 값을 다시 표현한다.

🚨 이상치가 있으면 어떻게 달라질까?

여기가 실전에서 중요한 차이야.

원래 데이터가

10, 20, 30, 40, 1000

이라고 해보자.

1000이라는 극단적인 값이 하나 들어왔어.

Min-Max 정규화에서는 1000이 최대값이 되어 버려.

그러면

10  → 0
20  → 약 0.01
30  → 약 0.02
40  → 약 0.03
1000 → 1

처럼 일반적인 값들이 0 근처에 몰릴 수 있어.

그래서 Min-Max Scaling은 이상치에 특히 민감해.

표준화도 평균과 표준편차가 이상치의 영향을 받기 때문에 완전히 안전하지는 않아. 다만 Min-Max처럼 극단값 하나가 곧바로 전체 범위의 끝점이 되는 구조와는 차이가 있어.

이상치에 강한 별도의 방법으로 RobustScaler도 있지만, 지금 단원의 중심은 StandardScaler와 MinMaxScaler니까 일단 둘을 확실히 구분하는 게 우선이야.

🧠 어떤 모델에서 스케일링이 중요한가?

변수의 크기 차이를 실제 계산에 사용하는 알고리즘들은 스케일에 영향을 많이 받아.

대표적으로:

KNN

K-Means

SVM

로지스틱 회귀

선형 회귀의 일부 최적화 상황

PCA

신경망

등이 있어.

특히 거리 기반 알고리즘을 생각하면 이유가 바로 보여.

나이 차이       = 10
연봉 차이       = 30,000,000

그대로 유클리드 거리를 계산하면 사실상 연봉이 거리를 결정해버리지.

반면 의사결정나무 계열은

x < 37.5 ?

처럼 임계값을 기준으로 분할하므로 일반적으로 스케일링의 필요성이 훨씬 낮아.

즉,

숫자의 절대적 크기를 이용해 거리·내적·최적화를 수행하는 모델일수록 스케일링을 의식한다.

라고 이해하면 좋아.

🧪 실기에서 특히 중요한 fit과 transform

여기에서 한 단계 올라가자.

머신러닝 데이터를

Python
실행됨
X_train
X_test

로 나눴다면 scaler의 기준은 훈련 데이터에서만 학습해야 해.

올바른 흐름은:

Python
실행됨
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

핵심은 이거야.

Python
실행됨
X_train → fit_transform
X_test  → transform

테스트 데이터에 다시

Python
실행됨
scaler.fit_transform(X_test)

를 하면 안 돼.

왜냐하면 테스트 데이터의 평균·표준편차 정보를 모델링 과정에 사용하게 되기 때문이야. 이를 데이터 누수(Data Leakage)라고 봐.

MinMaxScaler도 똑같아.

Python
실행됨
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()

X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

즉 scaler가 달라져도 원칙은 그대로야.

학습용 데이터로 기준을 만들고, 그 기준을 검증·테스트 데이터에 적용한다.

🧩 실기 코드 패턴을 한 번에 정리
표준화
Python
실행됨
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
정규화
Python
실행됨
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)

둘의 코드 구조는 거의 동일해.

StandardScaler()
      ↕
MinMaxScaler()

만 바뀌는 셈이지.

그래서 시험에서는 라이브러리 이름보다 각 scaler가 어떤 통계량을 사용하는지를 정확히 연결해야 해.

StandardScaler
→ 평균 + 표준편차

MinMaxScaler
→ 최솟값 + 최댓값

이 짝을 고정해 두자.

🧭 헷갈리는 지점을 분리해 두자
“표준화하면 0~1이다?”

아니야.

StandardScaler → 평균 0, 표준편차 1
MinMaxScaler   → 기본 범위 0~1

이 둘을 뒤집는 실수가 가장 흔해.

“표준화하면 정규분포가 된다?”

아니야.

표준화는 평균과 표준편차를 이용해 값의 위치와 척도를 재표현할 뿐이야.

“MinMaxScaler를 사용하면 항상 새 데이터도 0~1인가?”

주의해야 해.

훈련 데이터의 최소·최대를 기준으로 transform()하기 때문에, 새 데이터가 훈련 데이터에서 보았던 최대값보다 더 크면 결과가 1보다 커질 수도 있어.

즉 0~1이라는 말은 fit에 사용된 데이터 범위를 기준으로 한 기본적인 성질이라고 이해하는 게 정확해.

“모든 모델에 스케일링을 해야 하나?”

아니야.

모델의 계산 구조에 따라 중요도가 달라.

특히 거리 기반 모델과 경사하강 기반 모델에서는 중요하고, 트리 계열에서는 일반적으로 덜 중요해.

🏁 이번 단원의 시험용 압축

머릿속에 아래 연결만 남아도 좋아.

데이터 범위 변환
│
├─ 표준화 Standardization
│    ├─ 평균 = 0
│    ├─ 표준편차 = 1
│    ├─ 값의 범위 제한 없음
│    └─ StandardScaler
│
└─ 정규화 Min-Max Scaling
     ├─ 최소 = 0
     ├─ 최대 = 1
     ├─ 기본 범위 = 0~1
     └─ MinMaxScaler

그리고 머신러닝 데이터가 train/test로 나뉘었다면:

TRAIN → fit + transform
TEST  → transform만

이 원칙까지 붙이면 돼.

이제 “표준화와 정규화가 무엇인가?” 수준을 넘어서, 실제 실기 코드에서 어떤 scaler를 골라야 하고 결과를 어떻게 해석해야 하는지까지 연결된 상태야.

참고로 이번 학습 상태는 정확히 저장이라고 입력하면 저장할 수 있어.

╭─ 빅데이터분석기사 실기 · 학습 대시보드
📍 현재 주제 · 2-2-2-1. 표준화와 정규화
🧠 학습 상태 · 개념 → sklearn 코드 → 결과 비교 연결
➡️ 다음 방향 · 스케일링의 실전 적용과 데이터 누수 구분

[표준화와 정규화 · 다음 학습]

a. 🧪 StandardScaler·MinMaxScaler 실기 코드 패턴 완성하기
b. 🔍 이상치가 두 변환 결과에 미치는 영향 더 깊게 보기
c. 🤖 KNN·SVM·PCA에서 스케일링이 필요한 이유 연결하기
d. 🛡️ RobustScaler까지 확장해서 세 가지 방법 비교하기
╰─

KST [2026.08.26 (수) 18:17:00]
