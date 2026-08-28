# 4-1-3-1. 모형 결합과 성능 확인

> **공식 학습 범위**: 성능 향상을 위해 결합할 후보를 선정하고, 여러 모형의 예측을 적절히 결합한 뒤, 동일한 평가조건에서 단일모형과 성능을 비교한다.

**Curriculum topics**: `결합 대상 선정` · `예측 결합` · `단일모형과 성능 비교`

## 0. 결합의 목적부터 바로 잡기

앙상블은 모델을 많이 넣는 기술이 아니다. 서로 다른 모델이 만드는 오류를 보완해 **새 데이터에서 더 안정적인 예측**을 얻는 기술이다. 정확도가 비슷한 두 모델이라도 항상 같은 행을 틀리면 결합 이득이 작다. 반대로 강점과 오류 패턴이 다른 모델은 평균하거나 투표할 때 한 모델의 실수를 다른 모델이 완화할 수 있다.

이번 레슨의 세 가지 도착점은 명확하다.

1. 성능과 오류 다양성을 근거로 결합 대상을 고른다.
2. 분류 확률을 평균하거나 가중평균해 최종 예측을 만든다.
3. 단일모형과 결합모형을 같은 테스트셋·지표에서 비교한다.

결합 결과가 단일모형보다 나쁘다면 억지로 채택하지 않는다. “앙상블은 언제나 향상된다”가 아니라 **검증 결과로 향상 여부를 확인한다**가 정답이다.

---

## 1. 결합 대상 선정: 강한 모델보다 서로 다른 모델

### 1.1 최소 성능과 다양성을 함께 본다

결합 후보는 기본 성능이 지나치게 낮지 않으면서 오류 패턴이 달라야 한다. 다음 조합을 생각해 볼 수 있다.

| 후보 | 특징 | 기대 역할 |
|---|---|---|
| 로지스틱 회귀 | 선형 결정경계, 표준화 필요 | 전체적인 선형 경향 포착 |
| 의사결정나무 | 비선형 규칙, 상호작용 포착 | 국소적인 분기 규칙 보완 |
| 랜덤 포레스트 | 여러 나무의 배깅 | 분산 감소와 안정성 확보 |

모델 이름이 다르다는 사실만으로 다양성이 보장되지는 않는다. 같은 데이터에서 예측한 결과를 이용해 **불일치율**을 계산할 수 있다.

```python
import numpy as np

pred_a = np.array([0, 1, 1, 0, 1, 0, 0, 1])
pred_b = np.array([0, 1, 0, 0, 1, 1, 0, 1])

disagreement = np.mean(pred_a != pred_b)
print("불일치율:", disagreement)
```

```text
불일치율: 0.25
```

8건 중 2건에서 예측이 달랐다는 뜻이다. 불일치율이 크다고 무조건 좋은 조합은 아니다. 한 모델이 무작위로 틀려도 불일치율은 커진다. 따라서 각 후보의 검증 성능이 기본 수준을 넘는지 먼저 확인하고, 그다음 오류의 겹침을 본다.

### 1.2 결합 전에 후보를 검증 데이터로 확정한다

테스트셋 예측을 본 뒤 “이 조합이 좋아 보인다”며 모델이나 가중치를 바꾸면 테스트 데이터 누수다. 결합 후보와 가중치는 교차검증 또는 별도 검증셋에서 정하고, 테스트셋은 최종 비교에 한 번만 사용한다.

---

## 2. 예측 결합의 세 가지 기본 형태

### 2.1 다수결 하드 보팅

각 분류기가 예측한 0/1 레이블을 투표해 다수가 선택한 클래스를 최종값으로 정한다. 확률을 제공하지 않는 모델도 참여할 수 있지만, 각 모델의 확신 정도를 버린다. 모델 수가 짝수면 동률 처리 규칙도 필요하다.

### 2.2 확률 평균 소프트 보팅

각 모델의 양성 확률을 평균하고 임계값으로 레이블을 만든다.

\[
p_{ensemble}(x)=\frac{p_1(x)+p_2(x)+\cdots+p_m(x)}{m}
\]

