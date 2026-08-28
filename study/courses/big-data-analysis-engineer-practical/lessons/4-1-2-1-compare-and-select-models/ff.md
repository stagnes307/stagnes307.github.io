# 4-1-2-1. 여러 모형의 공정한 비교

> **공식 학습 범위**: 선택한 평가지표를 이용하여 구축된 여러 모형을 같은 조건에서 비교하고, 목적에 맞는 최종 후보를 선택한다.

**Curriculum topics**: `동일 평가조건 설정` · `평가지표 비교` · `최종 후보 선택`

## 0. 이번 레슨의 핵심 질문

모델 A의 정확도가 0.91이고 모델 B의 정확도가 0.88이면 A가 더 좋다고 말해도 될까? A는 훈련 데이터에서, B는 테스트 데이터에서 계산했다면 비교 자체가 성립하지 않는다. 서로 다른 표본, 다른 전처리, 다른 임계값으로 얻은 점수도 마찬가지다.

공정한 비교란 모델 이름을 나열하는 일이 아니라 다음 조건을 통제하는 일이다.

1. **동일 평가조건 설정**: 같은 개발 데이터, 같은 분할, 같은 전처리 원칙을 적용한다.
2. **평가지표 비교**: 업무 목적에 맞춘 주 지표와 보조 지표를 같은 방식으로 계산한다.
3. **최종 후보 선택**: 평균 점수뿐 아니라 변동성, 제약조건, 복잡도까지 근거로 남긴다.

이 레슨의 목표는 “가장 높은 숫자 찾기”가 아니라 **재현 가능한 선택 규칙을 코드로 구현하고 설명하는 것**이다.

---

## 1. 공정한 비교를 위한 실험 설계

### 1.1 데이터를 세 역할로 분리한다

| 데이터 | 역할 | 사용 시점 |
|---|---|---|
| 학습 폴드 | 모델과 전처리기의 파라미터 학습 | 후보별 반복 |
| 검증 폴드 | 후보 비교와 설정 선택 | 교차검증 중 반복 |
| 최종 테스트셋 | 선택된 후보의 일반화 성능 확인 | 모든 선택이 끝난 뒤 한 번 |

먼저 전체 데이터에서 테스트셋을 떼어 잠근다. 남은 개발 데이터에 동일한 교차검증 분할을 적용해 후보들을 비교한다. 테스트 점수를 보고 후보를 바꾸면 테스트셋이 선택 과정에 유입되어 낙관적 편향이 생긴다.

### 1.2 후보마다 같은 폴드를 사용한다

후보 A가 쉬운 검증 표본을, 후보 B가 어려운 표본을 우연히 받으면 모델 차이와 표본 차이를 구분할 수 없다. `StratifiedKFold`를 한 번 만들고 같은 `splits`를 모든 후보에 전달한다. 분류에서는 각 폴드의 클래스 비율을 유지하는 층화 분할이 특히 유용하다.

### 1.3 전처리의 결과가 아니라 원칙을 같게 한다

로지스틱 회귀는 표준화가 중요하지만 나무 모형은 표준화가 거의 필요 없다. “공정성”이 모든 후보에 무조건 같은 변환을 강제한다는 뜻은 아니다. 각 알고리즘에 필요한 전처리를 `Pipeline` 안에 넣되, 각 폴드의 학습 부분에서만 `fit`되도록 한다. 비교에 사용한 원본 행과 목표값, 폴드, 지표는 동일해야 한다.

### 1.4 난수와 계산 예산을 기록한다

`random_state`를 고정하면 분할과 확률적 학습을 재현하기 쉽다. 한 모델만 훨씬 넓은 탐색을 수행했다면 계산 예산도 비교 결과에 영향을 준다. 실기 답안에서는 적어도 후보 생성자, 주요 매개변수, 난수, 평가방법을 코드에 드러낸다.

---

## 2. 같은 조건에서 세 모형을 비교하는 실행 코드

