🧪 [타입을 바꾸기 전에 의미부터 지켜라] 2-2-1-1. 자료형과 표현 변환

#빅데이터분석기사 #실기 #데이터변환 #pandas #자료형변환

🎯 이번 단원의 핵심

빅데이터분석기사 실기에서 자료형 변환은 단순히 astype()을 쓰는 문제가 아니야. 실제 흐름은 항상 이렇게 생각하면 된다.

현재 자료형 확인 → 데이터의 실제 표현 확인 → 목표 자료형으로 변환 → 변환 결과 검증

특히 object형 데이터를 보자마자 무조건 숫자로 바꾸면 위험해. "1,200", "미상", "2026-08-01", "00123"처럼 겉으로는 문자열이지만 서로 다른 의미를 가진 값들이 모두 object에 들어갈 수 있기 때문이야.

🔍 1. 현재 유형 확인 — 지금 데이터가 무엇인지 먼저 본다

가장 먼저 볼 것은 dtype이야.

Python
실행됨
df.dtypes

특정 열 하나만 확인하려면:

Python
실행됨
df['age'].dtype

데이터프레임 전체 구조와 결측치까지 함께 확인하려면:

Python
실행됨
df.info()

예를 들어,

Python
실행됨
import pandas as pd

df = pd.DataFrame({
    'age': ['20', '31', '45'],
    'sales': ['1,200', '2,500', '900'],
    'date': ['2026-01-01', '2026-01-03', '2026-01-05']
})

print(df.dtypes)

결과가 다음처럼 나올 수 있어.

age      object
sales    object
date     object
dtype: object

여기서 중요한 판단은:

object = 그냥 문자열이라는 뜻으로 끝내면 안 된다.

실제 의미를 보면,

age → 정수로 사용하는 게 자연스러움

sales → 쉼표가 포함된 숫자 표현

date → 날짜

따라서 세 열의 목표 자료형이 서로 다르다.

시험에서 자주 생기는 착각
Python
실행됨
df['sales'].astype(int)

이건 바로 실패해.

왜냐하면 "1,200"의 쉼표 때문에 문자열을 그대로 정수로 해석할 수 없기 때문이야.

즉,

표현을 먼저 정리해야 하는 경우와 자료형만 바꾸면 되는 경우를 구분해야 한다.

🔄 2. 목표 유형 변환 — 무엇으로 바꿀 것인가
단순한 자료형 변환

값이 이미 깨끗하다면 astype()이 가장 직관적이야.

Python
실행됨
df['age'] = df['age'].astype(int)

또는:

Python
실행됨
df['age'] = df['age'].astype('int64')

실수형:

Python
실행됨
df['score'] = df['score'].astype(float)

문자형:

Python
실행됨
df['code'] = df['code'].astype(str)

여기서 code 같은 변수는 특히 주의해야 해.

00123
00457

이 값은 숫자처럼 보여도 상품코드·지역코드·우편번호 같은 식별자라면 정수로 바꾸면 안 돼.

Python
실행됨
int('00123')

결과는:

123

앞의 00이 사라진다.

따라서 자료형은 단순한 모양이 아니라 변수의 의미로 결정해야 해.

🧹 3. 표현을 정리한 뒤 변환하기

실기에서는 이 형태가 꽤 중요해.

Python
실행됨
df['sales']
0    1,200
1    2,500
2      900

쉼표를 없애고 숫자로 바꾼다.

Python
실행됨
df['sales'] = df['sales'].str.replace(',', '', regex=False).astype(int)

결과:

0    1200
1    2500
2     900
표현 변환과 자료형 변환을 분리해서 생각하자

원본:

"1,200"

1단계 — 표현 정리:

"1200"

2단계 — 자료형 변환:

1200

즉,

Python
실행됨
.str.replace(...)

는 표현을 정리하고,

Python
실행됨
.astype(int)

는 자료형을 변경한다.

이 차이를 이해하면 전처리 문제가 훨씬 쉬워져.

🛡️ 4. pd.to_numeric() — 숫자 변환에서 더 안전한 방법

실제 데이터에는 이런 값이 들어갈 수 있어.

20
31
미상
45

이 상태에서:

Python
실행됨
df['age'].astype(int)

를 하면 "미상" 때문에 오류가 발생한다.

이럴 때 자주 사용하는 것이:

Python
실행됨
pd.to_numeric()

