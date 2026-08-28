# 4-2-2-1. 결과와 산출물 저장

> **공식 학습 범위**: 빅데이터 분석 실무의 「데이터 모형 평가 작업 > 분석결과 활용하기」에 따라 최종모형 또는 분석결과를 저장할 수 있어야 한다.

이 레슨의 세 토픽은 **예측·분석결과 저장**, **모형 산출물 저장**, **저장 결과 검증**이다. 저장은 단순히 `write_csv`나 `to_csv`를 한 번 실행하는 일이 아니다. 어떤 행의 결과인지 식별할 수 있고, 제출 규격을 만족하며, 다시 읽었을 때 값과 자료형이 유지되고, 모형을 재사용할 때 동일한 전처리까지 적용되도록 만드는 과정이다.

---

## 1. 먼저 산출물을 구분한다

분석이 끝난 뒤 저장할 대상은 크게 세 종류다.

| 산출물 | 대표 내용 | 핵심 검증 |
|---|---|---|
| 결과 데이터 | 행 식별자, 예측값, 예측확률, 요약통계 | 행 수·순서·열 이름·결측·값 범위 |
| 모형 산출물 | 학습된 모형, 전처리기, 입력 열 목록 | 다시 불러오기·예측 일치·필요 객체 포함 |
| 재현 정보 | 데이터 분할 기준, 매개변수, 지표, 생성 시각 | 결과가 어떤 조건에서 만들어졌는지 확인 |

문제에서 지정한 파일 이름·열 이름·저장 위치가 있다면 그 지시가 가장 우선이다. 지시가 없는 세부를 임의로 꾸며 내지 말고 실제 생성한 구조를 점검한다.

---

## 2. 토픽 ① 예측·분석결과 저장

### 2.1 행 식별자를 기준으로 결과를 만든다

예측은 원본 평가 데이터의 행과 정확히 대응해야 한다. 전처리 과정에서 정렬이나 필터가 바뀌었을 수 있으므로 가능하면 식별자를 별도로 보존한다. 단순히 예측 배열만 파일로 쓰면 누가 누구의 결과인지 확인하기 어렵다.

```python
import pandas as pd
import numpy as np

test = pd.DataFrame({
    "customer_id": ["C103", "C101", "C102"],
    "age": [44, 28, 35],
    "visits": [2, 8, 5]
})

# 실제 시험에서는 학습된 모형의 predict 또는 predict_proba 결과를 사용한다.
prob = np.array([0.31, 0.82, 0.56])
submission = pd.DataFrame({
    "customer_id": test["customer_id"].to_numpy(),
    "probability": prob
})

assert len(submission) == len(test)
assert submission["customer_id"].tolist() == test["customer_id"].tolist()
assert submission["probability"].between(0, 1).all()
print(submission)
```

중요한 점은 원래 행 순서를 유지했다는 것이다. 평가 데이터의 정답 열이 없더라도 식별자와 예측값의 대응은 검증할 수 있다. 문제에서 식별자 열을 제출하지 말라고 했다면 최종 파일에서 제외하되, 생성 직전까지 대응 관계를 내부적으로 보존하는 편이 안전하다.

### 2.2 CSV 저장 옵션을 명시한다

Python에서는 보통 다음처럼 저장한다.

```python
from pathlib import Path
import pandas as pd

result = pd.DataFrame({"pred": [0, 1, 1, 0]})
output_path = Path("result.csv")

result.to_csv(output_path, index=False, encoding="utf-8")

assert output_path.exists()
print(output_path.read_text(encoding="utf-8"))
```

예상 파일은 다음과 같다.

```text
pred
0
1
1
0
```

`index=False`를 빼면 `0, 1, 2, 3` 같은 데이터프레임 인덱스가 불필요한 첫 열로 저장될 수 있다. 다만 문제에서 인덱스를 제출하라고 명시했다면 지시에 따른다. 인코딩도 환경과 제출 요구에 맞춘다. 숫자 열을 문자열로 임의 변환하거나 천 단위 구분 쉼표를 넣으면 채점 프로그램이 읽지 못할 수 있다.

R에서는 다음처럼 동일한 구조를 만들 수 있다.