다음 예시는 양성 1을 “위험 고객”으로 둔 불균형 이진분류다. 최종 테스트셋은 처음에 분리한 뒤 후보 선택 중에는 사용하지 않는다.

```python
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import (
    train_test_split, StratifiedKFold, cross_validate
)
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

# 1) 재현 가능한 예제 데이터
X, y = make_classification(
    n_samples=1000, n_features=14, n_informative=7,
    n_redundant=2, weights=[0.70, 0.30], flip_y=0.02,
    class_sep=1.0, random_state=42
)

# 2) 테스트셋은 후보 선택 전에 잠근다
X_dev, X_test, y_dev, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=42
)

# 3) 알고리즘별 필요한 전처리를 파이프라인 안에 둔다
models = {
    "logistic": make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=1000, random_state=42)
    ),
    "decision_tree": make_pipeline(
        SimpleImputer(strategy="median"),
        DecisionTreeClassifier(
            max_depth=5, min_samples_leaf=5, random_state=42
        )
    ),
    "random_forest": make_pipeline(
        SimpleImputer(strategy="median"),
        RandomForestClassifier(
            n_estimators=300, min_samples_leaf=3,
            random_state=42, n_jobs=-1
        )
    )
}

# 4) 실제 인덱스 분할을 한 번 만들어 모든 후보가 공유한다
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
same_splits = list(cv.split(X_dev, y_dev))
scoring = ["accuracy", "precision", "recall", "f1", "roc_auc"]

rows = []
for name, model in models.items():
    scores = cross_validate(
        model, X_dev, y_dev,
        cv=same_splits, scoring=scoring, n_jobs=-1
    )
    row = {"model": name}
    for metric in scoring:
        values = scores[f"test_{metric}"]
        row[f"{metric}_mean"] = values.mean()
        row[f"{metric}_std"] = values.std()
    rows.append(row)

result = pd.DataFrame(rows).set_index("model")
print(result.round(3))
```

출력에는 모델별로 `accuracy_mean`, `recall_mean`, `f1_mean`, `roc_auc_mean`과 각각의 `std`가 나타난다. 라이브러리 버전과 병렬 실행 환경에 따라 마지막 자릿수는 달라질 수 있으나 읽는 순서는 변하지 않는다.

1. `*_mean`은 동일한 5개 검증 폴드의 평균이다. 후보의 기대 성능을 비교한다.
2. `*_std`는 폴드에 따른 흔들림이다. 평균이 비슷하면 변동이 작은 후보가 더 안정적일 수 있다.
3. 위험 고객 누락 비용이 크다면 `recall_mean`을 먼저 본다.
4. 재현율만 높이고 오경보가 너무 많아질 수 있으므로 `precision_mean`과 `f1_mean`도 확인한다.
5. `roc_auc_mean`은 임계값 전반의 순위 구분력을 보조적으로 보여 준다.

평균 0.902와 0.900의 차이가 있다고 해서 무조건 앞 모델이 우월하다고 단정하지 않는다. 표준편차가 각각 0.040과 0.008이라면 후자가 더 안정적일 수 있고, 두 후보의 차이가 표본 변동 범위 안일 수도 있다.

---

## 3. 선택 규칙을 코드로 명시하기

업무 요구가 “위험 고객 재현율 0.80 이상인 후보 중 F1이 가장 높은 모델”이라고 하자. 눈으로 표를 보고 고르지 말고 규칙을 코드로 남긴다.

```python
eligible = result[result["recall_mean"] >= 0.80]

if eligible.empty:
    # 제약을 만족하는 후보가 없다는 사실 자체가 결론이다.
    # 임계값 조정, 데이터 개선 또는 모델 재구축을 검토한다.
    selected_name = result["recall_mean"].idxmax()
    print("주의: 재현율 제약 미충족")
else:
    selected_name = eligible["f1_mean"].idxmax()

print("selected:", selected_name)
print(result.loc[selected_name].round(3))
```

