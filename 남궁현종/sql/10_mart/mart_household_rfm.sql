-- =====================================================================
-- Phase 1-1. mart_household_rfm — RFM + 추세(T) 세그먼테이션
--
-- ★ 표준 RFM에 '추세' 축을 추가하는 이유:
--   Phase 2에서 최상위 분위(V5, 매출의 55%)가 연 -$117,941 감소하고 있고,
--   그 손실의 78%가 '아직 활발히 구매 중'인 가구에서 나온다는 것을 확인했다.
--   R/F/M만 쓰면 이 가구들은 전부 Champions로 분류돼 '건강함'으로 보인다.
--   침식이 시작된 시점에는 R도 F도 M도 아직 높기 때문이다.
--   → 반기 대비 성장률(T)을 넣어야 손실이 커지기 전에 잡아낼 수 있다.
--
-- 기간: DAY 127~711 (온보딩 완료 이후 전 구간)
--   H1 DAY 127~419 (41.9주) / H2 DAY 420~711 (41.7주)
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_household_rfm`
CLUSTER BY household_key
AS
WITH activity AS (
  SELECT
    household_key,
    COUNT(DISTINCT day)                                       AS frequency,
    SUM(net_sales)                                            AS monetary,
    SUM(retailer_funded_disc)                                 AS disc_received,
    SUM(gross_sales)                                          AS gross,
    MAX(day)                                                  AS last_day,
    SUM(IF(day BETWEEN 127 AND 419, net_sales, 0)) / 41.9     AS h1_weekly,
    SUM(IF(day BETWEEN 420 AND 711, net_sales, 0)) / 41.7     AS h2_weekly
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day BETWEEN 127 AND 711 AND NOT is_zero_row
  GROUP BY household_key
),
scored AS (
  SELECT
    h.household_key,
    IFNULL(a.frequency, 0)                                    AS frequency,
    IFNULL(a.monetary, 0.0)                                   AS monetary,
    IFNULL(a.disc_received, 0.0)                              AS disc_received,
    IFNULL(a.gross, 0.0)                                      AS gross,
    711 - a.last_day                                          AS recency,
    a.h1_weekly,
    a.h2_weekly,
    -- 추세: 반기 대비 주당 매출 증감률. H1이 0이면 정의 불가(NULL).
    SAFE_DIVIDE(a.h2_weekly - a.h1_weekly, NULLIF(a.h1_weekly, 0)) AS trend,

    -- R은 낮을수록 좋으므로 정렬을 뒤집는다
    NTILE(5) OVER (ORDER BY 711 - a.last_day DESC)            AS r_score,
    NTILE(5) OVER (ORDER BY IFNULL(a.frequency, 0))           AS f_score,
    NTILE(5) OVER (ORDER BY IFNULL(a.monetary, 0))            AS m_score
  FROM `ybigta-505002.dunnhumby_mart.dim_household` h
  LEFT JOIN activity a USING (household_key)
)
SELECT
  s.*,
  s.r_score + s.f_score + s.m_score                           AS rfm_total,

  -- 할인 의존도: 이 가구가 받은 매출 대비 할인 비율.
  -- 높은데 매출이 감소 중이면 '할인으로만 붙잡고 있는' 고객이다.
  SAFE_DIVIDE(s.disc_received, s.gross)                       AS disc_dependency,

  -- ---- 세그먼트 ----
  -- 가치(M)를 1축, 추세(T)를 2축으로 놓는다. 순서대로 평가되므로 상호배타적이다.
  CASE
    WHEN s.monetary = 0                          THEN '00_무활동'
    WHEN s.m_score >= 4 AND s.trend <= -0.10     THEN '01_핵심_침식'   -- ★ 최우선 타겟
    WHEN s.m_score >= 4 AND s.r_score <= 2       THEN '02_핵심_이탈징후'
    WHEN s.m_score >= 4                          THEN '03_핵심_안정'
    WHEN s.m_score = 3  AND s.trend <= -0.10     THEN '04_중간_침식'
    WHEN s.m_score = 3                           THEN '05_중간_안정'
    WHEN s.r_score >= 4 AND s.f_score <= 2       THEN '06_신규_저빈도'
    WHEN s.r_score <= 2                          THEN '07_휴면'
    ELSE                                              '08_일반'
  END                                                          AS segment

FROM scored s;
