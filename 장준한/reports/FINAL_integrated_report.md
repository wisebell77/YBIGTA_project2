# 판촉의 증분성 — 최종 통합 보고서 (확정본)

> **Final date:** 2026-08-17 · **Phase 0~8 완료** · **다중검정 BH-FDR 보정 반영**
> **전 수치 원본 CSV 교차검증 19/19 통과** (`src/phase8_final_tables.py`)
> **방법론 구분:** PART A = 전단지 노출 ITT (주 인과추정, 식별가정 필요) /
> PART B = 실현 딥할인 기반 observational·exploratory 분석 — 두 파트를 직접 비교하지 않는다.
> 핵심수치 `outputs/tables/FINAL_key_results.csv` · 의사결정 `outputs/tableau/07_final_decision_matrix.csv`

---

## 0. 최종 결론

> **전단지 판촉은 카테고리 구매확률을 24.3%, 0구매를 포함한 총수요를 34.4% 증가시켰으며,
> 강한 시간통제를 적용해도 수량효과는 약 27.0%로 유지되었다.**
>
> **56일 이후 동일 카테고리 구매를 추적한 결과 유의한 미래수요 감소가 관측되지 않아,
> 판촉이 단순히 미래 구매를 앞당기는 방식으로 작동한다는 근거는 확인되지 않았다.**
>
> **반면 정가환산 상품가치는 39.5% 증가한 데 비해 실제 매출은 26.1% 증가하여
> 13.4%p의 value-to-revenue gap이 존재했다.**
>
> **단순 gross-margin scenario에서는 약 40.3%가 증분 gross-profit proxy의 손익분기 가정으로
> 계산되지만, 실제 원가와 vendor funding 정보가 없어 실제 ROI로 해석할 수 없다.**
>
> **후속 observational analysis에서는 딥할인 구매 이후 28일 전체 매장 활동이 비교군보다 다소
> 낮게 관측되었다. 그러나 고객구성을 통제하면 격차가 크게 축소되었고, 카테고리 및 고객
> segment별 차이는 다중검정을 고려해 제한적으로 해석해야 한다.**
>
> **따라서 핵심 의사결정은 '판촉을 전면 중단할 것인가'가 아니라 '증분수요를 유지하면서
> 불필요한 할인 깊이를 얼마나 줄일 수 있는가'이며, 카테고리·고객별 세밀한 차별화는
> 현재 탐색결과를 바탕으로 추가 실험을 통해 검증하는 것이 적절하다.**

---

## ⚠️ 이 보고서를 읽는 법 — PART A와 PART B

| | **PART A** | **PART B** |
|---|---|---|
| Phase | 0 ~ 4A | 4B ~ 5C |
| 처치 | **전단지 노출** (category×store×week, `mailer<>'0'`) | **실현 딥할인** (할인율 ≥30%) |
| 성격 | **주 인과추정 설계 (ITT, 식별가정 필요)** | **관측적 / 탐색적** |
| 처치 할당 | 구매자가 실제 할인상품을 선택한 결과가 아니라, 사전에 존재한 category×store×week 전단지 노출기회를 treatment로 사용. realized-discount 설계보다 자기선택 위험은 낮지만 **category/time-specific confounding 가능성은 남아 있다.** | **가구가 스스로 딥할인을 선택** — 선택편의 미제거 |
| 표현 | "효과", "증분", "인과" 사용 가능 | **"차이", "연관", "패턴"만** |

**PART B는 "그래서 어떻게 활용하나"의 재료이지 인과 근거가 아니다.**
두 파트의 숫자를 같은 표에 나란히 놓고 비교하지 말 것.

---

# PART A — 인과 분석 (전단지 ITT)

## 1. 주 결과와 95% 신뢰구간

단위 `household_key × STORE_ID × DAY × COMMODITY_DESC`, N=46,714,794
FE `hh×cat` (551,670 pair) · SE household cluster (2,485가구) · 카테고리 222

