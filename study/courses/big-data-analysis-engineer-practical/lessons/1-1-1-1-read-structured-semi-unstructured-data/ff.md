🧭 [형태를 알면 읽는 법이 보인다] 1-1-1-1. 정형·반정형·비정형 데이터 읽기

#빅데이터분석기사 #실기 #데이터수집 #pandas #정형데이터 #반정형데이터 #비정형데이터

이번 단원의 핵심은 파일 확장자를 외우는 것보다 “데이터의 구조가 얼마나 고정되어 있는가”를 먼저 판별하는 것이야.

빅데이터분석기사 실기에서는 특히 정형 데이터 → pandas DataFrame으로 읽기 → 구조 확인 → 분석 가능한 상태로 만들기가 가장 중요하고, 반정형·비정형 데이터는 그 차이를 이해해 두면 돼.

참고로 지금 학습 상태는 저장이라고 입력하면 저장할 수 있어. 그리고 원하면 .cc 빅데이터분석기사 실기처럼 입력해서 이 내용을 HTML 학습 화면으로 볼 수도 있어.

🧩 먼저 세 종류를 한 번에 구분하자

데이터가 아래처럼 있다고 생각해 보자.

이름    나이    점수
민수     25      80
지수     27      92

행과 열의 위치가 정해져 있지? 이런 데이터가 정형 데이터야.

그런데 이렇게 생겼다면?

JSON
{
  "name": "민수",
  "age": 25,
  "scores": {
    "python": 80,
    "sql": 90
  }
}

name, age 같은 구조를 나타내는 표시가 존재하지만, 모든 데이터가 똑같은 행·열 구조로 고정된 것은 아니야. 이런 데이터가 반정형 데이터야.

반면 다음과 같은 것은?

오늘 고객센터에 문의했는데 상담원 응대가 정말 좋았습니다.

문장의 어느 위치가 이름이고 점수인지 정해져 있지 않아. 이런 것이 비정형 데이터야.

세 유형의 결정적인 차이
구분	구조	대표 예	분석 전 처리
정형	행·열 구조가 명확	CSV, Excel, DB 테이블	바로 DataFrame으로 사용하기 쉬움
반정형	태그·키 등 부분적 구조 존재	JSON, XML, HTML	필요한 구조를 추출·평탄화
비정형	고정된 구조 없음	텍스트, 이미지, 음성	특징 추출·전처리 필요

여기서 하나만 기억하면 돼.

정형 → 표가 이미 만들어져 있다.
반정형 → 표를 만들 단서가 있다.
비정형 → 표 자체가 없다.

📊 정형 데이터 읽기

빅데이터분석기사 실기에서 가장 먼저 익숙해져야 할 부분이야.

Python에서는 보통 pandas를 사용해.

Python
실행됨
import pandas as pd

이 한 줄을 먼저 쓰는 경우가 많아.

CSV 파일

가장 대표적인 형태야.

Python
실행됨
df = pd.read_csv("data.csv")

결과는 바로 DataFrame이 돼.

Python
실행됨
print(df.head())

head()는 기본적으로 앞의 5개 행을 보여줘.

파일을 읽었다고 바로 분석하지 말고 먼저 구조를 확인하는 습관을 들이는 게 좋아.

Python
실행됨
df.head()
df.shape
df.info()
df.dtypes

각각 의미가 달라.

코드	확인하는 것
df.head()	실제 데이터 형태
df.shape	행과 열의 개수
df.info()	자료형, 결측치 여부 등 전체 구조
df.dtypes	각 열의 자료형

예를 들어,

Python
실행됨
df.shape

결과가

(1000, 8)

이라면 1000행 8열이라는 뜻이야.

CSV에서 자주 만나는 옵션

구분자가 쉼표가 아닐 수도 있어.

Python
실행됨
df = pd.read_csv("data.csv", sep="\t")

이건 탭으로 구분된 데이터야.

특정 열을 인덱스로 바로 지정할 수도 있어.

Python
실행됨
df = pd.read_csv("data.csv", index_col=0)

첫 번째 열을 DataFrame의 index로 사용한다는 뜻이야.

인코딩 문제도 실제 데이터에서 자주 나타나.

Python
실행됨
df = pd.read_csv("data.csv", encoding="cp949")

또는

Python
실행됨
df = pd.read_csv("data.csv", encoding="utf-8")

한글 CSV 파일에서 글자가 깨지거나 UnicodeDecodeError가 나면 인코딩을 의심하는 것이 첫 번째 대응이야.

결측치 표현을 읽을 때 지정하기

파일에서 "?", "NA" 같은 문자열이 결측치를 의미할 수도 있어.

Python
실행됨
df = pd.read_csv(
    "data.csv",
    na_values=["?", "NA"]
)

