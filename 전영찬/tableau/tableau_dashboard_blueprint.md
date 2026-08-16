# Tableau CRM 판촉 대시보드 설계안

## 연결할 파일

1. `tableau_segment_kpi.csv` — 고객가치 × 이탈위험 × 고객-카테고리 행동유형
2. `tableau_category_kpi.csv` — 상품 카테고리별 28일 방문·지출 효과
3. `tableau_rfm_stability.csv` — RFM 가중치별 고객가치 등급 안정성

원본 BigQuery에 직접 연결할 경우 대응 테이블은 다음과 같다.

- `dunnhumby.tableau_segment_kpi`
- `dunnhumby.tableau_category_kpi`
- `dunnhumby.tableau_rfm_stability`
- 상세 이벤트 드릴다운: `dunnhumby.crm_event_validation`

테이블은 생성일로부터 30일 후 만료되도록 설정되어 있다.

## 대시보드 1 — Executive Overview

### KPI 카드

- 검증 이벤트: 481,110
- 검증 가구: 2,464
- 분석 가능한 카테고리: 161
- RFM 세 가중치 완전 일치율: 80.45%

### 핵심 차트

1. **성과 4분면 산점도**
   - X: `visit_diff`
   - Y: `spend_diff`
   - 크기: `households`
   - 색상: `performance_quadrant`
   - 세부정보: `value_tier`, `cat_behavior`, `churn_risk`

2. **고객가치 등급별 성과 막대**
   - 열: `value_tier`
   - 행: `spend_diff`, `visit_diff`
   - 필터: `weight_method`, `cat_behavior`, `churn_risk`

3. **신뢰구간 표시**
   - 방문: `visit_ci_low`~`visit_ci_high`
   - 지출: `spend_ci_low`~`spend_ci_high`

## 대시보드 2 — CRM Strategy Matrix

### 행과 열

- 행: `value_tier`
- 열: `cat_behavior`
- 색상: `performance_quadrant`
- 라벨: `households`, `visit_diff`, `spend_diff`
- 페이지/필터: `churn_risk`, `weight_method`

### 행동유형

- C1 Stock-up risk
- C2 New trial
- C3 Regular-price repeat
- C4 Promotion responsive
- C5 Low-frequency/irregular

### 도구설명 권장 문구

- 가구 수
- 딥할인/정가 이벤트 수
- 28일 방문 차이와 95% CI
- 28일 매장지출 차이와 95% CI
- 성과 4분면

## 대시보드 3 — Category Portfolio

### 카테고리 4분면

- X: `visit_diff`
- Y: `spend_diff`
- 크기: `households`
- 색상: `performance_quadrant`
- 라벨: `COMMODITY_DESC`

### 필터 권장값

- `households >= 30`
- 신뢰도 확인 시 `ABS(spend_diff / spend_se) >= 1.96`
- 이벤트 표본 필터: `deep_events`, `full_events`

## 대시보드 4 — RFM Stability

- 행: `equal_value_tier`
- 열: `visit_value_tier` 또는 `spend_value_tier`
- 색상/텍스트: `events`
- 필터: `sample`

가중치 세 방식이 모두 같은 등급을 부여한 검증 이벤트는 80.45%다. 나머지 이벤트는 가중치 선택에 민감하므로 별도 표식이 필요하다.

## 해석 시 주의사항

- 결과는 동일 가구·카테고리에서 딥할인 구매와 정가 구매 이후를 비교한 진단적 연관성이다.
- 구매 여부 자체에 대한 판촉 효과는 측정하지 않는다.
- 성과 4분면은 0 기준이며, 반드시 신뢰구간을 함께 표시한다.
- 고객가치와 행동유형은 이벤트 이전 정보만 사용했다.
- 세그먼트 KPI의 표준오차는 가구별 차이를 먼저 만든 뒤 계산했다.