| 결과변수 | beta | 95% CI | 상대% | 상대% 95% CI |
|---|---|---|---|---|
| **구매확률** | +0.005412 | [+0.005176, +0.005648] | **+24.31%** | [+23.25, +25.37] |
| **총수량 (0 포함)** | +0.012984 | [+0.012351, +0.013618] | **+34.41%** | [+32.74, +36.09] |
| **총매출 SALES** | +0.019989 | [+0.018913, +0.021064] | **+26.12%** | [+24.72, +27.53] |
| **정가환산 REG** | +0.033505 | [+0.032014, +0.034996] | **+39.52%** | [+37.76, +41.28] |

- 총수량 증가의 **약 70.6%가 extensive margin**(구매확률 상승)에서 발생 — 근사 분해(잔차 9.8%).
- 정가환산 상품가치 증가율은 **+39.52%**, 실제 SALES 증가율은 **+26.12%**로,
  두 상대효과 추정치 사이에 **13.40%p의 value-to-revenue gap이 관측되었다.**
  ⚠️ 두 상대효과는 서로 다른 control mean을 분모로 계산되며, 이 격차에 대한
  **정식 difference test는 수행하지 않았다.** 통계적으로 확정된 차이로 서술하지 않는다.

### 시간통제 밴드

| 통제 | 구매확률 | 총수량 |
|---|---|---|
| ① hh×cat (주 스펙) | +24.31% | +34.41% |
| ② +WEEK / ③ +store×cat | +23.98% | — |
| ⑥ +cat×quarter | +19.77% | +29.86% |
| **⑧ +cat×month +WEEK (최대통제)** | **+17.34%** | **+26.97%** |

> **보고 문장:** "총수량 효과는 +34.4%이며, 카테고리 계절성을 최대로 통제해도 약 +27.0%로 유지된다."

**SE 강건성:** 2-way cluster(household + store×cat)로 넓혀도 SE는 9~17% 증가에 그치고 t = 33~40 유지.

## 2. 56일 미래수요 추적 (Phase 3B-1)

| 스펙 | 당일 ΔQ0 | 미래 ΔQ56 | 95% CI | 판정 |
|---|---|---|---|---|
| M1 자연경로 | +0.013331 | +0.041058 (t=19.5) | [+0.0369, +0.0452] | ⚠️ 카테고리 계절성 인공물 |
| M2 +WEEK | — | +0.042847 (t=20.2) | — | ⚠️ 동일 |
| **M3 +cat×month+WEEK (확정)** | **+0.010298** | **+0.000158 (t=0.16, p=0.87)** | **[−0.001764, +0.002079]** | **유의한 payback 없음** |

> **헤드라인: 56일 이내 유의한 future payback이 관측되지 않았다.**

**정확한 표현:** 56일 미래효과의 점추정치는 +0.000158로 0과 통계적으로 구분되지 않았으며,
점추정 기준 누적효과는 당일효과의 약 101.5% 수준이었다.
**101.5%는 point-estimate cumulative ratio이며 헤드라인 수치로 사용하지 않는다.**

### CI 환산 참고값 (Approx. CI-implied payback bound = 17.1%)

M3의 56일 future quantity 95% CI 하단을 당일 ΔQ0에 단순 환산하면,
당일 증분량의 약 **17.1%**를 초과하는 수준의 negative payback은 현재 신뢰구간과 잘 부합하지 않는다.

⚠️ **이는 ΔQ0를 고정한 근사적 CI 환산이며, 사전에 margin을 정한 formal equivalence test가 아니다.**

### ⚠️ M1의 큰 양(+)의 미래효과는 최종 증분성 결과가 아니다

M1/M2에서 나온 미래효과(+0.041, t=19.5)는 `cat×month`를 넣으면 +0.000158(t=0.16)로 소멸한다.
반면 **당일효과는 −23% 감쇠에 그치고 살아남는다.** M3의 SE(0.00098)가 M1의 SE(0.00211)보다
**작으므로 검정력 문제가 아니다.** 56일 창은 약 2개월이라 카테고리 계절성에 최대로 노출된다.
→ **M1 기준 누적배수(3.0×/4.1×)를 증분성 지표로 인용하지 않는다.**