```r
result <- data.frame(pred=c(0, 1, 1, 0))
write.csv(result, "result_r.csv", row.names=FALSE, fileEncoding="UTF-8")

check <- read.csv("result_r.csv", stringsAsFactors=FALSE)
stopifnot(nrow(check) == 4)
stopifnot(identical(names(check), "pred"))
stopifnot(all(check$pred == result$pred))
print(check)
```

R의 `write.csv`도 `row.names=FALSE`를 명시하지 않으면 행 이름 열이 추가될 수 있다.

### 2.3 확률·클래스·회귀값을 혼동하지 않는다

분류 문제에서 요구값이 클래스인지 확률인지 확인한다. `predict`는 대개 클래스, `predict_proba`는 클래스별 확률을 반환하지만 모형과 라이브러리 인터페이스에 따라 확인이 필요하다. 이진 분류 확률 배열에서 어느 열이 양성인지 `classes_`로 확인할 수 있다.

```python
import numpy as np
from sklearn.linear_model import LogisticRegression

X = np.array([[0], [1], [2], [3], [4], [5]])
y = np.array([0, 0, 0, 1, 1, 1])
model = LogisticRegression().fit(X, y)

proba_all = model.predict_proba(np.array([[1.5], [3.5]]))
positive_col = list(model.classes_).index(1)
positive_prob = proba_all[:, positive_col]

print("classes:", model.classes_)
print("positive probability:", positive_prob)
assert proba_all.shape == (2, 2)
assert np.allclose(proba_all.sum(axis=1), 1.0)
```

무조건 두 번째 열이 양성이라고 외우기보다 클래스 순서를 확인한다. 회귀 문제에는 확률이 아니라 연속형 예측값을 저장한다.

### 2.4 결측과 무한대, 자릿수를 점검한다

결과 열에 `NaN`, 양·음의 무한대가 있으면 저장 자체는 되더라도 유효한 답안이 아닐 수 있다.

```python
import numpy as np
import pandas as pd

result = pd.DataFrame({"prediction": [10.2, 11.7, 9.8]})
values = result["prediction"].to_numpy(dtype=float)

assert np.isfinite(values).all(), "예측값에 결측 또는 무한대가 있습니다."

# 문제에서 소수 둘째 자리까지 요구한 경우에만 출력 단계에서 반올림
result["prediction"] = result["prediction"].round(2)
print(result)
```

평가지표 계산 전에 예측값을 반올림하면 결과가 달라질 수 있다. 계산은 원 정밀도로 하고 제출 형식이 요구될 때 마지막 출력에서 반올림한다.

---

## 3. 토픽 ② 모형 산출물 저장

### 3.1 모형만이 아니라 전처리까지 하나로 묶는다

학습 때 표준화와 원-핫 인코딩을 했는데 모형 객체만 저장하면 새 데이터에서 같은 변환을 재현하기 어렵다. 가능한 경우 전처리기와 모형을 파이프라인으로 묶어 저장한다.

```python
import numpy as np
from pathlib import Path
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
import joblib

X = np.array([[10, 1], [12, 2], [15, 2], [24, 5], [28, 6], [31, 7]])
y = np.array([0, 0, 0, 1, 1, 1])

pipeline = Pipeline([
    ("scale", StandardScaler()),
    ("model", LogisticRegression())
])
pipeline.fit(X, y)

artifact_path = Path("classification_pipeline.joblib")
joblib.dump(pipeline, artifact_path)
loaded = joblib.load(artifact_path)

before = pipeline.predict_proba(X)[:, 1]
after = loaded.predict_proba(X)[:, 1]

assert artifact_path.exists() and artifact_path.stat().st_size > 0
assert np.allclose(before, after)
print("재로딩 예측 일치:", np.allclose(before, after))
```

이 예시는 패키지가 제공되는 실행환경을 전제로 한다. 실기 체험환경에서는 추가 설치가 제한될 수 있으므로 실제 제공 패키지와 문제 지시를 먼저 확인한다. 패키지 버전이 다르면 직렬화 파일 호환성이 보장되지 않을 수 있다. 따라서 실제 업무에서는 사용 언어·라이브러리 환경 정보도 함께 기록한다.

### 3.2 파일 형식의 역할을 구분한다

