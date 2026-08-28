# 5-2-2-1. 제2유형 예측 CSV 생성·제출

> **범위 안내**: 이 레슨은 한국데이터산업진흥원(K-DATA)의 공식 실기 체험환경과 「빅데이터분석기사 실기 체험 환경 가이드」를 근거로 한 제출 절차 보충 학습이다. 체험문제는 실제 출제 경향과 다를 수 있다. 실제 파일명, 경로, 목표 열, 예측 열, 평가 방법, 언어와 제공 패키지는 매 문제 화면과 최신 안내를 최종 기준으로 확인한다.

학습 토픽은 **예측 코드 작성**, **지정 파일·열 구성**, **CSV 제출 검증**이다. 제2유형은 화면에서 예측 숫자를 눈으로 확인하는 문제가 아니다. 학습 데이터로 모형을 만들고 평가 데이터 행마다 예측한 뒤, 요구 스키마를 가진 CSV 파일을 지정 위치에 생성하고 제출해야 끝난다.

---

## 1. 공식 가이드가 제시하는 CSV 규칙

공식 체험환경 가이드는 제2유형에서 예측 결과를 CSV로 생성하는 코드를 제출하며, 생성 파일이 다음 형식을 따라야 한다고 안내한다.

1. 예측 결과는 문제에서 지시한 칼럼명으로 생성한다.
2. 자동 생성되는 `index` 칼럼을 제거한다.
3. 답안 CSV에는 예측 결과 칼럼 1개만 둔다.
4. 문제에서 지시한 파일명으로 생성한다.
5. 별도의 디렉터리를 지정하지 않는다.

가이드의 체험 UI에서는 코드를 여러 번 제출할 수 있고, 마지막 제출 코드로 생성된 CSV가 채점 대상이라고 설명한다. 이 규칙을 “항상 `result.csv`와 `pred`를 써야 한다”는 뜻으로 오해하면 안 된다. 파일명과 예측 칼럼명은 각 문제의 지시가 결정한다.

---

## 2. 제출 계약부터 적는다

코딩 전에 학습·평가 파일의 정확한 경로, 목표 열, 식별 열, 예측 열, 출력 파일명, 평가 행 수를 문제에서 찾아 메모한다. `data/train.csv`, `target`, `id`, `pred`, `result.csv` 같은 문자열은 아래 연습 예시일 뿐이다. 실제 문제에서는 단 한 글자도 추측하지 않으며 `Pred`, `pred`, `prediction`을 서로 다른 열 이름으로 다룬다.

---

## 3. 토픽 ① 예측 코드 작성

### 3.1 안전한 작업 순서

제2유형 코드는 다음 일곱 단계로 나누면 오류 위치를 찾기 쉽다.

1. 학습·평가 파일 읽기
2. 행 수, 열 이름, 목표 열 존재 여부 확인
3. 식별 열과 목표 열을 분리
4. 학습 데이터로만 전처리 기준과 모형 학습
5. 평가 데이터에 같은 변환 적용
6. 평가 데이터 원래 행 순서대로 예측
7. 한 열짜리 제출 프레임 생성 후 CSV 저장

교차검증 점수가 좋아도 출력 행이 섞이거나 칼럼명이 틀리면 올바른 제출 파일이 아니다.

### 3.2 Python 실행 예제

아래 코드는 작은 데이터를 메모리에서 만들기 때문에 그대로 실행해 `result.csv`를 생성한다. 실제 시험에서는 예제 데이터 생성부만 화면에 제시된 `pd.read_csv()` 두 줄로 바꾼다. 사용하는 패키지가 환경에 제공되는지는 먼저 확인해야 하며, 특정 버전을 가정하지 않는다.

```python
from io import StringIO
from pathlib import Path
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

train_text = """id,age,amount,region,target
101,22,10.0,A,0
102,35,40.0,B,1
103,28,18.0,A,0
104,48,65.0,C,1
105,31,30.0,B,0
106,52,80.0,C,1
107,41,55.0,A,1
108,25,15.0,B,0
"""
test_text = """id,age,amount,region
201,29,21.0,A
202,46,60.0,C
203,33,35.0,B
"""

train = pd.read_csv(StringIO(train_text))
test = pd.read_csv(StringIO(test_text))

target_col = "target"       # 실제 문제 지시로 교체
id_col = "id"               # 실제 식별 열 지시로 교체
prediction_col = "pred"     # 실제 지정 칼럼명으로 교체
output_path = Path("result.csv")  # 실제 지정 파일명으로 교체

assert target_col in train.columns
assert target_col not in test.columns
assert id_col in train.columns and id_col in test.columns
assert len(test) > 0

feature_cols = [
    col for col in train.columns
    if col not in {target_col, id_col}
]
assert feature_cols == [col for col in test.columns if col != id_col]

X_train = train[feature_cols].copy()
y_train = train[target_col].copy()
X_test = test[feature_cols].copy()  # test의 원래 행 순서를 유지

numeric_cols = X_train.select_dtypes(include="number").columns.tolist()
categorical_cols = [c for c in feature_cols if c not in numeric_cols]

numeric_pipe = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scale", StandardScaler()),
])
categorical_pipe = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("onehot", OneHotEncoder(handle_unknown="ignore")),
])
preprocess = ColumnTransformer([
    ("num", numeric_pipe, numeric_cols),
    ("cat", categorical_pipe, categorical_cols),
])
model = Pipeline([
    ("preprocess", preprocess),
    ("model", LogisticRegression(max_iter=1000)),
])

model.fit(X_train, y_train)
prediction = model.predict_proba(X_test)[:, 1]

answer = pd.DataFrame({prediction_col: prediction})
assert answer.shape == (len(test), 1)
assert answer.columns.tolist() == [prediction_col]
assert answer[prediction_col].notna().all()

answer.to_csv(output_path, index=False)
print(answer)
print("saved:", output_path.resolve())
```