---

# PART B — 관측적 분석 (실현 딥할인)

> ⚠️ 이하 전부 **관측적/탐색적**이다. 딥할인 구매는 가구가 스스로 선택한 것이므로 선택편의가
> 제거되지 않았다. **인과효과로 해석 금지.**

## 3. Phase 4B — 딥할인 이후 28일 매장 전체 행동

anchor 271,334 (딥 80,256 / 정가 191,078) · 가구 2,081 · 카테고리 210 · hh×cat pair 34,444
전처리: ±28일 내 다른 딥할인 anchor 제거 + 우측중도절단(`DAY+28<=705`) → 511,703 → 271,334
추정: `hh×cat` FE, household cluster SE

| 28일 미래 (매장 전체) | 정가 평균 | 차이 (딥−정가) | 95% CI | 상대% |
|---|---|---|---|---|
| 방문 횟수 | 7.015 | −0.0779 | [−0.107, −0.049] | −1.11% |
| 총지출 | $280.20 | **−$4.56** | [−5.96, −3.16] | −1.63% |
| 바스켓 수 | 8.734 | −0.128 | [−0.177, −0.078] | −1.46% |
| 타 카테고리 지출 | $275.66 | −$4.27 | [−5.65, −2.89] | −1.55% |

**정확한 표현:** 딥할인 구매 이후 28일 전체 매장 활동이 비교군보다 낮게 관측되었다.
**realized deep-discount 선택 자체의 자기선택 가능성이 있으므로 이를 인과적 고객관계 악화로
해석하지 않는다.** 차이의 크기도 −1.1~1.6%로 작다.

## 4. Phase 5A — 카테고리 포트폴리오 (⚠️ FDR 보정 후)

83개 카테고리 × 2지표 = 166개 동시검정 → 지표별 Benjamini-Hochberg FDR 적용.

| | visits (83) | spend (83) |
|---|---|---|
| 명목 p<0.05 | 10 | 10 |
| **BH FDR q<0.05** | **0** | **0** |
| 최소 q | 0.1020 | 0.0647 |
| joint family(166) q<0.05 | 0 | 0 |

> ⚠️ **Phase 5A FDR은 공표 CI(`beta ± 1.96·SE`)에서 복원한 SE를 이용한 정규근사 p-value 기반이다.** 원 회귀의 p-value와 완전히 동일하지 않다.
> *BH-FDR uses normal-approximation p-values reconstructed from the reported beta ± 1.96·SE confidence intervals.*

| 최종 분류 | 수 |
|---|---|
| **robust strengthening** | **0** |
| **robust weakening** | **0** |
| suggestive (방향 일관, q≥0.05) | 63 |
| indeterminate | 20 |

> **83개 카테고리 중 FDR 보정 후 robust strengthening/weakening category는 확인되지 않았다.**

FDR 이전 "weakening"이던 3개(BREAKFAST SWEETS / SOUP / CHEESE)는 전부 suggestive로 내려간다.

⚠️ **suggestive 63개를 과대해석하지 말 것.** 부호 일관성만 요구하는 라벨이고, visits/spend는
같은 행동을 재는 강한 상관 지표라 83개 중 **75.9%가 부호 일관**이다. 한 축이라도 명목 유의한 것은
16개, 양축 모두는 3개뿐이다.

> **→ 카테고리별 SCALE/STOP을 결정할 만큼 안정적인 이질성 근거가 없다.**

## 5. Phase 5B — Period-Split RFM / CRM (⚠️ FDR 보정 후)

사전창 DAY 55–138(84일, 누수 없음) / 평가 DAY 139–677 / occasion 992,694
최소 cell(가구≥30 & occasion≥100) 전부 충족, 병합 불필요.
**naive −$19.24는 최종 정책결론에 사용하지 않는다.**

### 5-1. 주 추정치 (hh×cat FE, 사전지정)

