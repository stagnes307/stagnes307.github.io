# 5-1-2-1. 코드 실행·저장·오류 대응

> **학습 위치**: 이 레슨은 공식 실기 수험 안내를 바탕으로 시험 실행환경 적응을 돕는 보충 학습이다. 실제 버튼 이름과 화면 구성은 변경될 수 있으므로 최신 안내와 시험 화면을 최종 기준으로 삼는다.

이 레슨의 세 토픽은 **1분 실행 제한**, **코드 저장과 초기화**, **오류 메시지 확인**이다. 시험 코드는 정답을 계산하는 것만으로 끝나지 않는다. 제한 안에 실행되고, 중간 작업을 잃지 않도록 저장하며, 오류가 발생했을 때 원인을 좁혀 복구하고, 마지막 결과를 다시 검증해야 한다.

---

## 1. 실행 루프를 짧게 만든다

실전에서 안전한 기본 루프는 다음과 같다.

1. 문제와 입력·출력 요구를 읽는다.
2. 데이터 일부와 구조를 확인한다.
3. 전처리 한 단계만 작성해 실행한다.
4. 행 수·열 수·결측·자료형을 검증한다.
5. 모형 또는 통계 계산을 실행한다.
6. 결과 범위와 제출 형식을 확인한다.
7. 코드를 저장하고 최종 실행한다.

전체 풀이를 한 번에 길게 작성한 뒤 처음 실행하면 오류 위치가 많아진다. “읽기 → 확인 → 변환 → 확인 → 계산 → 확인”처럼 작은 단위로 실행하면 어느 단계에서 잘못되었는지 알기 쉽다.

---

## 2. 토픽 ① 1분 실행 제한

### 2.1 제한은 코드 한 번의 실행을 기준으로 관리한다

수험 안내에 제시된 **1분 실행 제한**을 고려해, 한 번의 실행이 오래 걸리는 구조를 피한다. 실제 제한 적용 방식과 메시지는 시험 화면을 따른다. 핵심은 제한을 늘리는 방법을 찾는 것이 아니라 각 실행을 짧고 검증 가능하게 만드는 것이다.

시간을 많이 쓰는 대표 원인은 다음과 같다.

- 지나치게 큰 매개변수 후보를 전부 탐색한다.
- 교차검증 반복 수와 폴드 수를 불필요하게 크게 잡는다.
- 반복문 안에서 파일을 계속 읽거나 같은 전처리를 반복한다.
- 전체 데이터·행렬·로그를 화면에 모두 출력한다.
- 종료 조건이 잘못된 반복문을 실행한다.
- 데이터 크기를 확인하지 않고 복잡한 모형부터 학습한다.

### 2.2 먼저 데이터 크기와 실행 구간을 잰다

Python에서는 표준 기능으로 구간 시간을 확인할 수 있다.

```python
from time import perf_counter
import pandas as pd

df = pd.DataFrame({
    "group": ["A", "B", "A", "B"] * 2500,
    "value": range(10000)
})

start = perf_counter()
answer = df.groupby("group", as_index=False)["value"].mean()
elapsed = perf_counter() - start

print(answer)
print(f"집계 시간: {elapsed:.4f}초")
assert len(answer) == 2
```

R에서는 `system.time()`을 사용할 수 있다.

```r
df <- data.frame(
  group=rep(c("A", "B"), 5000),
  value=seq_len(10000)
)

timing <- system.time({
  answer <- aggregate(value ~ group, data=df, FUN=mean)
})
print(answer)
print(timing)
stopifnot(nrow(answer) == 2)
```

시간 측정 자체가 목적은 아니다. 어느 단계가 느린지 구분해 필요한 부분만 줄이는 것이 목적이다.

### 2.3 작은 표본으로 코드 구조를 먼저 검증한다

전체 데이터 학습 전에 작은 행으로 자료형·함수 호출·출력 구조를 확인할 수 있다. 단, 최종 답은 반드시 전체 요구 데이터에서 다시 계산해야 한다.

