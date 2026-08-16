-- =====================================================================
-- Phase 2-3. mart_household_churn — 이탈 상태 정의
--
-- ★ 정의 원칙: 절대 기준이 아니라 "가구 자신의 통상 주기 대비" 상대 기준.
--   가구별 중앙 구매주기가 p10 2일 ~ p90 18일로 9배 차이가 난다.
--   "90일 미구매 = 이탈" 같은 전역 기준은 2일 주기 가구에겐 너무 늦고
--   18일 주기 가구에겐 과하게 이르다.
--
--   Churned : recency > max(3.0 × 자기 중앙주기, 30일)
--   At-risk : recency > max(1.5 × 자기 중앙주기, 14일)
--   Active  : 그 외
--   (최소 일수 하한은 초단주기 가구의 오탐을 막기 위한 것)
--
-- ★ 검증 설계: 정의가 실제로 '멈춤'을 잡아내는지 홀드아웃으로 확인한다.
--   관측창 DAY 1~547 만으로 상태를 판정하고(누수 없음),
--   홀드아웃 DAY 548~711(164일) 동안 실제로 안 왔는지 대조한다.
--   판정에 쓰는 중앙주기도 관측창 데이터만으로 다시 계산한다.
-- =====================================================================
CREATE TEMP FUNCTION churn_class(recency INT64, median_gap INT64) AS (
  CASE
    WHEN recency IS NULL OR median_gap IS NULL THEN 'Unknown'
    WHEN recency > GREATEST(CAST(3.0 * median_gap AS INT64), 30) THEN 'Churned'
    WHEN recency > GREATEST(CAST(1.5 * median_gap AS INT64), 14) THEN 'At-risk'
    ELSE 'Active'
  END
);

CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_household_churn`
CLUSTER BY household_key
AS
WITH purchase_days AS (
  SELECT DISTINCT household_key, day
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE NOT is_zero_row
),

-- ---- 전체 구간(DAY 1~711) 기준: 현재 상태 판정용 ----
gaps_full AS (
  SELECT household_key,
         day - LAG(day) OVER (PARTITION BY household_key ORDER BY day) AS gap_days
  FROM purchase_days
),
stats_full AS (
  SELECT household_key,
         APPROX_QUANTILES(gap_days, 100)[OFFSET(50)] AS median_gap,
         APPROX_QUANTILES(gap_days, 100)[OFFSET(90)] AS p90_gap,
         COUNT(gap_days)                             AS n_gaps
  FROM gaps_full WHERE gap_days IS NOT NULL
  GROUP BY household_key
),
rec_full AS (
  SELECT household_key,
         MIN(day)            AS first_day,
         MAX(day)            AS last_day,
         711 - MAX(day)      AS recency_days,
         COUNT(DISTINCT day) AS n_visits
  FROM purchase_days GROUP BY household_key
),

-- ---- 관측창(DAY 1~547) 기준: 홀드아웃 검증용. 미래 정보 누수 없음 ----
gaps_obs AS (
  SELECT household_key,
         day - LAG(day) OVER (PARTITION BY household_key ORDER BY day) AS gap_days
  FROM purchase_days WHERE day <= 547
),
stats_obs AS (
  SELECT household_key,
         APPROX_QUANTILES(gap_days, 100)[OFFSET(50)] AS median_gap_obs
  FROM gaps_obs WHERE gap_days IS NOT NULL
  GROUP BY household_key
),
rec_obs AS (
  SELECT household_key,
         MAX(day)            AS last_day_obs,
         547 - MAX(day)      AS recency_obs,
         COUNT(DISTINCT day) AS n_visits_obs
  FROM purchase_days WHERE day <= 547
  GROUP BY household_key
),

-- ---- 홀드아웃 구간(DAY 548~711) 실제 행동 ----
holdout AS (
  SELECT household_key,
         COUNT(DISTINCT day)  AS n_visits_holdout,
         SUM(net_sales)       AS sales_holdout
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day BETWEEN 548 AND 711 AND NOT is_zero_row
  GROUP BY household_key
)

SELECT
  h.household_key,

  -- ---- 전체 구간 기준 현재 상태 ----
  s.median_gap,
  s.p90_gap,
  IFNULL(s.n_gaps, 0)                       AS n_gaps,
  r.first_day,
  r.last_day,
  r.recency_days,
  r.n_visits,
  churn_class(r.recency_days, s.median_gap) AS churn_status,

  -- ---- 관측창 기준 상태 (검증용) ----
  so.median_gap_obs,
  ro.recency_obs,
  ro.n_visits_obs,
  churn_class(ro.recency_obs, so.median_gap_obs) AS churn_status_at_547,

  -- ---- 홀드아웃 실제 결과 ----
  IFNULL(ho.n_visits_holdout, 0)            AS n_visits_holdout,
  IFNULL(ho.sales_holdout, 0.0)             AS sales_holdout,
  IFNULL(ho.n_visits_holdout, 0) > 0        AS purchased_in_holdout

FROM `ybigta-505002.dunnhumby_mart.dim_household` h
LEFT JOIN stats_full s  USING (household_key)
LEFT JOIN rec_full   r  USING (household_key)
LEFT JOIN stats_obs  so USING (household_key)
LEFT JOIN rec_obs    ro USING (household_key)
LEFT JOIN holdout    ho USING (household_key);