| | diff (FE) | t | 95% CI |
|---|---|---|---|
| future 28d store visits | −0.0226 | −2.50 | [−0.040, −0.005] |
| future 28d store spend | **−$1.35** | −3.32 | [−2.15, −0.55] |

### 5-2. 세그먼트 FDR (결과변수별 17개 검정 family, ALL 제외)

| family | 명목 p<0.05 | **FDR q<0.05** | 최소 q |
|---|---|---|---|
| visits (segments) | 6 | **6** | 0.0117 |
| spend (segments) | 6 | **6** | 0.0000114 |

**17개 고객특성 비교 중 6개의 High-level 비교에서 visits와 spend 모두 FDR 보정 후
음(−)의 association이 유지되었다.**

⚠️ **이는 서로 배타적인 6개 고객군이 아니다.** 동일 household가 여러 High 특성을 동시에
가질 수 있으므로 비교군끼리 크게 중첩된다.

| High 특성 비교 | visits (q) | spend (q) |
|---|---|---|
| F(frequency) High | −0.0428 (0.0117) | −2.831 (1.1e−05) |
| RFM 종합 High value | −0.0379 (0.0117) | −2.668 (2.2e−05) |
| 딥할인성향 High | −0.0483 (0.0117) | −2.830 (2.4e−05) |
| M(monetary) High | −0.0314 (0.0306) | −2.370 (0.00017) |
| R(recency) High | −0.0440 (0.0117) | −2.206 (0.00197) |
| churn_flag = 0 | −0.0334 (0.0117) | −1.689 (0.00234) |

Low/Mid 세그먼트는 FDR 전후 모두 유의하지 않다(최소 q=0.134).
여전히 **관측적 연관**이며 자기선택 가능성이 남아 있다.

### 5-3. ⭐ naive → FE 축소 (방법론적 핵심 증거)

| 28일 미래 매장 지출 | naive (FE 없음) | **hh×cat FE** |
|---|---|---|
| 전체 | −$19.24 (t=−5.34) | **−$1.35** (t=−3.32) |

> **CRM 세그먼트 분석에서도 단순 평균비교는 딥할인 고객의 구성 차이를 크게 반영했다.
> 가구×카테고리 고정효과를 적용하자 future spend 차이가 약 93% 축소되어,
> 판촉성과 평가에서 고객구성 통제의 중요성이 다시 확인되었다.**

⚠️ **"93%가 전부 selection bias"라는 정확한 분해는 아니다.** FE는 가구·카테고리 수준의 고정된
차이만 제거하며 시점별 상태(재고·노출·타이밍)는 통제하지 못한다. 말할 수 있는 것은
**"93% 축소되었고, 따라서 구성효과가 상당했음을 시사한다"**까지다.

naive에서 보였던 딥할인성향 그래디언트(Low −25.0 → High −3.0)는 FE에서 **역전**된다
(Low −0.62 n.s. → High −2.83 유의). **naive 세그먼트 그래디언트를 CRM 타겟팅 근거로 쓰면 안 된다.**

## 6. Phase 5C — 전환 · 할인깊이 · 마진 시나리오

### 6-1. Trial → Repeat → 정가 전환 (기술통계)

첫 딥할인 구매 114,903건. 우측중도절단은 28일/56일 각각 별도 적용.

| | 28일 | 56일 |
|---|---|---|
| 대상 | 112,100 | 108,871 |
| **재구매율** | **33.55%** | **49.73%** |
| **재구매 중 정가 전환율** | **50.22%** | **57.15%** |

⚠️ 비교군이 없는 단일군 기술통계다.

### 6-2. 실현 할인 깊이 밴드 (기술통계)

| 밴드 | N | 평균 수량 | 평균 SALES | 56일 재구매율 | **정가 전환율** |
|---|---|---|---|---|---|
| <20% | 1,666,750 | 1.271 | $3.105 | 66.71% | **77.89%** |
| 20–30% | 290,170 | 1.301 | $2.670 | 69.26% | 60.58% |
| 30–40% | 231,107 | 1.369 | $2.411 | 68.86% | 59.53% |
| **40%+** | 253,861 | **1.559** | **$2.336** | 69.54% | **60.53%** |

