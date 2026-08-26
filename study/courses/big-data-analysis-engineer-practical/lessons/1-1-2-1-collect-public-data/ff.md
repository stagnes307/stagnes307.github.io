🗃️ [공개 데이터를 내 분석 환경으로] 1-1-2-1. 공개 데이터 확보와 적재

#빅데이터분석기사 #실기 #데이터수집 #공개데이터 #API #CSV #데이터적재 #pandas

이 단원에서 잡아야 할 핵심 흐름은 딱 하나야.

공개 데이터에 접근한다 → 필요한 데이터를 수집한다 → 분석 가능한 형태로 적재한다 → 제대로 들어왔는지 확인한다

파일을 읽는 코드 하나를 외우는 단원이 아니야. “외부의 데이터를 신뢰할 수 있는 DataFrame으로 만드는 과정”이라고 이해하면 이후 전처리까지 자연스럽게 이어져.

그리고 지금부터 진행한 학습 상태는 나중에 **저장**이라고 입력하면 이어서 공부할 수 있게 저장할 수 있어.

🧭 먼저 전체 그림을 잡자

공개 데이터 수집은 크게 두 가지 모습으로 나타나.

방식	공개 데이터의 모습	대표 접근법
파일형	CSV, Excel, JSON 등	pd.read_csv(), pd.read_excel()
API형	요청하면 서버가 데이터를 반환	requests.get() → JSON/XML 처리

둘은 겉모습은 다르지만 결국 목적지는 같아.

외부 데이터 → Python 객체 → DataFrame → 확인 → 분석

공공데이터포털 / 공개 웹사이트 / 기관
              ↓
        데이터 접근
              ↓
       CSV 또는 API 응답
              ↓
          데이터 수집
              ↓
      pandas DataFrame
              ↓
       구조·결측·자료형 확인
              ↓
          분석 시작

여기서 적재(load)라는 말이 중요해.

데이터를 내려받았다는 것만으로는 아직 분석할 준비가 끝난 게 아니야. Python이나 분석 시스템에서 실제로 사용할 수 있는 구조로 올려놓아야 해.

실기에서는 보통 그 구조가 **pandas.DataFrame**이라고 생각하면 돼.

🌐 1. 공개 데이터 접근
공개 데이터 접근이란 무엇인가

공개 데이터는 정부·공공기관·기업·연구기관 등이 외부에 제공하는 데이터야.

예를 들어 이런 형태가 있어.

공공데이터포털의 CSV 파일

행정기관의 Excel 통계자료

기상·교통 등의 Open API

공개된 JSON 데이터

분석용으로 제공된 CSV 데이터셋

여기서 먼저 판단할 것은 “어떤 방식으로 제공되고 있는가?”야.

파일인가, API인가

이 구분이 첫 번째 분기점이야.

데이터 제공 방식
├─ 파일
│   ├─ CSV
│   ├─ Excel
│   └─ JSON
│
└─ API
    ├─ URL 요청
    ├─ 파라미터 전달
    └─ JSON/XML 응답

파일이면 읽으면 되고, API이면 요청해야 해.

이 차이를 확실하게 잡아두자.

CSV 파일 접근

가장 기본적인 형태야.

Python
실행됨
import pandas as pd

df = pd.read_csv("data.csv")

여기서 일어나는 일을 풀면,

data.csv
   ↓ read_csv()
pandas
   ↓
DataFrame df

즉 pd.read_csv()는 단순한 파일 열기가 아니라 CSV 데이터를 DataFrame으로 적재하는 함수야.

URL에 있는 CSV도 직접 읽을 수 있어

CSV 파일이 웹에 공개되어 있다면 경우에 따라 URL을 그대로 사용할 수도 있어.

Python
실행됨
import pandas as pd

url = "https://example.com/data.csv"

df = pd.read_csv(url)

구조는 같지.

웹 서버의 CSV
      ↓
   URL 접근
      ↓
pd.read_csv()
      ↓
 DataFrame
Excel 데이터
Python
실행됨
df = pd.read_excel("data.xlsx")

여러 시트가 있으면 특정 시트를 지정할 수도 있어.

Python
실행됨
df = pd.read_excel("data.xlsx", sheet_name="Sheet1")