그러면 해당 값을 pandas의 결측값으로 처리할 수 있어.

여기서 중요한 흐름은:

파일 읽기 → 자료형 확인 → 결측치 확인 → 분석

이야.

📗 Excel 데이터 읽기

Excel 파일은 다음처럼 읽어.

Python
실행됨
df = pd.read_excel("data.xlsx")

특정 시트를 지정하려면:

Python
실행됨
df = pd.read_excel(
    "data.xlsx",
    sheet_name="Sheet1"
)

시트 번호를 사용할 수도 있어.

Python
실행됨
df = pd.read_excel(
    "data.xlsx",
    sheet_name=0
)

0은 첫 번째 시트야.

필요한 열만 읽기
Python
실행됨
df = pd.read_excel(
    "data.xlsx",
    usecols=["이름", "점수"]
)

이렇게 하면 지정된 열만 가져와.

CSV와 Excel이 달라도, 읽고 난 뒤에는 둘 다 대부분 DataFrame으로 다룬다는 점이 중요해.

CSV ─────┐
         │
Excel ───┼──→ DataFrame → 전처리 → 분석 → 모델링
         │
DB ──────┘

즉, 실기에서 중요한 건 입력 형식은 달라도 pandas DataFrame으로 통합해서 처리한다는 사고방식이야.

🗃️ 데이터베이스 형태의 정형 데이터

관계형 데이터베이스도 정형 데이터야.

테이블을 생각하면 돼.

customer

id | name | age | city
-----------------------
1  | 민수 | 25  | 서울
2  | 지수 | 27  | 부산

id, name, age, city라는 열 구조가 정해져 있지.

Python에서는 DB 연결 후 SQL을 이용해 가져올 수 있고, pandas에서는 다음과 같은 형태가 사용돼.

Python
실행됨
pd.read_sql(...)

시험 학습에서는 우선

DB 테이블 = 행과 열이 정해진 대표적인 정형 데이터

라고 연결해 두면 충분해.

🧱 반정형 데이터 읽기

반정형에서 가장 대표적인 형식은 JSON이야.

JSON은 이런 형태를 사용해.

JSON
{
    "name": "Ailey",
    "score": 90
}

"name"과 "score"가 구조를 알려주는 key이고,

"Ailey"와 90이 value야.

JSON을 pandas로 읽기

표 형태에 가까운 JSON이라면:

Python
실행됨
df = pd.read_json("data.json")

사용할 수 있어.

하지만 JSON의 핵심은 중첩 구조가 가능하다는 것이야.

JSON
{
    "name": "민수",
    "score": {
        "python": 90,
        "sql": 80
    }
}

이 데이터는 단순한 2차원 표가 아니지.

score 안에 다시 python, sql이라는 구조가 들어가 있어.

이게 정형 데이터와 반정형 데이터를 구분하는 중요한 지점이야.

Python의 json 모듈

JSON을 Python 객체로 직접 처리할 때는:

Python
실행됨
import json

with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

이렇게 읽을 수 있어.

이후:

Python
실행됨
print(data["name"])

처럼 key를 이용해서 값을 가져와.

즉,

JSON 파일
   ↓
json.load()
   ↓
dict / list
   ↓
필요한 데이터 추출
   ↓
DataFrame

이라는 흐름도 알아두면 좋아.

🌐 XML과 HTML은 왜 반정형일까?

HTML을 보면 이런 태그가 있지.

HTML
<h1>제목</h1>
<p>본문입니다.</p>

완전한 행·열 구조는 아니지만,

<h1>은 제목이고 <p>는 문단이라는 구조 정보가 존재해.

그래서 반정형 데이터로 볼 수 있어.

XML도 마찬가지야.

XML
<person>
    <name>민수</name>
    <age>25</age>
</person>

<name>, <age>라는 태그가 데이터의 의미를 표현하지.

따라서 반정형 데이터의 핵심은:

행과 열은 고정되어 있지 않더라도 데이터를 설명하는 구조적 표식이 존재한다.

이거야.

📝 비정형 데이터 읽기

비정형 데이터에는 대표적으로 다음이 있어.

텍스트, 이미지, 음성, 영상

이들은 그대로는 일반적인 표 형태의 분석에 넣기 어려워.

예를 들어 고객 리뷰가 있다고 해보자.

배송은 빨랐는데 제품 포장이 조금 아쉬웠어요.

여기에는 배송=긍정, 포장=부정 같은 열이 원래 존재하지 않아.

우리가 분석을 위해 구조를 만들어야 해.

텍스트 파일 읽기

일반 텍스트 파일 자체는 Python으로 다음처럼 읽을 수 있어.

Python
실행됨
with open("review.txt", "r", encoding="utf-8") as f:
    text = f.read()

이때 결과는 DataFrame이 아니라 **문자열(str)**이야.

