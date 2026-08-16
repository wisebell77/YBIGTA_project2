-- =====================================================================
-- Phase 4-1. mart_basket — 바스켓 단위 진열 노출 마트
--
-- 발제서의 질문: "매장 내 진열을 바꿨을 때 연관 상품을 같이 샀는가?"
-- → 진열 상품 자체의 매출이 아니라 '장바구니 확장' 효과를 본다.
--
-- ★ 종속변수 설계의 핵심:
--   진열 상품의 매출을 포함하면 "진열하면 그 상품이 더 팔린다"는 동어반복이 된다.
--   반드시 진열 상품을 제외한 나머지 금액(nondisplay_sales)을 봐야
--   "진열이 다른 상품 구매까지 끌어냈는가"라는 질문에 답할 수 있다.
--
-- ★ causal_data 구조 전제 (직접 검증 완료):
--   display='0' 이면서 mailer='0' 인 행은 정확히 0건이다.
--   즉 이 테이블은 전체 패널이 아니라 프로모션이 걸린 건만 기록한 이벤트 로그다.
--   → (상품,점포,주차) 행이 없다 = 결측이 아니라 '프로모션 없음'.
--   → 반드시 LEFT JOIN 하고 매칭 실패를 FALSE로 채운다.
--
-- ★ 표본 한정: causal_data가 커버하는 점포·주차로만 제한한다.
--   커버 밖 구간을 섞으면 '진열 없음'과 '데이터 없음'이 구분되지 않는다.
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_basket`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(0, 110, 1))
CLUSTER BY household_key
AS
WITH causal_stores AS (
  SELECT DISTINCT store_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_psw`
),
lines AS (
  SELECT
    f.basket_id,
    f.household_key,
    f.store_id,
    f.week_no,
    f.day,
    f.net_sales,
    f.commodity_desc,
    f.department,
    -- 매칭 실패 = 프로모션 없음
    IFNULL(c.is_on_display, FALSE)      AS on_display,
    IFNULL(c.is_on_mailer,  FALSE)      AS on_mailer,
    IFNULL(c.is_premium_display, FALSE) AS on_premium_display
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN causal_stores s USING (store_id)
  LEFT JOIN `ybigta-505002.dunnhumby_mart.mart_causal_psw` c
    ON  f.product_id = c.product_id
    AND f.store_id   = c.store_id
    AND f.week_no    = c.week_no
  WHERE NOT f.is_zero_row
    AND f.week_no BETWEEN 9 AND 101      -- causal_data 커버 구간
)
SELECT
  basket_id,
  ANY_VALUE(household_key)                                   AS household_key,
  ANY_VALUE(store_id)                                         AS store_id,
  week_no,
  ANY_VALUE(day)                                              AS day,

  COUNT(*)                                                    AS n_lines,
  COUNT(DISTINCT commodity_desc)                              AS n_commodities,
  COUNT(DISTINCT department)                                  AS n_departments,
  SUM(net_sales)                                              AS basket_sales,

  -- ---- 진열 상품 / 비진열 상품 분해 ----
  COUNTIF(on_display)                                         AS n_display_lines,
  SUM(IF(on_display, net_sales, 0))                           AS display_sales,
  SUM(IF(NOT on_display, net_sales, 0))                       AS nondisplay_sales,
  COUNT(DISTINCT IF(NOT on_display, commodity_desc, NULL))    AS n_nondisplay_commodities,

  COUNTIF(on_premium_display)                                 AS n_premium_display_lines,
  COUNTIF(on_mailer)                                          AS n_mailer_lines,

  COUNTIF(on_display) > 0                                     AS has_display,
  COUNTIF(on_premium_display) > 0                             AS has_premium_display,
  COUNTIF(on_mailer) > 0                                      AS has_mailer

FROM lines
GROUP BY basket_id, week_no;