즉 시험에서 가장 먼저 생각해야 하는 대응 관계는 이거야.

데이터	대표 함수
CSV	pd.read_csv()
Excel	pd.read_excel()
JSON	pd.read_json() 또는 JSON → DataFrame
API	requests.get()
📡 2. API를 통한 공개 데이터 접근

파일은 이미 만들어진 데이터를 가져오는 방식이야.

API는 조금 다르다.

서버에 원하는 데이터를 요청하면 서버가 결과를 보내주는 방식이야.

API 요청의 구조

가장 단순화하면 이렇게 볼 수 있어.

나
↓
"서울의 특정 데이터를 주세요"
↓
API 서버
↓
JSON 등의 응답
↓
나

Python에서는 보통 requests 라이브러리를 사용해.

Python
실행됨
import requests

url = "https://api.example.com/data"

response = requests.get(url)

여기서 중요한 구분이 하나 있어.

response는 아직 DataFrame이 아니야.

HTTP 응답
≠
DataFrame

응답에서 데이터를 꺼내고 다시 DataFrame으로 만들어야 해.

JSON 응답 처리

API가 JSON을 반환한다고 해보자.

Python
실행됨
import requests
import pandas as pd

url = "https://api.example.com/data"

response = requests.get(url)

data = response.json()

df = pd.DataFrame(data)

전체 흐름은 이거야.

API 서버
   ↓
requests.get()
   ↓
response
   ↓
response.json()
   ↓
Python dict / list
   ↓
pd.DataFrame()
   ↓
DataFrame

이 흐름은 꼭 이해해야 해.

requests.get()이 데이터를 요청하고,

response.json()이 응답 내용을 Python 자료구조로 변환하고,

pd.DataFrame()이 그것을 분석 가능한 표로 적재하는 거야.

🧩 3. API의 파라미터

공개 API에서는 전체 데이터를 무작정 보내주지 않는 경우가 많아.

우리가 조건을 지정해 요청하지.

예를 들어,

지역 = 서울
연도 = 2025
페이지 = 1
한 페이지 데이터 수 = 100

같은 조건이 파라미터야.

Python에서는 다음처럼 작성할 수 있어.

Python
실행됨
params = {
    "region": "Seoul",
    "year": 2025,
    "page": 1,
    "perPage": 100
}

response = requests.get(url, params=params)

즉,

Python
실행됨
requests.get(url)

은 단순 요청이고,

Python
실행됨
requests.get(url, params=params)

은 조건을 포함한 요청이라고 보면 돼.

인증키가 있는 경우

공공 API에는 흔히 서비스키나 인증키가 필요해.

개념적으로는 이렇게 들어갈 수 있어.

Python
실행됨
params = {
    "serviceKey": "발급받은_인증키",
    "pageNo": 1,
    "numOfRows": 100
}

그리고

Python
실행됨
response = requests.get(url, params=params)

으로 요청하는 방식이지.

여기서 기억할 핵심은 인증키 자체의 형식보다,

API는 URL + 필요한 요청 파라미터를 이용해 데이터를 요청한다

는 구조야.

📥 4. 데이터 수집

접근할 수 있다고 해서 수집이 끝난 건 아니야.

데이터를 실제로 확보해야 하지.

파일형 데이터의 수집

파일이 이미 제공되어 있다면 흔히 한 줄이면 충분해.

Python
실행됨
df = pd.read_csv("data.csv")

이 코드에는 사실 두 과정이 같이 들어 있어.

파일 읽기
+
DataFrame 적재

그래서 파일형 데이터는 접근·수집·적재가 거의 동시에 일어나는 경우가 많아.

API형 데이터의 수집

API는 조금 더 단계가 드러나.

Python
실행됨
import requests

response = requests.get(url, params=params)

여기서 반드시 확인할 만한 것이 응답 상태야.

Python
실행됨
print(response.status_code)

대표적으로 HTTP 상태 코드 200은 요청이 정상적으로 처리됐다는 뜻이야.

개념적으로,

요청
↓
서버 응답
↓
상태 확인
↓
데이터 변환

순서가 된다.

정상 응답만 처리하는 구조
Python
실행됨
response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
else:
    print("데이터 수집 실패")

여기서 꽤 중요한 사고 습관이 생겨.