```python
import pandas as pd

df = pd.DataFrame({
    "x": range(1000),
    "category": ["A", "B"] * 500
})

probe = df.head(20).copy()
probe_result = probe.groupby("category")["x"].mean()
print(probe_result)
assert probe_result.index.isin(["A", "B"]).all()

# 구조 확인 후 전체 데이터로 최종 계산
final_result = df.groupby("category")["x"].mean()
assert final_result.notna().all()
print(final_result)
```

표본 결과를 최종 답으로 제출하지 않도록 `probe_`와 `final_`처럼 이름을 분리한다.

### 2.4 탐색 범위를 현실적으로 제한한다

무작정 많은 조합을 탐색한다고 좋은 답이 되는 것은 아니다. 먼저 단순 기준모형을 만들고, 소수의 의미 있는 후보만 비교한다.

```python
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

X, y = make_classification(n_samples=500, n_features=10, random_state=17)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=17, stratify=y
)

scores = {}
for depth in [None, 5, 10]:
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=depth,
        random_state=17,
        n_jobs=1
    )
    model.fit(X_train, y_train)
    scores[str(depth)] = accuracy_score(y_test, model.predict(X_test))

print(scores)
assert len(scores) == 3
```

후보 수를 정할 때 데이터 크기와 실행 제한을 고려한다. 무거운 작업을 병렬화하려고 임의로 많은 프로세스를 만들면 오히려 환경 자원과 제한에 문제를 일으킬 수 있다.

### 2.5 출력량을 제한한다

`print(df)`로 큰 데이터 전체를 출력하지 않는다. 필요한 정보만 확인한다.

```python
print(df.shape)
print(df.head(3))
print(df.dtypes)
print(df.isna().sum().sort_values(ascending=False).head(10))
```

---

## 3. 토픽 ② 코드 저장과 초기화

### 3.1 실행과 저장을 같은 것으로 생각하지 않는다

코드를 실행했다고 자동으로 안전하게 저장되었다고 가정하지 않는다. 시험 화면이 제공하는 저장 동작과 저장 상태 표시를 확인한다. 실제 버튼 이름, 자동 저장 여부, 저장 범위는 최신 화면 지시를 따른다.

저장 시점은 다음처럼 잡는다.

- 입력 파일을 정상적으로 읽은 뒤
- 핵심 전처리를 완료하고 검증한 뒤
- 모형 또는 통계 계산이 성공한 뒤
- 제출 파일 생성과 검증을 완료한 뒤
- 큰 수정이나 초기화 전에

코드에 구역 제목을 붙이면 복구가 쉽다.

```python
# 1. 라이브러리
import pandas as pd

# 2. 데이터 읽기
# train = pd.read_csv("화면에 제시된 경로")

# 3. 전처리

# 4. 계산 또는 모형

# 5. 결과 검증과 저장
```

### 3.2 중간 객체 이름을 명확하게 유지한다

`df`, `df2`, `df3`만 반복하면 어느 단계인지 혼동한다. `train_raw`, `train_clean`, `X_train`, `prediction`, `submission`처럼 역할이 드러나는 이름을 사용한다. 원본 객체를 바로 덮어쓰지 않으면 잘못된 변환에서 돌아오기 쉽다.

```python
import pandas as pd

train_raw = pd.DataFrame({
    "age": [21, None, 35],
    "target": [0, 1, 1]
})
train_clean = train_raw.copy()
train_clean["age"] = train_clean["age"].fillna(train_clean["age"].median())

assert train_raw["age"].isna().sum() == 1
assert train_clean["age"].isna().sum() == 0
```

원본을 보존했기 때문에 대체 기준이 틀렸다면 처음부터 데이터를 다시 읽지 않고 수정할 수 있다.

### 3.3 초기화 전에 보존할 것을 확인한다

초기화는 꼬인 상태를 정리할 수 있지만 메모리의 객체와 저장하지 않은 코드를 잃을 수 있다. 다음 순서를 지킨다.

1. 현재 코드가 저장되었는지 확인한다.
2. 필요한 결과 파일이 실제로 생성되었는지 확인한다.
3. 초기화 후 다시 실행할 셀·코드 순서를 확인한다.
4. 화면이 명시한 초기화 범위를 읽는다.
5. 초기화 후 처음부터 순서대로 재실행한다.