출력의 `selected:` 다음 이름이 선택 규칙을 통과한 후보다. 이어지는 행에서 주 지표뿐 아니라 정밀도, AUC, 표준편차를 함께 읽는다. 제약을 만족한 후보가 없는데 임의로 “최고 모델”이라고 포장하지 않는 것도 중요한 평가 태도다.

여러 후보의 주 지표가 사실상 비슷하면 다음 순서로 동률을 해소할 수 있다.

1. 검증 변동성이 더 작은가?
2. 예측 시간과 메모리 요구량이 허용되는가?
3. 설명 가능성과 운영 복잡도가 요구에 맞는가?
4. 더 단순한 후보로도 목적을 달성하는가?

실기 시험의 짧은 코드에서는 모든 운영 지표를 측정하지 못하더라도, “동일 성능이면 단순한 모델을 선택한다”와 같은 기준을 설명에 남기면 선택 논리가 명확해진다.

---

## 4. 최종 후보는 잠가 둔 테스트셋에서 한 번 확인한다

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)

selected_model = models[selected_name]
selected_model.fit(X_dev, y_dev)  # 개발 데이터 전체로 마지막 재학습

test_pred = selected_model.predict(X_test)
test_prob = selected_model.predict_proba(X_test)[:, 1]

test_result = {
    "accuracy": accuracy_score(y_test, test_pred),
    "precision": precision_score(y_test, test_pred),
    "recall": recall_score(y_test, test_pred),
    "f1": f1_score(y_test, test_pred),
    "roc_auc": roc_auc_score(y_test, test_prob)
}