“코드가 실행됐다”와 “데이터가 정상적으로 수집됐다”는 같은 말이 아니다.

HTTP 요청 자체는 실행됐어도 서버가 오류를 반환할 수 있으니까.

🧱 5. 수집한 데이터를 DataFrame으로 적재

API에서 이런 JSON 구조를 받았다고 해보자.

Python
실행됨
data = [
    {"city": "서울", "population": 930},
    {"city": "부산", "population": 330},
    {"city": "대구", "population": 240}
]

이것을 DataFrame으로 바꾸면,

Python
실행됨
df = pd.DataFrame(data)

대략 이런 표가 만들어져.

city	population
서울	930
부산	330
대구	240

여기서 적재의 의미가 선명해지지.

JSON 데이터
     ↓
pd.DataFrame()
     ↓
행 × 열 구조
     ↓
pandas 분석 가능
🪆 6. 실제 API JSON이 한 단계 더 복잡한 이유

API 응답에서 초보자가 자주 막히는 곳이 있어.

JSON 안에 우리가 원하는 데이터가 바로 있지 않고 중첩되어 있는 경우야.

예를 들어 응답이 이렇게 생겼다고 하자.

Python
실행됨
data = {
    "response": {
        "items": [
            {"city": "서울", "value": 10},
            {"city": "부산", "value": 20}
        ]
    }
}

그냥

Python
실행됨
pd.DataFrame(data)

한다고 우리가 원하는 표가 만들어지지는 않아.

먼저 실제 데이터가 있는 위치까지 들어가야 해.

Python
실행됨
items = data["response"]["items"]

df = pd.DataFrame(items)

이걸 구조로 보면 쉬워.

data
└─ response
   └─ items
      ├─ 서울 / 10
      └─ 부산 / 20

따라서 필요한 것은

Python
실행됨
data["response"]["items"]

야.

핵심 원칙

JSON API를 만나면 바로 DataFrame부터 만들려고 하지 말고,

“실제 행 데이터가 JSON의 어느 위치에 들어 있지?”

부터 확인해야 해.

이건 실무에서도 아주 중요한 습관이야.

🔎 수집 결과 확인

데이터를 적재하고 바로 모델링으로 가면 안 돼.

데이터가 의도한 모습으로 들어왔는지 먼저 확인해야 해.

이때 가장 많이 사용하는 pandas 도구들을 묶어서 보자.

👀 1. 데이터 일부 확인 — head()
Python
실행됨
df.head()

기본적으로 앞부분을 보여줘.

특정 개수를 보고 싶으면,

Python
실행됨
df.head(10)

처럼 사용할 수 있어.

이걸 통해 확인하는 것은,

열 이름이 맞는지

데이터가 실제로 들어왔는지

값의 형태가 예상과 비슷한지

야.

📐 2. 데이터 크기 확인 — shape
Python
실행됨
df.shape

결과가

Python
실행됨
(1000, 8)

이라면,

1000행 × 8열

이라는 뜻이야.

순서를 기억하자.

Python
실행됨
df.shape
# (행, 열)

많이 헷갈리는 부분이야.

🏷️ 3. 열 이름 확인 — columns
Python
실행됨
df.columns

예를 들어,

Index(['city', 'year', 'population'], dtype='object')

처럼 나타날 수 있어.

분석 전에 필요한 변수가 실제로 있는지 확인하는 데 사용해.

🧬 4. 자료형과 결측 상태 확인 — info()
Python
실행됨
df.info()

여기서는 주로,

행 수

열 이름

Non-Null 개수

데이터 타입

을 확인할 수 있어.

예를 들어 숫자라고 생각했던 변수가 object로 들어왔다면 이후 처리가 필요할 수 있어.

즉 info()는 단순 출력이 아니라 데이터 구조 진단이야.

🕳️ 5. 결측치 확인
Python
실행됨
df.isnull().sum()

각 열에 결측값이 몇 개 있는지 확인해.

예를 들어,

city          0
year          0
population    7

이라면 population에 결측치가 7개 있다는 뜻이야.

isna()도 같은 목적으로 자주 사용해.

Python
실행됨
df.isna().sum()
📊 6. 기초 통계량 확인 — describe()
Python
실행됨
df.describe()

수치형 변수의,

개수

평균