- CSV는 표 형태 결과를 사람이 확인하고 다른 도구에서 읽기에 편하지만 학습된 객체 구조를 보존하지 않는다.
- JSON은 구조화된 설정·요약 통계를 저장하기 좋지만 모든 모형 객체를 그대로 표현하지 못한다.
- 언어별 직렬화 형식은 모형 객체를 보존할 수 있지만 신뢰할 수 없는 파일을 불러오면 위험하며 환경 호환성을 확인해야 한다.
- 단순한 계수와 입력 열 목록은 공개 형식으로 별도 보존하면 검토가 쉬워진다.

직렬화된 객체는 **신뢰할 수 있는 출처에서 생성한 파일만** 읽는다. 일부 직렬화 형식은 로드 과정에서 코드를 실행할 수 있으므로 이메일이나 임의 저장소에서 받은 파일을 그대로 열지 않는다.

### 3.3 R 모형 저장과 재로딩

R의 기본 함수로도 모형을 저장하고 예측을 비교할 수 있다.

```r
train <- data.frame(
  y=c(10, 13, 16, 20, 24),
  x=c(1, 2, 3, 4, 5)
)
fit <- lm(y ~ x, data=train)
before <- predict(fit, newdata=train)

saveRDS(fit, "linear_model.rds")
loaded <- readRDS("linear_model.rds")
after <- predict(loaded, newdata=train)

stopifnot(file.exists("linear_model.rds"))
stopifnot(isTRUE(all.equal(before, after)))
print(after)
```

여기서도 파일 존재만 확인하면 부족하다. 다시 불러온 객체가 같은 입력에서 같은 출력을 내는지 검증해야 한다.

### 3.4 입력 스키마와 학습 조건을 함께 기록한다

모형 파일과 함께 최소한 다음 정보를 남기면 재사용 오류를 줄인다.

1. 목표변수와 입력 열 이름, 열 순서
2. 범주 수준과 결측 처리 방식
3. 학습·평가 분할 기준
4. 주요 매개변수와 난수 시드
5. 평가 지표와 계산 기준
6. 생성 시각과 데이터 기준 시점

단, 개인정보나 비밀키를 메타데이터에 넣지 않는다. 원본 데이터 경로에 사용자 이름이나 민감한 서버 주소가 포함되지 않도록 한다.

---

## 4. 토픽 ③ 저장 결과 검증

### 4.1 저장 후 반드시 다시 읽는다

검증의 기본 순서는 **존재 → 크기 → 재로딩 → 스키마 → 값**이다.

```python
from pathlib import Path
import pandas as pd
import numpy as np

expected = pd.DataFrame({
    "id": [11, 12, 13],
    "prediction": [0.125, 0.750, 0.500]
})
path = Path("checked_result.csv")
expected.to_csv(path, index=False, encoding="utf-8")

assert path.exists(), "파일이 생성되지 않았습니다."
assert path.stat().st_size > 0, "빈 파일입니다."

actual = pd.read_csv(path)
assert actual.shape == expected.shape
assert actual.columns.tolist() == expected.columns.tolist()
assert actual["id"].tolist() == expected["id"].tolist()
assert np.allclose(actual["prediction"], expected["prediction"])
assert actual["prediction"].notna().all()
print("검증 완료:", actual.shape, actual.columns.tolist())
```

`DataFrame.equals`는 자료형 차이에도 엄격하므로, 부동소수점은 `np.allclose`로 허용 오차를 두고 비교하는 것이 적절할 수 있다. 반면 식별자와 범주값은 정확히 일치해야 한다.

### 4.2 제출 전 체크리스트

- 파일 이름과 확장자가 문제 지시와 정확히 같은가?
- 지정한 디렉터리에 저장했는가?
- 행 수가 평가 데이터와 같은가?
- 열 개수, 열 이름, 열 순서가 요구 형식과 같은가?
- 불필요한 인덱스 열이 들어가지 않았는가?
- 예측값에 결측·무한대·범위 위반이 없는가?
- 분류 확률과 클래스 중 요구된 값을 저장했는가?
- CSV를 다시 읽었을 때 값이 유지되는가?

파일을 만들었다는 로그만 보고 제출하지 않는다. 마지막 한 줄은 언제나 재로딩 검증으로 끝내는 습관이 좋다.

### 4.3 흔한 실패 원인과 대응