Python
실행됨
type(text)

를 확인하면 문자열 형태라는 걸 볼 수 있어.

여러 줄을 리스트로 읽고 싶다면:

Python
실행됨
with open("review.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

하지만 중요한 건 코드를 외우는 것보다 읽은 뒤 무엇이 생기는지야.

CSV
↓
DataFrame
↓
열을 바로 분석

텍스트
↓
문자열
↓
전처리·특징 추출
↓
분석 가능한 구조

이 차이가 핵심이야.

🔬 파일 확장자만 보고 판단하면 위험한 이유

여기서 시험 공부할 때 자주 생기는 오해가 하나 있어.

“CSV는 무조건 정형, JSON은 무조건 반정형이다.”

대표적으로 그렇게 분류하기는 하지만, 더 본질적인 기준은 데이터 구조야.

예를 들어 JSON도 아주 단순하게 작성돼 있으면:

JSON
[
  {"id": 1, "age": 20},
  {"id": 2, "age": 21},
  {"id": 3, "age": 25}
]

DataFrame으로 매우 쉽게 바꿀 수 있어.

반대로 중첩이 깊다면:

JSON
{
  "user": {
    "profile": {
      "address": {
        "city": "Seoul"
      }
    }
  }
}

표로 만들기 전에 구조를 풀어내는 작업이 필요하지.

그래서 판단 순서는 이렇게 잡는 게 정확해.

① 행·열 구조가 고정되어 있는가?
        │
      Yes
        ↓
     정형 데이터

      No
        ↓
② key·태그 등 구조 정보가 있는가?
        │
      Yes
        ↓
    반정형 데이터

      No
        ↓
    비정형 데이터

이 분류법을 잡아두면 암기량이 크게 줄어.

🧠 실기에서 중요한 pandas 읽기 패턴

이 단원에서 코드를 전부 따로 외우려고 하면 오히려 헷갈려.

하나의 패턴으로 기억해.

Python
실행됨
pd.read_무엇(...)

대표적인 연결은:

Python
실행됨
pd.read_csv()
pd.read_excel()
pd.read_json()
pd.read_sql()

그리고 데이터를 읽으면 거의 항상 다음 행동으로 이어져.

Python
실행됨
df.head()
df.shape
df.info()
df.dtypes

즉 실전 사고 흐름은:

파일 형식 확인
    ↓
적절한 read 함수
    ↓
DataFrame 생성
    ↓
데이터 구조 확인
    ↓
결측치·자료형 확인
    ↓
전처리

이 순서를 몸에 익히는 게 좋아.

🎯 시험용 핵심 압축
정형 데이터

이미 행 × 열 형태로 구조가 결정되어 있어.

대표적으로:

CSV
Excel
관계형 DB 테이블

Python에서는 주로:

Python
실행됨
pd.read_csv()
pd.read_excel()
pd.read_sql()
반정형 데이터

고정된 행·열은 아니지만 key나 태그가 구조를 알려줘.

대표적으로:

JSON
XML
HTML

대표적인 Python 처리:

Python
실행됨
pd.read_json()
json.load()
비정형 데이터

일정한 구조가 없어.

대표적으로:

텍스트
이미지
음성
영상

분석하려면 보통 전처리 또는 특징 추출을 통해 구조화하는 단계가 필요해.

🧠 Ailey의 기억 공식

시험장에서 이 세 문장만 복원해도 돼.

정형은 표가 있다.

반정형은 표를 만들 구조가 있다.

비정형은 구조부터 만들어야 한다.

그리고 Python 데이터 읽기는:

read → 확인 → 전처리

Python
실행됨
df = pd.read_csv("data.csv")

df.head()
df.shape
df.info()

여기까지 자연스럽게 나오면 이 단원의 기본 뼈대는 제대로 잡힌 거야.

╭─ 📍 빅데이터분석기사 실기 학습 현황
🎯 현재 단원 · 1-1-1-1. 정형·반정형·비정형 데이터 읽기
🧠 학습 상태 · 개념 구조와 기본 읽기 코드 학습 완료
➡️ 주 진행 방향 · 데이터 읽기 실전 패턴 고정하기

[데이터 읽기 · 다음 학습]

a. 🚀 1-1-1-1 정형 데이터 읽기 실전 코드 깊게 학습
b. 🔎 CSV read_csv() 옵션·인코딩·결측치 깊게 보기
c. 🔗 JSON을 DataFrame으로 바꾸는 과정 연결하기
d. 🌱 파일을 읽은 직후 해야 하는 데이터 점검 탐구
e. 🗺️ 빅데이터분석기사 실기 전체 학습 지도 보기
f. 🛠️ 현재 학습 경로 다시 설계하기
╰─

2026.08.26 (Wed) 18:09:00 KST