초기화 전에는 오류 종류와 변수 상태를 먼저 확인한다. 실행 순서가 꼬여 메모리 객체에 의존한다면 저장 후 초기화하고 위에서부터 재실행해 재현성을 검증한다.

### 3.4 재시작 가능한 코드를 만든다

재시작 가능한 코드는 숨은 수동 단계를 줄인다. 예를 들어 변수가 이미 존재할 때만 동작하는 코드를 피하고, 입력 읽기부터 출력 저장까지 순서가 명확해야 한다.

```python
from pathlib import Path
import pandas as pd

def build_result(input_path, output_path):
    data = pd.read_csv(input_path)
    required = {"group", "value"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"필수 열 누락: {sorted(missing)}")

    result = data.groupby("group", as_index=False)["value"].mean()
    result.to_csv(output_path, index=False)
    return result

# 실제 시험에서는 화면이 제시한 경로로 호출한다.
```

---

## 4. 토픽 ③ 오류 메시지 확인

### 4.1 마지막 줄만 보지 말고 오류 유형과 최초 원인을 본다

Python 오류는 보통 traceback 마지막에 오류 유형과 메시지가 있고, 위쪽에 호출 경로가 있다. 먼저 자신이 작성한 코드의 가장 가까운 줄을 찾는다. R도 오류가 발생한 함수와 메시지를 읽고, 경고와 오류를 구분한다.

| 오류 유형·증상 | 흔한 원인 | 첫 확인 |
|---|---|---|
| `FileNotFoundError` | 경로·파일명 불일치 | 화면에 제시된 정확한 경로, 현재 작업경로 |
| `KeyError` | 열 이름 오탈자·공백 | `df.columns.tolist()` |
| `NameError` | 변수 미생성·실행 순서 오류 | 변수를 만드는 코드가 실행되었는지 |
| `TypeError` | 잘못된 자료형 또는 인자 | `type()`, 함수 호출 인자 |
| `ValueError` | 형태·값 범위 불일치 | `shape`, 고유값, 결측 |
| 메모리·시간 문제 | 데이터 복사·탐색 과다 | 행·열 수, 반복 구조, 후보 수 |

### 4.2 열 이름 오류를 체계적으로 찾는다

```python
import pandas as pd

df = pd.DataFrame({" age ": [20, 30], "TARGET": [0, 1]})
print(repr(df.columns.tolist()))

# 의미가 확인된 뒤 공백만 정리
df.columns = df.columns.str.strip()
assert "age" in df.columns
print(df.columns.tolist())
```

대소문자를 무조건 바꾸거나 공백을 전부 제거하면 문제에서 요구한 원래 열 이름과 달라질 수 있다. 먼저 실제 문자열을 `repr` 형태로 확인한다.

### 4.3 자료형 오류를 값과 함께 본다

```python
import pandas as pd

s = pd.Series(["10", "20", "unknown", "30"])
numeric = pd.to_numeric(s, errors="coerce")

bad = s[numeric.isna() & s.notna()]
print("변환 실패값:", bad.tolist())
assert bad.tolist() == ["unknown"]
```

무조건 `errors="coerce"`로 끝내면 잘못된 값이 결측으로 숨어 버린다. 어떤 값이 변환되지 않았는지 확인하고 문제 조건에 맞게 처리한다.

### 4.4 형태 불일치를 바로 검증한다

```python
import numpy as np

X_train = np.zeros((80, 5))
y_train = np.zeros(79)

if len(X_train) != len(y_train):
    print("행 수 불일치:", X_train.shape, y_train.shape)
```

모형 학습 전에 `X_train.shape`, `y_train.shape`, 열 목록을 출력하면 긴 오류를 예방할 수 있다.

### 4.5 오류를 숨기는 광범위한 예외 처리를 피한다

다음은 위험하다.

```python
try:
    result = 1 / 0
except Exception:
    pass
```

오류가 사라진 것이 아니라 숨겨졌다. 복구 가능한 오류만 구체적으로 처리하고 메시지를 남긴다.

```python
from pathlib import Path

path = Path("input.csv")
try:
    text = path.read_text(encoding="utf-8")
except FileNotFoundError as error:
    print("입력 경로를 다시 확인하세요:", error.filename)
```