`id`를 출력 파일에 넣어야 하는 문제라면 위 예제를 그대로 쓰면 안 된다. 공식 체험 가이드의 해당 예시는 예측 열 1개만 요구하지만 실제 문제 화면의 제출 형식이 최우선이다. 이번 커리큘럼 토픽에서는 공식 가이드의 한 열 제출 절차를 연습한다.

### 3.3 R 실행 예제

다음 예제는 R 기본 `stats`의 로지스틱 회귀를 사용한다. 실제 데이터의 범주 수준과 결측 처리는 별도로 확인한다.

```r
train_text <- "id,age,amount,region,target
101,22,10.0,A,0
102,35,40.0,B,1
103,28,18.0,A,0
104,48,65.0,C,1
105,31,30.0,B,0
106,52,80.0,C,1
107,41,55.0,A,1
108,25,15.0,B,0"
test_text <- "id,age,amount,region
201,29,21.0,A
202,46,60.0,C
203,33,35.0,B"

train <- read.csv(text=train_text, stringsAsFactors=FALSE)
test <- read.csv(text=test_text, stringsAsFactors=FALSE)

target_col <- "target"       # 실제 지시로 교체
id_col <- "id"
prediction_col <- "pred"
output_path <- "result.csv"

stopifnot(target_col %in% names(train))
stopifnot(!(target_col %in% names(test)))
stopifnot(id_col %in% names(train), id_col %in% names(test))

train$region <- factor(train$region)
test$region <- factor(test$region, levels=levels(train$region))

model <- glm(target ~ age + amount + region,
             data=train, family=binomial())
prediction <- predict(model, newdata=test, type="response")

answer <- data.frame(prediction)
names(answer) <- prediction_col
stopifnot(nrow(answer) == nrow(test))
stopifnot(ncol(answer) == 1)
stopifnot(all(is.finite(answer[[prediction_col]])))

write.csv(answer, output_path, row.names=FALSE)
print(answer)
print(normalizePath(output_path))
```

범주형 수준이 평가 데이터에 새로 등장하면 R 예제가 오류를 낼 수 있다. 그때 임의로 행을 삭제하지 말고 학습·평가 범주 수준을 확인하고, 문제 환경에서 제공되는 전처리 방법으로 일관되게 처리한다.

---

## 4. 토픽 ② 지정 파일·열 구성

### 4.1 예측 길이와 순서를 보존한다

출력 행 수는 평가 데이터 행 수와 같아야 한다. 예측 전에 평가 데이터를 정렬하거나 결측 행을 제거하면 길이 또는 순서가 바뀐다. 모형 입력을 위한 복사본을 만들더라도 제출 예측은 원래 평가 행 순서와 대응해야 한다.

```python
expected_rows = len(test)
assert len(prediction) == expected_rows

answer = pd.DataFrame({prediction_col: prediction})
assert answer.index.equals(pd.RangeIndex(expected_rows))
```

식별 열이 있다면 검증용 사본에서 `test[id_col]`과 예측의 행 대응을 확인하되, 공식 가이드의 한 열 제출 예시에서는 실제 답안에 식별 열을 넣지 않는다.

### 4.2 자동 인덱스를 저장하지 않는다

Python `pandas`는 `to_csv()`의 기본 설정에서 인덱스를 파일에 쓸 수 있으므로 `index=False`를 명시한다. R `write.csv()`는 `row.names=FALSE`를 명시한다.

잘못된 Python 예:

```python
answer.to_csv("result.csv")  # 인덱스 열이 추가될 수 있음
```

안전한 예:

```python
answer.to_csv("result.csv", index=False)
```

“파일을 열어 보니 첫 열 제목이 비어 있다” 또는 `Unnamed: 0`이 보이면 자동 인덱스가 저장되었을 가능성이 크다.

### 4.3 별도 디렉터리를 만들지 않는다

공식 가이드의 체험 제출 형식은 답안 CSV의 별도 디렉터리 지정을 금지한다. 따라서 문제에서 `result.csv`를 요구한다면 `output/result.csv`, 절대경로, 임의 하위 폴더를 쓰지 않는다. 현재 작업 위치에 정확한 파일명으로 생성하고 존재 여부를 확인한다.