**정확한 표현:** 깊은 할인은 더 많은 물량과 함께 **낮은 realized revenue 및 낮은 정상가 전환과
연관**된다. **밴드 membership은 자기선택이므로 "깊게 할인해서 전환율이 떨어진다"고 쓰지 않는다.**

### 6-3. gross-margin 시나리오

```
ΔSALES = +0.019989   ΔREG = +0.033505     (PART A 인과량)
회수율 = ΔSALES/ΔREG = 59.66%
profit(m) = ΔSALES − (1−m)·ΔREG
scenario break-even m* ≈ 40.34%
```

| 총마진 m | 구매기회당 | 패널 전체 (46.7M) |
|---|---|---|
| 20% | −$0.006815 | −$318,361 |
| 30% | −$0.003464 | −$161,843 |
| **40.34%** | $0 | **$0 (분기 가정)** |
| 45% | +$0.001561 | +$72,933 |
| 50% | +$0.003236 | +$151,192 |

> 실제 원가·vendor funding·rebate·프로모션 운영비가 없는 **단순 gross-margin scenario**에서,
> 약 **40.3%**가 증분 gross-profit proxy의 손익분기 가정으로 계산된다.

⚠️ **실제 ROI가 아니다.** vendor funding은 임계값을 낮추고, 전단지 제작·배포비와 운영비는
높인다. 두 정보가 모두 없으므로 방향조차 단정할 수 없다.

---

# 7. 최종 Decision Matrix

`outputs/tableau/07_final_decision_matrix.csv`

| # | 판단 대상 | 결론 | 근거 | PART | 신뢰도 |
|---|---|---|---|---|---|
| 1 | 56일 payback 우려 | **큰 미래수요 잠식 근거 없음** | M3 ΔQ56=+0.000158 (t=0.16), CI 환산 bound ≈17.1% | A | **높음** |
| 2 | 전체 판촉 수요효과 | **purchase / quantity 증가** | +24.31% / +34.41% (강통제 +26.97%) | A | **높음** |
| 3 | gross-margin < 40.3% | 경제성 재검토 / 할인 깊이 축소 후보 | scenario break-even ≈40.34% | A량+가정 | 중 |
| 4 | gross-margin 40.3~45% | 경제성 민감구간 / 실제 원가정보 필요 | 손익 부호가 가정에 민감 | A량+가정 | 중 |
| 5 | gross-margin ≥ 45% | 단순 scenario상 상대적으로 경제성 우호적 | +$72,933 ~ +$151,192 | A량+가정 | 중 |
| 6 | category SCALE/STOP | **현재 데이터만으로 세밀한 차별화 보류** | FDR 후 robust category **0개** (최소 q=0.065) | B | **높음** |
| 7 | 고객 segment targeting | High 특성 비교 일부에서 FDR 이후에도 음(−)의 future-store association 유지. **단, 특성들은 서로 중첩되며 PART B는 observational이므로 정책화 전 실험 필요** | 17개 비교 중 6개 High-level 비교에서 visits·spend 모두 유지 | B | 낮음~중 |
| 8 | discount depth | 깊은 할인은 더 많은 물량 + 낮은 realized revenue + 낮은 정상가 전환과 **연관** | 수량 1.27→1.56, SALES $3.11→$2.34, 전환 77.9%→60.5% | B | 낮음~중 |

## 전략 요약

1. **판촉의 문제는 잠식이 아니다.** 56일 내 유의한 payback이 관측되지 않았다. "미래를 당겨쓴다"는 프레임은 이 데이터로 지지되지 않는다.
2. **판촉의 경제성은 마진 가정에 달려 있다.** 증분 단위 회수율이 정가의 59.7%이므로, 단순 scenario에서 임계 마진은 약 40.3%다. 실제 판단에는 **원가·vendor funding 정보가 반드시 필요하다.**
3. **1순위 실험 대상은 할인 깊이다.** 카테고리 차별화 근거는 FDR 후 사라졌고(0개), 할인 깊이는 물량·회수율·정가 전환과 뚜렷하게 연관된다. 다만 관측적 결과이므로 **실험으로 검증**해야 한다.