---

## 5. 오류 복구 5단계

1. **멈춘 단계 확인**: 읽기·변환·학습·예측·저장 중 어디인가?
2. **오류 유형 읽기**: 파일, 이름, 자료형, 값, 형태 중 어느 범주인가?
3. **최소 상태 출력**: `shape`, 열 이름, 자료형, 결측, 고유값 일부만 본다.
4. **한 가지 원인만 수정**: 여러 줄을 동시에 바꾸지 않는다.
5. **앞 단계 검증 재실행**: 수정 후 최종 줄만 실행하지 말고 관련 전처리부터 다시 확인한다.

R에서는 `str()`, `dim()`, `names()`, `summary()`, `is.na()`가 핵심 진단 도구다. Python에서는 `type()`, `shape`, `columns`, `dtypes`, `head()`, `isna()`를 먼저 쓴다.

---

## 6. 시험 함정

1. 코드를 모두 작성한 뒤 처음으로 전체 실행한다.
2. 큰 데이터 전체를 출력해 오류 메시지를 놓친다.
3. 작은 표본의 시험 결과를 전체 데이터 결과로 착각한다.
4. 매개변수 후보를 과도하게 늘려 실행 제한을 넘긴다.
5. 실행 성공을 저장 성공으로 오해한다.
6. 저장하지 않은 상태에서 초기화한다.
7. 셀 실행 순서에 의존해 위에서부터 재실행하면 실패한다.
8. 오류 유형을 읽지 않고 코드를 여러 군데 동시에 바꾼다.
9. `except Exception: pass`로 실제 오류를 숨긴다.
10. 출력 파일 생성 후 재로딩 검증을 생략한다.

---

## 7. 확인 문제

### 문제 1

실행 제한을 피하기 위해 가장 먼저 해야 할 일은 모든 작업을 병렬화하는 것인가?

**정답**: 아니다.

**해설**: 데이터 크기와 느린 구간을 확인하고, 중복 계산·과도한 탐색·불필요한 출력을 줄인다. 임의 병렬화는 자원 문제를 만들 수 있다.

### 문제 2

작은 표본 20행에서 코드가 정상 실행되었다. 그 결과를 최종 제출해도 되는가?

**정답**: 아니다.

**해설**: 표본은 코드 구조와 자료형을 확인하는 용도다. 최종 답은 문제에서 요구한 전체 데이터로 다시 계산하고 검증한다.

### 문제 3

초기화 전에 확인할 두 가지를 쓰시오.

**정답 예시**: 현재 코드 저장 여부, 필요한 결과 파일 생성 여부를 확인한다. 또한 초기화 범위와 재실행 순서를 확인해야 한다.

### 문제 4

`KeyError: 'age'`가 발생했다. 첫 진단은 무엇인가?

**정답**: 실제 열 이름을 `df.columns.tolist()` 또는 `repr(df.columns.tolist())`로 확인해 오탈자, 대소문자, 앞뒤 공백을 찾는다.

### 문제 5

모든 오류를 `except Exception: pass`로 감싸면 코드가 안전해지는가?

**정답**: 아니다.

**해설**: 오류를 숨겨 잘못되거나 미생성된 결과를 제출할 수 있다. 복구할 오류만 구체적으로 처리하고 정상 결과를 별도로 검증한다.

---

## 8. 최종 요약

- **1분 실행 제한**에 대비해 실행 단위를 작게 나누고, 데이터 크기·느린 구간·탐색 범위·출력량을 관리한다.
- **코드 저장과 초기화**에서는 실행과 저장을 구분하고, 중요한 단계마다 저장하며 초기화 전에 코드와 산출물을 확인한다.
- **오류 메시지 확인**은 오류 유형, 발생 단계, 최소 상태 출력, 한 원인 수정, 재검증 순으로 진행한다.
- 작은 표본은 구조 점검에만 사용하고 최종 답은 전체 요구 데이터에서 다시 계산한다.
- 화면 동작은 최신 공식 안내를 따르되, 짧은 실행·명확한 저장·체계적인 오류 진단이라는 원칙은 변하지 않는다.