이야.

Python
실행됨
df['age'] = pd.to_numeric(df['age'], errors='coerce')

errors='coerce'는 숫자로 변환할 수 없는 값을 결측값으로 바꾼다.

20
31
NaN
45
하지만 여기서 끝내면 안 돼

errors='coerce'는 아주 편해서 오히려 위험해.

원래 정상 데이터였는데 잘못된 변환 때문에 NaN이 생겨도 코드가 그냥 실행될 수 있거든.

그래서 다음 단계인 검증이 반드시 붙어야 한다.

📅 5. 날짜 자료형 변환

날짜가 다음처럼 문자로 들어오는 경우가 많아.

2026-01-01
2026-02-15
2026-03-20

현재 타입은 보통 문자열 계열이지만 의미는 날짜야.

날짜 변환은:

Python
실행됨
df['date'] = pd.to_datetime(df['date'])

사용하면 된다.

변환 후에는 날짜 연산이 가능해진다.

Python
실행됨
df['date'].dt.year
Python
실행됨
df['date'].dt.month
Python
실행됨
df['date'].dt.day

예를 들어:

Python
실행됨
df['year'] = df['date'].dt.year
잘못된 날짜가 있다면
Python
실행됨
df['date'] = pd.to_datetime(df['date'], errors='coerce')

변환 불가능한 값은 NaT가 된다.

숫자의 NaN과 비슷하게 **날짜 결측값은 NaT**라고 보면 돼.

🧩 6. 범주형 변환

성별, 등급, 지역처럼 값의 종류가 제한된 변수는 범주형으로 표현할 수도 있어.

Python
실행됨
df['grade'] = df['grade'].astype('category')

예를 들어:

A
B
A
C
A
B

처럼 반복되는 범주 데이터에 적합해.

다만 실기 문제에서 단순히 "A", "B", "C"가 있다고 무조건 category로 변환할 필요는 없어.

문제가 요구하는 분석이나 전처리 목적에 따라 선택하면 된다.

⚠️ 7. 퍼센트 표현은 특히 의미를 확인한다

예를 들어 데이터가:

"35%"
"20%"
"7%"

라고 하자.

일단 %를 제거할 수 있어.

Python
실행됨
df['rate'] = df['rate'].str.replace('%', '', regex=False)
df['rate'] = pd.to_numeric(df['rate'])

그러면:

35
20
7

이 된다.

그런데 비율값이 필요하다면 여기서 한 단계 더 필요해.

Python
실행됨
df['rate'] = df['rate'] / 100

결과:

0.35
0.20
0.07

여기서 중요한 차이는:

자료형 변환과 값의 의미 변환은 같은 일이 아니다.

"35%" → 35는 표현과 자료형을 바꾼 것이고,

35 → 0.35는 비율의 의미에 맞게 값을 변환한 것이야.

✅ [변환보다 중요한 마지막 단계] 변환 결과 검증

자료형을 바꿨으면 반드시 확인해야 해.

🔎 검증 1 — 자료형이 목표대로 바뀌었는가
Python
실행됨
df.dtypes

또는:

Python
실행됨
df['age'].dtype

예를 들어 목표가 숫자형인데 여전히 object라면 변환이 제대로 되지 않은 거야.

🔎 검증 2 — 실제 값이 정상적인가
Python
실행됨
df.head()
Python
실행됨
df['age'].head()

자료형만 보는 것으로 부족해.

예를 들어 "35%" → 35가 됐는데 문제에서 요구한 값이 0.35라면 dtype은 맞아도 데이터는 틀린 것이거든.

🔎 검증 3 — 새로운 결측값이 생겼는가

특히:

Python
실행됨
errors='coerce'

를 사용했다면 꼭 확인하자.

Python
실행됨
df['age'].isna().sum()

가장 좋은 습관은 변환 전후를 비교하는 거야.

Python
실행됨
before_na = df['age'].isna().sum()

df['age'] = pd.to_numeric(df['age'], errors='coerce')

after_na = df['age'].isna().sum()

print(before_na, after_na)

예를 들어:

0 5

라면 변환 과정에서 5개가 새롭게 결측값이 된 거야.

그 5개가 왜 생겼는지 확인해야 한다.

🔎 검증 4 — 값의 범위가 상식적인가

나이를 변환했다고 해보자.

Python
실행됨
df['age'].describe()