확률 정보가 유지되므로 ROC AUC 계산과 임계값 조정에 유리하다. 단, 확률의 품질이 심하게 다른 모델을 단순 평균하면 과도하게 확신하는 모델이 결과를 왜곡할 수 있다.

### 2.3 가중 소프트 보팅

검증 성능과 신뢰도에 따라 가중치를 준다.

\[
p_{ensemble}(x)=\frac{w_1p_1(x)+w_2p_2(x)+\cdots+w_mp_m(x)}{w_1+w_2+\cdots+w_m}
\]

가중치를 테스트 성능으로 정해서는 안 된다. 검증에서 근거를 세우고 합이 1이 되도록 정규화하면 해석하기 쉽다.

### 손으로 확인하는 확률 결합

```python
import numpy as np
from sklearn.metrics import f1_score, roc_auc_score

y_true = np.array([1, 1, 0, 0, 1, 0])
prob_a = np.array([.80, .45, .30, .20, .62, .40])
prob_b = np.array([.65, .70, .55, .15, .58, .25])
prob_c = np.array([.90, .52, .35, .30, .40, .10])

soft = (prob_a + prob_b + prob_c) / 3
weighted = .40 * prob_a + .35 * prob_b + .25 * prob_c

for name, prob in {"A": prob_a, "soft": soft, "weighted": weighted}.items():
    pred = (prob >= .50).astype(int)
    print(name, "prob=", np.round(prob, 3),
          "F1=", round(f1_score(y_true, pred), 3),
          "AUC=", round(roc_auc_score(y_true, prob), 3))
```

```text
A prob= [0.8  0.45 0.3  0.2  0.62 0.4 ] F1= 0.8 AUC= 1.0
soft prob= [0.783 0.557 0.4   0.217 0.533 0.25 ] F1= 1.0 AUC= 1.0
weighted prob= [0.772 0.557 0.399 0.207 0.551 0.273] F1= 1.0 AUC= 1.0
```

두 번째 표본에서 A의 확률은 0.45라 음성으로 틀리지만 B와 C가 보완해 평균 확률이 0.5를 넘는다. 반면 AUC는 A도 이미 1.0이다. AUC는 양성과 음성의 순위가 완벽하다는 뜻이고, 임계값 0.5의 F1은 별개다. 이 차이는 “결합 성능”을 하나의 지표로만 말하면 안 되는 이유이기도 하다.

---

## 3. 실제 모델을 소프트 보팅으로 결합하기

다음 코드는 로지스틱 회귀, 의사결정나무, 랜덤 포레스트를 결합한다. 모든 모델은 같은 학습·테스트 행을 사용하고, 전처리는 각 파이프라인 안에서 학습 데이터에만 적합된다.

```python
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score
)

X, y = make_classification(
    n_samples=1200, n_features=16, n_informative=8,
    n_redundant=2, weights=[0.70, 0.30],
    class_sep=1.0, flip_y=0.02, random_state=42
)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, stratify=y, random_state=42
)

lr = make_pipeline(
    SimpleImputer(strategy="median"),
    StandardScaler(),
    LogisticRegression(max_iter=1000, random_state=42)
)
dt = make_pipeline(
    SimpleImputer(strategy="median"),
    DecisionTreeClassifier(
        max_depth=5, min_samples_leaf=5, random_state=42
    )
)
rf = make_pipeline(
    SimpleImputer(strategy="median"),
    RandomForestClassifier(
        n_estimators=300, min_samples_leaf=3,
        random_state=42, n_jobs=-1
    )
)

ensemble = VotingClassifier(
    estimators=[("lr", lr), ("dt", dt), ("rf", rf)],
    voting="soft",
    weights=[1, 1, 2]  # 검증에서 정했다고 가정한 예시 가중치
)

models = {"logistic": lr, "tree": dt, "forest": rf, "soft_vote": ensemble}
rows = []

for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    prob = model.predict_proba(X_test)[:, 1]
    rows.append({
        "model": name,
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred),
        "recall": recall_score(y_test, pred),
        "f1": f1_score(y_test, pred),
        "roc_auc": roc_auc_score(y_test, prob)
    })

comparison = pd.DataFrame(rows).set_index("model")
print(comparison.round(3).sort_values("f1", ascending=False))
```