| 증상 | 원인 후보 | 확인·대응 |
|---|---|---|
| 행 수가 다름 | 결측 제거 또는 필터 후 인덱스 불일치 | 원 평가 식별자와 병합해 대응 확인 |
| 첫 열이 불필요함 | 데이터프레임 인덱스 저장 | `index=False` 또는 `row.names=FALSE` |
| 확률이 반대로 보임 | 클래스 열 순서를 오해 | `classes_` 등으로 양성 열 확인 |
| 다시 읽으면 한글이 깨짐 | 인코딩 불일치 | 요구 환경에 맞는 인코딩으로 저장·재로딩 |
| 모형 로딩 후 예측이 달라짐 | 전처리 누락·열 순서 변화 | 파이프라인 저장, 입력 스키마 비교 |
| 제출 파일이 없음 | 현재 작업 경로 오해 | 절대·상대 경로와 `exists()` 확인 |

---

## 5. 시험 함정

1. `to_csv()` 기본값으로 불필요한 인덱스 열을 추가한다.
2. 분류 클래스 대신 확률을, 또는 확률 대신 클래스를 제출한다.
3. 양성 클래스가 어느 열인지 확인하지 않고 확률 열을 고른다.
4. 평가 데이터 정렬 후 원 식별자 순서와 어긋난다.
5. 파일 이름의 대소문자·확장자·경로를 문제와 다르게 쓴다.
6. 저장 전에만 확인하고 실제 파일을 다시 읽지 않는다.
7. 전처리기 없이 모형 객체만 저장해 새 데이터 예측이 달라진다.
8. 제공되지 않은 패키지를 설치하려다 시간을 잃는다.
9. 직렬화 파일을 버전과 출처 확인 없이 불러온다.
10. 지표 계산 전에 예측값을 반올림한다.

---

## 6. 확인 문제

### 문제 1

`pandas.DataFrame.to_csv("answer.csv")`로 저장했더니 첫 번째 열에 0, 1, 2가 들어갔다. 원인과 해결 방법은?

**정답**: 데이터프레임 인덱스가 함께 저장된 것이다. 문제에서 요구하지 않으면 `index=False`로 저장한다.

### 문제 2

이진 분류의 `predict_proba` 결과가 두 열이다. 무조건 두 번째 열을 제출해도 되는가?

**정답**: 안 된다.

**해설**: 각 열이 어떤 클래스 확률인지 모형의 클래스 순서로 확인하고, 문제에서 요구한 클래스의 확률을 선택해야 한다.

### 문제 3

CSV 파일 존재와 크기가 0보다 큼을 확인했다. 저장 검증이 끝났는가?

**정답**: 아니다.

**해설**: 다시 읽어서 행 수, 열 이름·순서, 식별자 대응, 결측·무한대, 값 일치를 확인해야 한다.

### 문제 4

표준화 후 학습한 모형을 저장하려 한다. 모형 객체만 저장할 때 생길 수 있는 문제는?

**정답**: 새 입력에 동일한 표준화를 적용하지 못하거나 다른 방식으로 적용해 예측이 달라질 수 있다. 전처리와 모형을 파이프라인으로 묶거나 전처리 객체와 설정을 함께 보존한다.

### 문제 5

예측값을 소수 둘째 자리로 제출해야 한다. 어느 시점에 반올림하는 것이 안전한가?

**정답**: 지표 계산과 모형 비교는 원 정밀도로 끝내고, 제출 파일을 만드는 마지막 출력 단계에서 요구 자릿수로 반올림한다.

---

## 7. 최종 요약

- **예측·분석결과 저장**은 식별자 대응, 요구 열, 행 순서, 확률·클래스 구분을 보존하는 작업이다.
- **모형 산출물 저장**은 모형뿐 아니라 전처리와 입력 스키마, 재현 조건까지 고려한다.
- **저장 결과 검증**은 파일 존재 확인에서 끝나지 않고 재로딩 후 구조와 값을 비교해야 완성된다.
- 제출 규격이 있으면 파일 이름·경로·열 이름·열 순서·인덱스 포함 여부를 그대로 따른다.
- 불확실한 환경이나 패키지 버전을 가정하지 말고, 제공된 실행환경에서 실제 저장과 재로딩을 확인한다.