---

# 8. 이 프로젝트를 관통하는 방법론적 발견

서로 독립된 세 지점에서 같은 현상이 반복됐다.

| 지점 | naive | 교란 제거 후 | 변화 |
|---|---|---|---|
| Phase 3A — 구매기회당 지출 | +4.40% | **−0.99%** | 부호 반전 |
| Phase 3B-1 — 56일 미래 수량 | +0.041058 (t=19.5) | +0.000158 (t=0.16) | 소멸 |
| Phase 5B — 28일 미래 지출 | −$19.24 | **−$1.35** | 약 93% 축소 |

> **판촉 성과 지표에서 고객·카테고리 구성 통제의 중요성이 세 번 독립적으로 확인되었다.**

여기에 **다중검정 보정**이 네 번째 사례를 더한다 —
Phase 5A에서 명목 유의 10개 카테고리가 FDR 후 **0개**로 사라졌다.

---

# 9. 최종 핵심 수치

전체 21개는 `outputs/tables/FINAL_key_results.csv` 참조.

| # | 지표 | 값 | PART |
|---|---|---|---|
| 1 | 구매확률 증가 | **+24.31%** | A |
| 2 | 총수량 증가 (0구매 포함) | **+34.41%** | A |
| 3 | 강한 시간통제 수량효과 | **+26.97%** | A |
| 4 | 실제 매출 증가 | +26.12% | A |
| 5 | 정가환산 증가 | +39.52% | A |
| 6 | **value-to-revenue gap** | **13.40%p** | A |
| 7 | extensive-margin 근사 기여 | 70.6% | A |
| 8 | 56일 future quantity (M3) | **+0.000158 (t=0.16)** → payback 없음 | A |
| 9 | 점추정 기준 cumulative ratio | ≈101.5% *(헤드라인 금지)* | A |
| 10 | Approx. CI-implied payback bound | ≈17.1% *(formal equivalence 아님)* | A |
| 11 | gross-margin scenario break-even | ≈40.34% | A량+가정 |
| 12 | 4B 28d whole-store spend association | −$4.56 (−1.63%) | B |
| 13 | 5B naive −$19.24 → FE −$1.35 | 약 93% 축소 | B |
| 14 | 첫 딥할인 후 28d / 56d 재구매율 | 33.55% / 49.73% | B |
| 15 | 재구매 중 정가 전환율 (56d) | 57.15% | B |
| 16 | 5A FDR 후 robust category | **0개 / 83개** | B |
| 17 | 5B FDR 후 negative High-level comparisons | 6 / 17 (지표별) | B |

---

# 10. 한계

1. **마진율 `m`은 가정이다.** 원가 데이터가 없다. 40.34%는 실측 손익분기가 아니라 조건부 임계값이며, vendor funding·rebate·전단지 제작배포비·운영비가 모두 빠져 있어 **실제 ROI로 해석할 수 없다.**
2. **PART B(4B/5A/5B/5C) 전체가 관측적이다.** 딥할인은 가구의 자기선택이며 어떤 숫자도 인과로 읽을 수 없다.
3. **`exp_any`는 category×store×week 수준의 ITT다.** 개별 가구의 실제 전단지 열람 여부는 알 수 없어, 실노출자 기준으로는 과소추정(희석)일 가능성이 있다.
4. **후속 전단지 노출은 통제하지 않았다**(post-treatment). 노출 anchor의 28일 내 재노출률 86.9% vs 미노출 41.7%. 주 결과는 natural-course ITT이며 이 교란은 M3 시간통제로 다뤘다.
5. **anchor 창이 서로 겹친다.** 오차 자기상관 때문에 household cluster SE가 필수이며, 2-way에서도 t=33~40을 유지한다.
6. **표본은 causal 115개 점포 × WEEK 9–101.** 점포 수로는 19.8%지만 매출로는 98.49% — 매출 비중으로 제시할 것.
7. **용량(pack size) 정보 부재.** "수량 증가가 대용량팩 선택 아니냐"는 반박에 직접 답할 수 없어 정가환산액을 병기했다.
8. **Phase 5B 사전창이 DAY 55에서 시작**한다(표본 최소 DAY). 가구 128곳(5.1%)은 사전활동이 없어 제외됐다.
9. **Phase 5A의 p값은 공표 CI에서 역산했다.** 원 스크립트가 CI를 `beta ± 1.96·se`로 구성했으므로 se는 정확히 복원되나, p는 t분포가 아닌 정규근사 기준이다(가구 클러스터 수가 많아 실질 차이는 미미).