출력표에서 `soft_vote` 행과 세 단일모형 행을 같은 열로 비교한다. 예제 데이터 생성기나 라이브러리 버전에 따라 마지막 자릿수와 순위는 달라질 수 있으며, 그것이 정상이다. 해석 절차는 다음과 같다.

1. 업무 주 지표가 F1이면 `f1` 열에서 결합모형이 최고 단일모형보다 높은지 확인한다.
2. 위험 대상을 놓치는 비용이 크면 `recall` 제약을 먼저 확인한다.
3. `roc_auc`가 좋아졌는데 F1이 나빠졌다면 확률 순위는 개선됐지만 임계값 0.5가 목적에 맞지 않을 수 있다.
4. 차이가 매우 작다면 계산량과 운영 복잡도까지 고려해 단일모형을 유지할 수 있다.
5. 결합모형이 낮으면 후보·가중치·확률 보정 문제를 검증 데이터에서 재검토하거나 결합을 채택하지 않는다.

위 코드는 결합 원리를 보여 주려고 한 번의 테스트 분할을 사용한다. 실제 후보와 가중치를 정할 때는 교차검증으로 선택하고, 고정된 테스트셋은 마지막 비교에만 사용해야 한다.

---

## 4. 단일모형 대비 향상을 정확히 표현하기

결합의 비교 기준은 “아무 단일모형”이 아니라 **가장 좋은 단일 후보**다.

```python
single = comparison.loc[["logistic", "tree", "forest"]]
best_single_name = single["f1"].idxmax()
best_single_f1 = single.loc[best_single_name, "f1"]
ensemble_f1 = comparison.loc["soft_vote", "f1"]

delta = ensemble_f1 - best_single_f1
print("best single:", best_single_name)
print("F1 difference:", round(delta, 4))
```

`F1 difference`가 양수면 이 테스트에서 결합모형이 최고 단일모형보다 그만큼 높았다는 뜻이다. 음수면 결합이 오히려 나빴다. 예를 들어 차이가 0.003이라면 “크게 개선”이라고 과장하지 않는다. 교차검증 폴드별 차이나 반복 실험의 변동도 확인해야 한다.

모델 결합은 다음 비용을 추가한다.

- 여러 모델 파일을 저장하고 버전을 함께 관리해야 한다.
- 예측 시 모든 기본 모델을 실행하므로 시간과 메모리가 증가한다.
- 일부 기본 모델이 실패했을 때 처리 규칙이 필요하다.
- 개별 설명과 결합 결과를 함께 추적해야 해 해석이 복잡해진다.

따라서 성능 향상이 작고 단일모형이 요구 지표를 충분히 만족한다면 단순한 모델을 선택하는 것도 올바른 결론이다.

---

## 5. 누수를 막는 결합 설계

### 5.1 테스트셋으로 가중치를 찾지 않는다

`weights=[1, 1, 2]`, `[1, 2, 3]` 등을 테스트셋에서 반복해 최고 점수를 고르면 테스트 정보가 결합 규칙에 들어간다. 가중치는 개발 데이터의 교차검증으로 정한 뒤 고정한다.

### 5.2 스태킹의 메타모델은 동일 행의 학습 예측을 그대로 배우면 안 된다

스태킹은 기본 모델의 예측을 입력으로 삼아 메타모델이 결합법을 학습한다. 기본 모델이 자신을 학습한 행에 낸 예측으로 메타모델을 학습하면 과도하게 낙관적이다. 각 행에 대해 그 행을 학습하지 않은 폴드의 예측, 즉 OOF(out-of-fold) 예측을 사용해야 한다. `StackingClassifier`는 내부 교차검증으로 이 절차를 지원하지만, 이번 레슨의 기본 구현은 더 직접적인 소프트 보팅이다.

### 5.3 전처리는 기본 모델별 파이프라인 안에 둔다

전체 데이터로 스케일링한 뒤 결합기에 넣으면 누수가 발생한다. 위 예시처럼 각 기본 모델을 파이프라인으로 정의하면 `VotingClassifier`가 복제하여 학습할 때도 전처리가 학습 데이터에만 맞춰진다.