표준편차

최솟값

사분위수

최댓값

등을 볼 수 있어.

이건 단순 통계 출력 이상의 의미가 있어.

예를 들어 인구 데이터에 음수가 들어 있다면 describe()의 최솟값을 보고 이상 가능성을 알아챌 수도 있지.

🧰 공개 데이터 적재 후 기본 점검 루틴

실기 공부에서는 아래 순서를 하나의 루틴으로 만들어두면 좋아.

Python
실행됨
import pandas as pd

df = pd.read_csv("data.csv")

print(df.head())
print(df.shape)
print(df.columns)
print(df.info())
print(df.isnull().sum())
print(df.describe())

다만 여기서 한 가지.

Python
실행됨
df.info()

는 자체적으로 내용을 출력하기 때문에 보통은

Python
실행됨
df.info()

라고만 작성해도 충분해.

따라서 더 자연스러운 형태는,

Python
실행됨
print(df.head())
print(df.shape)
print(df.columns)

df.info()

print(df.isnull().sum())
print(df.describe())

야.

⚠️ 공개 데이터에서 자주 만나는 문제
한글이 깨진다 — 인코딩

CSV를 불러올 때 한글이 깨지거나 오류가 날 수 있어.

기본적으로는,

Python
실행됨
df = pd.read_csv("data.csv")

를 사용하지만 파일의 인코딩에 따라,

Python
실행됨
df = pd.read_csv("data.csv", encoding="cp949")

또는

Python
실행됨
df = pd.read_csv("data.csv", encoding="euc-kr")

등을 지정해야 하는 상황이 생길 수 있어.

여기서 중요한 개념은 특정 인코딩을 무조건 외우는 게 아니야.

UnicodeDecodeError 같은 문제가 나면 파일의 문자 인코딩이 현재 읽는 방식과 맞지 않을 가능성을 의심한다.

이렇게 원인과 조치를 연결해야 해.

구분자가 쉼표가 아니다

CSV처럼 보이지만 실제 구분자가 ;인 파일도 있어.

Python
실행됨
df = pd.read_csv("data.csv", sep=";")

탭으로 구분된 데이터라면,

Python
실행됨
df = pd.read_csv("data.tsv", sep="\t")

처럼 처리할 수 있어.

즉 read_csv()의 본질은 단순히 .csv 확장자를 읽는 것이 아니라 구분자로 나뉜 표 형태의 데이터를 읽는 것이라고 이해하면 좋아.

🔄 공개 API의 여러 페이지 수집

공개 API에서는 데이터를 한 번에 전부 보내주지 않는 경우가 많아.

예를 들어 총 5,000건인데 API가 한 번에 100건씩만 준다면,

1페이지 → 100건
2페이지 → 100건
3페이지 → 100건
...

처럼 여러 번 요청해야 해.

이걸 페이지네이션(pagination)이라고 해.

개념적으로는 이렇게 수집해.

Python
실행됨
all_data = []

for page in range(1, 6):

    params = {
        "page": page,
        "perPage": 100
    }

    response = requests.get(url, params=params)
    data = response.json()

    all_data.extend(data)

그리고 마지막에,

Python
실행됨
df = pd.DataFrame(all_data)

로 적재하지.

흐름을 붙여보면,

page 1 ─┐
page 2 ─┤
page 3 ─┼→ all_data → DataFrame
page 4 ─┤
page 5 ─┘

이 부분에서 중요한 건 코드 자체보다 왜 반복하는지야.

API가 한 번에 제공하는 데이터 개수가 제한되어 있기 때문이야.

🧠 세 개념을 구별하면 이 단원은 정리된다
접근 · 수집 · 확인
단계	질문	대표 행동
공개 데이터 접근	데이터가 어디 있고 어떻게 받을 수 있지?	파일/URL/API 확인
데이터 수집·적재	실제 분석 환경으로 어떻게 가져오지?	read_csv, requests, DataFrame
수집 결과 확인	제대로 가져온 게 맞나?	head, shape, info, 결측 확인

이 세 단계를 한 문장으로 만들어보면,

공개 데이터의 제공 방식을 확인하고, 파일 또는 API를 통해 데이터를 수집하여 DataFrame으로 적재한 뒤 데이터의 크기·구조·자료형·결측 여부를 확인한다.

