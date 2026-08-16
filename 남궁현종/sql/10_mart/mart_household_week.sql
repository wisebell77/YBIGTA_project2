-- =====================================================================
-- 04. mart_household_week — 가구 × 주차 스파인 (2,500 × 102 = 255,000행)
--
-- ★ 이 프로젝트에서 가장 중요한 설계 결정:
--   거래를 그냥 GROUP BY 하면 "구매가 없던 주"가 행 자체로 존재하지 않는다.
--   그러면 이탈 분석에서 공백 구간이 사라지고, DiD에서는 처치군/대조군의
--   0 매출 주차가 누락돼 효과가 체계적으로 과대추정된다.
--   → 전체 가구 × 전체 주차를 CROSS JOIN으로 먼저 깔고 거래를 LEFT JOIN 한다.
--
-- 이 테이블 하나로 Phase 2(이탈)와 Phase 3(DiD)를 모두 처리한다.
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_household_week`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(0, 110, 1))
CLUSTER BY household_key
AS
WITH spine AS (
  -- 구매가 없는 주차까지 포함한 완전한 격자
  SELECT h.household_key, w AS week_no
  FROM (SELECT household_key FROM `ybigta-505002.dunnhumby_mart.dim_household`) h
  CROSS JOIN UNNEST(GENERATE_ARRAY(1, 102)) AS w
),
weekly AS (
  SELECT
    household_key,
    week_no,
    COUNT(DISTINCT basket_id)                 AS n_baskets,
    COUNT(*)                                  AS n_lines,
    COUNT(DISTINCT product_id)                AS n_distinct_products,
    COUNT(DISTINCT store_id)                  AS n_stores,
    SUM(quantity)                             AS total_quantity,
    SUM(net_sales)                            AS net_sales,
    SUM(gross_sales)                          AS gross_sales,
    SUM(retailer_funded_disc)                 AS retailer_funded_disc,
    SUM(vendor_funded_disc)                   AS vendor_funded_disc,
    MIN(day)                                  AS first_day_in_week,
    MAX(day)                                  AS last_day_in_week
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  GROUP BY household_key, week_no
),
joined AS (
  SELECT
    s.household_key,
    s.week_no,
    IFNULL(w.n_baskets, 0)                    AS n_baskets,
    IFNULL(w.n_lines, 0)                      AS n_lines,
    IFNULL(w.n_distinct_products, 0)          AS n_distinct_products,
    IFNULL(w.n_stores, 0)                     AS n_stores,
    IFNULL(w.total_quantity, 0)               AS total_quantity,
    IFNULL(w.net_sales, 0.0)                  AS net_sales,
    IFNULL(w.gross_sales, 0.0)                AS gross_sales,
    IFNULL(w.retailer_funded_disc, 0.0)       AS retailer_funded_disc,
    IFNULL(w.vendor_funded_disc, 0.0)         AS vendor_funded_disc,
    w.first_day_in_week,
    w.last_day_in_week,
    w.n_baskets IS NOT NULL                   AS has_purchase
  FROM spine s
  LEFT JOIN weekly w
    ON s.household_key = w.household_key AND s.week_no = w.week_no
)
SELECT
  j.*,

  -- ---- 이탈 분석용 파생 (Phase 2) ----
  -- 마지막 구매 주차: 이번 주 포함 과거 구간에서 구매가 있었던 가장 최근 주
  LAST_VALUE(IF(j.has_purchase, j.week_no, NULL) IGNORE NULLS)
    OVER (PARTITION BY j.household_key ORDER BY j.week_no
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)     AS last_purchase_week,

  -- 마지막 구매 이후 경과 주차 (0이면 이번 주에 구매)
  j.week_no - LAST_VALUE(IF(j.has_purchase, j.week_no, NULL) IGNORE NULLS)
    OVER (PARTITION BY j.household_key ORDER BY j.week_no
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)     AS weeks_since_last_purchase,

  -- 가구별 최초/최종 구매 주차 (전체 구간 기준) — 신규/이탈 구분에 사용
  MIN(IF(j.has_purchase, j.week_no, NULL)) OVER (PARTITION BY j.household_key) AS first_ever_week,
  MAX(IF(j.has_purchase, j.week_no, NULL)) OVER (PARTITION BY j.household_key) AS last_ever_week,

  -- 누적 매출 — 코호트/생애가치 분석용
  SUM(j.net_sales) OVER (PARTITION BY j.household_key ORDER BY j.week_no
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)     AS cum_net_sales

FROM joined j;


-- 검증 1: 행 수 = 2,500 × 102 = 255,000 (스파인이 제대로 깔렸는가)
-- SELECT COUNT(*) n_rows, COUNT(DISTINCT household_key) n_hh,
--        COUNT(DISTINCT week_no) n_weeks, COUNTIF(has_purchase) n_active_weeks,
--        ROUND(COUNTIF(has_purchase)/COUNT(*), 3) pct_active
-- FROM `ybigta-505002.dunnhumby_mart.mart_household_week`;

-- 검증 2: 매출 합계가 fct_transaction과 일치하는가 (스파인 조인으로 유실/중복이 없는가)
-- SELECT ROUND(SUM(net_sales)) FROM `ybigta-505002.dunnhumby_mart.mart_household_week`;  -- ≈ 8,057,463

-- 참고: 구매 간격 분포 — Phase 2의 이탈 기준(며칠 미구매) 근거가 되는 쿼리
-- SELECT APPROX_QUANTILES(weeks_since_last_purchase, 100)[OFFSET(50)] AS p50,
--        APPROX_QUANTILES(weeks_since_last_purchase, 100)[OFFSET(90)] AS p90,
--        APPROX_QUANTILES(weeks_since_last_purchase, 100)[OFFSET(95)] AS p95
-- FROM `ybigta-505002.dunnhumby_mart.mart_household_week` WHERE last_purchase_week IS NOT NULL;