print(pd.Series(test_result).round(3))
print(confusion_matrix(y_test, test_pred))
```

첫 출력은 선택된 한 모델의 테스트 지표다. 검증 평균과 완전히 같을 필요는 없다. 차이가 작고 업무 제약을 만족하면 일반화가 비교적 안정적이라고 해석한다. 차이가 매우 크다면 과대적합, 작은 표본, 분포 차이 또는 선택 과정의 누수를 의심한다. 혼동행렬에서는 관심 클래스의 FN과 FP가 실제 몇 건인지 확인한다.

이 테스트 결과를 본 뒤 `selected_name`을 바꾸어 다시 평가하면 더 이상 정직한 최종 평가가 아니다. 추가 개선이 필요하다면 새 검증 절차를 설계하거나 별도의 최종 평가 데이터를 마련한다.

---

## 5. 데이터 누수가 비교 순위를 뒤집는 방식

### 잘못된 예 1: 전체 데이터로 전처리

```python
# 잘못된 흐름
X_scaled = StandardScaler().fit_transform(X)
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y)
```

테스트 데이터의 평균과 표준편차가 학습 과정에 들어간다. 후보 모두에 똑같이 누수가 발생했다고 공정한 비교가 되는 것은 아니다. 모델마다 누수 정보에 반응하는 정도가 다르므로 순위까지 왜곡될 수 있다.

### 잘못된 예 2: 후보마다 다른 분할

반복문 안에서 `train_test_split`을 난수 고정 없이 매번 호출하면 각 모델이 서로 다른 문제를 푼다. 모델 차이인지 분할 운인지 알 수 없다.

### 잘못된 예 3: 테스트셋으로 최고 후보 선택

후보 30개의 테스트 점수를 확인해 최고값을 고르면, 우연히 해당 테스트 표본에 맞은 후보가 선택될 가능성이 커진다. 후보 선택은 검증 데이터에서, 테스트는 마지막 확인에만 사용한다.

### 잘못된 예 4: 목표 정보가 포함된 열 유지

해지 처리 후 생성된 상태 코드로 해지를 예측하거나, 연체 확정일 이후의 값을 연체 예측에 쓰면 모델 종류와 무관하게 높은 점수가 나온다. 열의 의미와 생성 시점을 확인하고 예측 시점에 이용 가능한 변수만 남긴다.

---

## 6. 비교표를 읽을 때의 시험 함정

1. **훈련점수와 검증점수 혼합**: `score(X_train, y_train)`과 교차검증 평균을 같은 열에서 비교하지 않는다.
2. **서로 다른 지표의 숫자 크기 비교**: AUC 0.91이 F1 0.86보다 숫자가 크다고 같은 의미의 우위가 아니다.
3. **정확도만으로 불균형 문제 선택**: 다수 클래스를 잘 맞힌 후보가 관심 클래스는 모두 놓칠 수 있다.
4. **평균만 보고 표준편차 무시**: 평균 차이가 작다면 폴드별 변동과 복잡도를 함께 본다.
5. **`cross_val_score` 기본 지표 방치**: 분류기의 기본 `score`는 대개 정확도다. 목적 지표를 `scoring=`에 명시한다.
6. **확률 미지원 모델**: ROC AUC를 계산할 때 `predict_proba` 또는 `decision_function` 지원 여부를 확인한다.
7. **양성 레이블 오인**: 위험 대상을 0으로 코딩했다면 기본 `precision`과 `recall`이 다른 클래스를 평가할 수 있다.
8. **테스트 성능으로 재선택**: 마지막 결과를 보고 후보를 교체하면 평가 데이터 누수다.

---

## 7. 확인 문제와 해설

### 문제 1

모델 A는 분할 난수 1에서 F1 0.84, 모델 B는 분할 난수 99에서 F1 0.82를 얻었다. A가 우수하다고 결론 내릴 수 있는가?

**정답과 해설**: 없다. 서로 다른 평가 표본을 사용해 모델 효과와 분할 효과가 섞였다. 동일한 폴드와 지표로 다시 비교해야 한다.

### 문제 2

재현율 제약이 0.85이고 결과가 A `(recall=.88, F1=.79)`, B `(.84, .83)`, C `(.90, .81)`이라면 F1 우선 규칙으로 무엇을 고르는가?

**정답과 해설**: B는 재현율 제약을 충족하지 못해 제외한다. A와 C 중 F1이 높은 C를 선택한다.

### 문제 3

교차검증 F1 평균이 A 0.86, B 0.855이고 표준편차는 A 0.07, B 0.01이다. 어떤 사실을 추가로 말해야 하는가?

**정답과 해설**: 평균 차이는 작지만 A의 폴드별 변동이 훨씬 크다. 단순히 A가 우수하다고 단정하지 말고 안정성, 반복검증, 복잡도를 함께 검토해야 한다.

### 문제 4

모든 후보의 결측치를 전체 데이터 중앙값으로 대체한 뒤 교차검증했다. 후보에 같은 처리를 했으므로 공정한가?

**정답과 해설**: 아니다. 각 검증 폴드의 정보가 학습 폴드 전처리에 유입되었다. `SimpleImputer`를 `Pipeline`에 넣어 폴드 안에서 학습해야 한다.

### 문제 5

최종 테스트에서 검증 평균보다 점수가 낮았다. 바로 두 번째 후보로 바꾸어도 되는가?

**정답과 해설**: 안 된다. 테스트 결과를 선택에 사용하게 된다. 먼저 차이의 원인을 보고하고, 필요하면 새로운 검증 설계와 독립 평가셋으로 다음 실험을 진행한다.

---

## 8. 최종 요약

- 공정한 비교는 같은 개발 데이터, 같은 폴드, 같은 지표, 누수 없는 전처리에서 시작한다.
- 후보마다 필요한 전처리는 다를 수 있지만 반드시 `Pipeline` 안에서 학습 폴드에만 적합한다.
- 평균 점수와 함께 표준편차, 오류 비용, 업무 제약, 복잡도를 확인한다.
- 선택 규칙을 먼저 정하고 코드로 구현해야 결과를 본 뒤 기준을 바꾸는 편향을 막을 수 있다.
- 후보 선택은 검증 데이터로 끝내고, 잠가 둔 테스트셋은 선택된 모델을 마지막에 한 번 확인하는 데 쓴다.
- “최고 점수 모델”보다 **왜 같은 조건에서 이 후보를 선택했는지 재현 가능한 근거**가 더 중요하다.