이 문장이 이번 단원의 뼈대야.

🧪 코드 하나로 전체 과정 연결하기

파일형 공개 데이터라면 가장 간단해.

Python
실행됨
import pandas as pd

# 1. 공개 데이터 접근 및 적재
df = pd.read_csv("public_data.csv")

# 2. 수집 결과 확인
print(df.head())
print(df.shape)
print(df.columns)

df.info()

print(df.isnull().sum())

API형이라면 단계가 더 선명하게 보여.

Python
실행됨
import requests
import pandas as pd

# 1. 공개 데이터 접근 정보
url = "https://api.example.com/data"

params = {
    "page": 1,
    "perPage": 100
}

# 2. 데이터 수집
response = requests.get(url, params=params)

# 3. 정상 응답 확인
if response.status_code == 200:

    data = response.json()

    # 실제 JSON 구조에 맞게 데이터 추출
    items = data["response"]["items"]

    # 4. DataFrame 적재
    df = pd.DataFrame(items)

    # 5. 수집 결과 확인
    print(df.head())
    print(df.shape)
    df.info()

else:
    print("데이터 수집 실패")

여기서 코드 한 줄씩 외우기보다 다음 연결을 기억해.

URL + params
      ↓
requests.get()
      ↓
response
      ↓
JSON 변환
      ↓
실제 데이터 추출
      ↓
DataFrame
      ↓
head / shape / info

이 흐름을 머릿속에서 재구성할 수 있으면 훨씬 강해져.

🎯 실기에서 특히 구별해야 할 포인트
requests.get()과 pd.read_csv()는 역할이 다르다
Python
실행됨
pd.read_csv(...)

는 표 형태 파일을 읽어서 DataFrame으로 적재하는 쪽이고,

Python
실행됨
requests.get(...)

은 웹 서버에 HTTP 요청을 보내 응답을 받는 것이야.

requests.get() 결과가 바로 DataFrame은 아니지.

이 차이는 확실히 잡아둬.

response.json()과 pd.DataFrame()도 다르다
Python
실행됨
data = response.json()

은 JSON 응답을 Python의 리스트나 딕셔너리 등의 구조로 바꾸는 단계야.

그 다음,

Python
실행됨
df = pd.DataFrame(data)

가 표 형태의 DataFrame을 만드는 단계고.

그래서

response
→ Python 자료구조
→ DataFrame

이라는 두 단계가 존재해.

head()만 보고 끝내면 부족하다

head()는 값 몇 개가 보인다는 것만 확인해.

그런데 실제 분석을 시작하려면 최소한,

Python
실행됨
df.shape
df.info()
df.isnull().sum()

같은 구조 확인도 같이 하는 게 좋아.

왜냐하면 데이터가 존재하는 것과 분석 가능한 상태인 것은 다르기 때문이야.

🧷 이번 단원의 기억 고리

시험장에서 머리가 하얘지면 이 다섯 글자 흐름으로 복구하면 돼.

접 → 수 → 적 → 구 → 검

접 : 접근 방식 확인
       ↓
수 : 수집
       ↓
적 : DataFrame 적재
       ↓
구 : 구조 확인
       ↓
검 : 이상·결측 검증

그리고 Python으로 번역하면,

파일/API 확인
    ↓
read_csv / requests.get
    ↓
DataFrame
    ↓
head / shape / info
    ↓
isnull / describe

이 대응 관계가 이번 학습의 중심이야.

╭─ 📍 공개 데이터 확보와 적재 · 학습 대시보드

🗃️ 주제 · 1-1-2-1. 공개 데이터 확보와 적재

🧠 학습 상태 · 접근 → 수집 → 적재 → 확인 흐름 형성

🎯 다음 방향 · 실제 코드에서 데이터 수집 절차 연결

[공개 데이터 · 다음 학습]
a. 💻 CSV·API 수집 코드를 직접 따라가며 실습하기
b. 🔬 JSON 중첩 구조와 페이지네이션 더 깊게 보기
c. 🧹 수집 후 결측치·자료형 전처리와 연결하기
d. 🌐 공공데이터 API가 실제로 반환하는 구조 살펴보기
╰─

[2026.08.26 (Wed) 18:10:03 KST]