만약:

min      -5
max     999

같은 값이 나온다면 자료형 변환에는 성공했지만 데이터 자체에는 문제가 있을 가능성이 있어.

즉 검증은:

문법적으로 성공했는가 + 데이터 의미도 유지됐는가

두 가지를 본다.

🧠 [한 덩어리로 기억하기] 실전 변환 패턴

숫자처럼 생긴 문자형 데이터가 있다고 하자.

Python
실행됨
df['sales']
1,200
2,500
미상
3,100
① 현재 상태 확인
Python
실행됨
df['sales'].dtype
df['sales'].head()
② 표현 정리
Python
실행됨
df['sales'] = df['sales'].str.replace(',', '', regex=False)
③ 목표 자료형 변환
Python
실행됨
df['sales'] = pd.to_numeric(df['sales'], errors='coerce')
④ 결과 검증
Python
실행됨
df['sales'].dtype
df['sales'].head()
df['sales'].isna().sum()
df['sales'].describe()

이 패턴을 머릿속에 박아두면 돼.

확인 → 정리 → 변환 → 검증

🧭 [시험장에서 어떤 함수를 고를까?] 변환 도구 비교
목적	대표 코드	핵심
현재 자료형 확인	df.dtypes	여러 열 확인
특정 열 자료형 확인	df['x'].dtype	한 열 확인
구조 + 결측 확인	df.info()	전체 구조 파악
일반 자료형 변환	astype()	깨끗한 값에 적합
숫자 변환	pd.to_numeric()	잘못된 숫자 처리 가능
날짜 변환	pd.to_datetime()	날짜/시간 자료형 변환
범주형 변환	astype('category')	범주형 데이터
문자열 표현 정리	.str.replace()	쉼표·기호 제거
변환 확인	dtypes, head()	유형과 값 확인
결측 증가 확인	isna().sum()	coerce 후 중요
범위 검증	describe()	비정상 값 탐색
💡 [실기에서 자주 틀리는 세 갈래] 꼭 구분하기
자료형만 바꾸면 되는 경우
"25" → 25
Python
실행됨
df['age'] = df['age'].astype(int)
표현부터 정리해야 하는 경우
"1,200" → "1200" → 1200
Python
실행됨
df['sales'] = (
    df['sales']
    .str.replace(',', '', regex=False)
    .astype(int)
)
잘못된 값까지 처리해야 하는 경우
"20", "31", "미상"
Python
실행됨
df['age'] = pd.to_numeric(df['age'], errors='coerce')

그리고 반드시:

Python
실행됨
df['age'].isna().sum()

까지 확인.

🧷 [이 네 줄이면 뼈대가 잡힌다] 시험 직전 암기
Python
실행됨
df.dtypes
df['col'] = pd.to_numeric(df['col'], errors='coerce')
df['col'].dtype
df['col'].isna().sum()

다만 실제 문제에서는 중간에 필요에 따라:

Python
실행됨
.str.replace()
pd.to_datetime()
.astype()

가 들어온다고 생각하면 돼.

핵심 판단 순서는 하나야.

① 지금 무엇인가 → ② 무엇이어야 하는가 → ③ 어떻게 바꿀까 → ④ 무엇이 망가졌는지 확인했나

자료형 변환의 진짜 실력은 astype()을 아는 게 아니라 변환 후 데이터의 의미가 보존됐는지 확인할 줄 아는 것이야.

참고로 지금 학습 상태는 메시지에 정확히 **저장**이라고 보내면 이어서 복원할 수 있게 저장할 수 있어.
또 원하면 주제 뒤에 **.cc**를 붙여 HTML 기반 학습 화면으로 볼 수도 있어.

╭─ 📍 학습 대시보드

🧭 현재 단원 · 2-2-1-1. 자료형과 표현 변환

🧠 학습 상태 · 핵심 개념 학습 완료

🎯 주 경로 · 현재 유형 → 목표 변환 → 결과 검증
╰─

[자료형과 표현 변환 · 다음 학습]

a. 🚀 2-2-1-1 실기형 적용 패턴 익히기
b. 🔬 astype()·to_numeric()·to_datetime() 차이 깊게 보기
c. 🔗 결측치 처리와 자료형 변환 연결하기
d. 🧩 범주형·문자열·날짜형 변환 사례 확장하기

2026.08.26 (Wed) 18:17:00 KST