---

# 11. 실행하지 않은 분석

| 항목 | 사유 | 위치 |
|---|---|---|
| Cox / AFT 생존분석 (frailty) | 20분+ | 추가 timing robustness로 남김 |
| Phase 3B-1 **28일 M3** | 1건 30분 | 56일 주결론에는 필요하지 않은 추가 robustness. **28일 horizon의 동일 강도 시간통제 결과는 미확인** |
| ④ `store×cat + WEEK` 전체 회귀 | 87분 | 추가 FE robustness로 남김. ③(+store×cat)은 +23.98%로 ①과 근접 |
| ⑧ SALES_VALUE beta / 흡수율 | 3중 FE 1건 30분+ | 시간통제 하 매출효과는 ⑤·⑥으로만 확인됨 |
| formal equivalence test | 사전 margin 설정 필요 | payback 상한은 근사 CI 환산으로만 제시 |

⚠️ **위 항목들이 결론을 바꾸지 않는다고 입증된 것은 아니다.** 주 결론(56일 payback 미관측)에
필요하지 않은 추가 robustness이며, 수행 시 정밀도와 적용 범위가 넓어진다.

---

# 12. 생성 파일

### 보고서 (`docs/`)
`00_design.md` (D1~D19) · `TEAM_HANDOFF.md` · `01_phase3b0_report.md` · `02_phase3b1_report.md` ·
`03_phase4a_report.md` · `04_phase4b_report.md` · `05_phase5a_report.md` · `06_phase5b_report.md` ·
`07_phase5c_report.md` · **`FINAL_integrated_report.md`** · **`FINAL_onepage_summary.md`**

### 최종 산출 (`outputs/tables/`)
**`FINAL_key_results.csv`** (21개) · `FINAL_phase4a_robustness.csv` (116행) · `FINAL_phase4a_ci.csv` ·
**`phase5a_category_portfolio.csv`** (FDR) · `phase5a_fdr_summary.csv` ·
**`phase5b_rfm_segments.csv`** (FDR) · `phase5b_fdr_summary.csv` ·
`phase4b_future28_results.csv` · `phase5c_margin_sensitivity.csv` ·
`phase5c_step3_trial_conversion.csv` · `phase5c_step4_discount_bands_summary.csv`

### Tableau (`outputs/tableau/`)
**`07_final_decision_matrix.csv`** · **`category_portfolio.csv`** (FDR) · **`customer_segments.csv`** (FDR) ·
`FINAL_tableau_headline.csv` · `FINAL_tableau_incrementality_curve.csv` ·
`FINAL_tableau_margin_scenarios.csv` · `FINAL_tableau_discount_bands.csv` · `FINAL_tableau_timecontrol.csv`

### 스크립트 (`src/`)
`phase4a_robustness.py` · `phase4b_deepdisc_future.py` · `phase5a_category_matrix.py` ·
`phase5b_01_build.py` · `phase5b_02_estimate.py` · `phase5c_step3_trial_to_conversion.py` ·
`phase5c_step4_discount_bands.py` · `phase7_tableau_build.py` ·
**`phase8_fdr_correction.py`** · **`phase8_final_tables.py`**