```python
assert output_path.parent == Path("."), "별도 디렉터리를 지정하지 않음"
assert output_path.name == "result.csv"  # 실제 지정 파일명으로 교체
```

---

## 5. 토픽 ③ CSV 제출 검증

저장 성공 메시지만으로는 부족하다. 저장한 파일을 다시 읽어 실제 스키마를 검사한다.

```python
import csv
from pathlib import Path
import pandas as pd

output_path = Path("result.csv")
prediction_col = "pred"
expected_rows = len(test)

assert output_path.is_file()

with output_path.open("r", encoding="utf-8", newline="") as file:
    reader = csv.reader(file)
    header = next(reader)
assert header == [prediction_col], f"헤더 불일치: {header}"

check = pd.read_csv(output_path)
assert check.shape == (expected_rows, 1), check.shape
assert check.columns.tolist() == [prediction_col]
assert not any(str(c).startswith("Unnamed") for c in check.columns)
assert check[prediction_col].notna().all()
print(check.head())
```

R에서도 다시 읽는다.

```r
check <- read.csv("result.csv", check.names=FALSE)
stopifnot(nrow(check) == nrow(test))
stopifnot(ncol(check) == 1)
stopifnot(identical(names(check), "pred"))  # 실제 지정 열로 교체
stopifnot(!any(is.na(check[[1]])))
print(head(check))
```

클래스·확률·연속값 중 문제에서 요구한 예측 종류를 확인한다. 확률이라면 다음처럼 범위를 점검한다.

```python
assert answer[prediction_col].between(0, 1).all()
```

연속값 회귀에는 이 검사를 적용하지 않는다.

---

## 6. 오류 대응과 시험 함정

| 증상 | 원인 후보 | 대응 |
|---|---|---|
| 학습과 평가 열 수가 다름 | 목표 열 포함 차이 또는 누락 | 목표·식별 열을 제외한 특징 목록 비교 |
| 범주 변환 오류 | 평가에 새 범주 | 학습 기준 변환과 미지 범주 처리 확인 |
| CSV가 두 열 | 자동 인덱스 포함 | `index=False` 또는 `row.names=FALSE` |
| 행 수 불일치 | 평가 행 제거·결합 오류 | 원본 평가 행 수와 예측 길이 비교 |

예측 결측은 입력·전처리를, 헤더 불일치는 문제의 지정 문자열을, 파일 없음은 현재 위치와 파일명 오타를 먼저 확인한다. 추가 함정도 점검한다.

- 학습·평가 데이터를 합쳐 목표값이나 분할 정보를 누출했다.
- 예측 후 값 기준으로 정렬해 평가 행 순서가 바뀌었다.
- 식별자를 숫자 특징으로 학습에 넣었다.
- 마지막 검증 뒤 코드를 바꾸고 재실행하지 않았다.
- 올바른 파일을 만들었지만 마지막 코드 제출을 완료하지 않았다.

---

## 7. 60초 제출 전 점검표

파일명, 현재 디렉터리, 한 개의 지정 헤더, 자동 인덱스 부재, 평가 데이터와 같은 행 수, 결측·무한값 부재, 요구한 예측 종류를 차례로 확인한다. 저장 파일을 다시 읽고 검증된 코드를 마지막으로 실행·제출한다.

---

## 8. 확인 문제

### 문제 1

평가 데이터가 500행이고 문제에서 `pred` 칼럼 한 개를 요구한다. 올바른 답안 구조는 무엇인가?

### 문제 2

CSV를 다시 읽었더니 열이 `Unnamed: 0`, `pred` 두 개다. 가장 가능성 높은 원인과 수정 방법은 무엇인가?

### 문제 3

모형 성능을 높이려고 예측값을 큰 순서로 정렬한 뒤 저장했다. 왜 위험한가?

## 정답과 해설

1. **정답: 500행 × 1열이고 헤더가 정확히 `pred`인 구조다.** 단, 실제 칼럼명은 해당 문제 지시를 따라야 한다.
2. **정답: 데이터프레임 인덱스를 함께 저장했을 가능성이 높다.** Python은 `index=False`, R은 `row.names=FALSE`로 다시 저장하고 재읽기 검증을 한다.
3. **정답: 예측 행과 평가 데이터 원래 행의 대응이 깨진다.** 점수가 좋아 보여도 다른 관측치의 예측으로 채점될 수 있으므로 원래 순서를 유지한다.

---

## 9. 요약

- **예측 코드 작성**은 입력 검증, 특징 정렬, 학습, 원래 행 순서 예측, 결과 프레임 생성의 순서로 진행한다.
- **지정 파일·열 구성**은 문제에서 준 파일명과 예측 칼럼명, 한 열 구조, 자동 인덱스 제거, 별도 디렉터리 금지를 지킨다.
- **CSV 제출 검증**은 파일을 다시 읽어 헤더·열 수·행 수·결측·예측 범위와 종류를 확인한다.
- 특정 파일명·열·패키지·버전을 고정 규칙으로 외우지 말고 실제 문제와 최신 공식 안내를 최종 기준으로 삼는다.