### 5.4 동일한 평가 표본을 유지한다

단일모형은 테스트셋 A, 앙상블은 테스트셋 B에서 평가하면 결합 효과를 분리할 수 없다. 동일한 `X_test`, `y_test`, 양성 레이블, 임계값, 지표를 사용한다.

---

## 6. 시험 함정 정리

1. **앙상블 만능론**: 서로 비슷한 모델의 오류가 강하게 겹치면 평균해도 향상이 작다.
2. **하드 보팅과 소프트 보팅 혼동**: 하드는 레이블 투표, 소프트는 확률 평균이다.
3. **가중치 순서 오류**: `weights`의 순서는 `estimators` 목록의 순서와 일치해야 한다.
4. **AUC에 레이블 사용**: ROC AUC에는 `predict_proba()[:, 1]` 같은 확률·점수를 넣는다.
5. **최고 단일모형이 아닌 약한 기준과 비교**: 앙상블의 이득은 최고 단일 후보 대비로 확인한다.
6. **테스트셋으로 조합 탐색**: 후보, 가중치, 임계값은 검증 단계에서 확정한다.
7. **양성 클래스 오인**: `predict_proba`의 열은 `classes_` 순서를 따른다. 항상 1열이 업무상 관심 대상인지 확인한다.
8. **성능 차이 과장**: 소수점 몇 천분의 일 차이는 변동 범위와 운영비용을 함께 봐야 한다.

---

## 7. 확인 문제와 해설

### 문제 1

정확도 0.88인 모델 세 개가 모든 평가 행에서 거의 같은 예측을 낸다. 세 모델을 투표하면 큰 향상이 보장되는가?

**정답과 해설**: 보장되지 않는다. 오류가 겹치면 다수결도 같은 오류를 유지한다. 개별 검증 성능과 오류 다양성을 함께 확인해야 한다.

### 문제 2

모델 확률이 A 0.8, B 0.6, C 0.4이고 가중치가 1:2:1일 때 결합 확률은?

**정답과 해설**: `(1×0.8 + 2×0.6 + 1×0.4) / 4 = 0.6`이다. 임계값 0.5라면 양성으로 예측한다.

### 문제 3

결합모형 F1이 0.842, 최고 단일모형 F1이 0.845다. “앙상블이므로” 결합모형을 선택해야 하는가?

**정답과 해설**: 아니다. 동일 평가조건에서 결합이 더 낮고 운영도 복잡하다. 다른 업무 제약에서 뚜렷한 장점이 없다면 단일모형이 합리적이다.

### 문제 4

테스트셋에서 여러 가중치를 시험해 가장 높은 조합을 선택했다. 문제는 무엇인가?

**정답과 해설**: 테스트셋이 결합 규칙 선택에 사용된 데이터 누수다. 가중치는 검증 또는 교차검증에서 정하고 테스트는 마지막 확인에만 쓴다.

### 문제 5

소프트 보팅의 AUC는 올랐지만 임계값 0.5의 재현율은 낮아졌다. 모순인가?

**정답과 해설**: 아니다. AUC는 전체 임계값의 순위 구분력이고 재현율은 특정 임계값의 결과다. 검증 데이터에서 업무 목적에 맞는 임계값을 별도로 정할 수 있다.

---

## 8. 최종 요약

- 결합 대상은 기본 성능이 충분하면서 오류 패턴이 다른 모델로 선정한다.
- 하드 보팅은 레이블 투표, 소프트 보팅은 확률 평균, 가중 보팅은 검증 근거를 반영한 확률 결합이다.
- 후보와 가중치는 검증 데이터에서 확정하고 테스트셋을 결합 규칙 탐색에 사용하지 않는다.
- 단일모형과 결합모형은 동일한 데이터, 지표, 임계값에서 비교한다.
- 향상 기준은 최고 단일모형이며, 지표 차이와 변동성·계산비용·운영복잡도를 함께 본다.
- 결합이 성능을 높이지 않으면 채택하지 않는 것이 올바른 모델 평가다.

좋은 앙상블은 모델 수가 많은 시스템이 아니라, **서로 다른 판단을 누수 없이 결합하고 실제 향상을 검증한 시스템**이다.
