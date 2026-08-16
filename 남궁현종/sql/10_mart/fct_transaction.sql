-- =====================================================================
-- 03. fct_transaction — 라인아이템 팩트 (2,595,732행)
--
-- 이 프로젝트의 중심 테이블. 이후 모든 분석이 여기서 출발한다.
--
-- ★ 핵심 설계: 매출을 "정가 / 리테일러 수취 / 고객 지불 / 할인"으로 분해한다.
--   할인 3개 컬럼은 모두 음수 저장 (2,595,732행 전수 검증 완료).
--     정가 gross = SALES_VALUE - RETAIL_DISC - COUPON_MATCH_DISC
--   이 분해가 있어야 "매출은 늘었는데 마진은 깎였다"를 잡아낼 수 있고,
--   그게 '마케팅 효율 최적화'라는 주제의 핵심 논거가 된다.
--
-- ★ SALES_VALUE의 정확한 의미 (공식 User Guide):
--   "Amount of dollars retailer receives from sale" — **리테일러 수취액**이지
--   고객이 낸 금액이 아니다. 제조사 쿠폰을 쓰면 제조사가 리테일러에게 그 금액을
--   보전해주므로, 고객 지불액 < SALES_VALUE 가 된다.
--     고객 지불 = SALES_VALUE - |COUPON_DISC|
--   User Guide 예시로 확인: sales_value 2.89, coupon_disc -0.55
--     → 고객은 $2.34를 냈지만 리테일러는 $2.89를 받는다.
--   COUPON_DISC 총액이 매출의 0.53%라 집계 수준 영향은 작지만, 개념은 구분해야 한다.
--
-- ★ 정가 공식 검증 (User Guide 4p 예시 표):
--   Line2: sales_value 2, retail_disc -1.34, qty 2 → 정가 (2+1.34)/2 = 1.67
--   Line3: sales_value 2.89, coupon_match -0.45, qty 2 → 정가 (2.89+0.45)/2 = 1.67
--   아래 gross_sales 공식이 두 예시 모두와 일치한다.
--   (참고: User Guide 본문의 'Loyalty card price / Non-loyalty card price' 두 불릿은
--    같은 문서의 예시와 라벨이 서로 뒤바뀌어 있다. 예시 쪽이 옳으므로 예시를 따랐다.)
--
-- ★ 비용 귀속:
--   RETAIL_DISC, COUPON_MATCH_DISC → 리테일러가 부담 (전체 -$1,405,911, 정가의 14.9%)
--   COUPON_DISC                    → 제조사가 부담 (전체 -$42,612, 정가의 0.5%)
--   따라서 리테일러의 마케팅 비용은 쿠폰이 아니라 로열티 할인이 33배 지배적이다.
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.fct_transaction`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(0, 110, 1))
CLUSTER BY household_key, product_id
AS
WITH base AS (
  SELECT
    t.household_key,
    t.BASKET_ID           AS basket_id,
    t.DAY                 AS day,
    t.WEEK_NO             AS week_no,
    t.PRODUCT_ID          AS product_id,
    t.STORE_ID            AS store_id,
    t.TRANS_TIME          AS trans_time,
    t.QUANTITY            AS quantity,
    t.SALES_VALUE         AS sales_value,

    -- 할인을 양수 크기로 변환 (음수 부호를 매번 신경쓰지 않도록)
    -RETAIL_DISC          AS retail_disc_amt,
    -COUPON_DISC          AS coupon_disc_amt,
    -COUPON_MATCH_DISC    AS coupon_match_disc_amt
  FROM `ybigta-505002.sql_study.transaction_data` t
)
SELECT
  b.household_key,
  b.basket_id,
  b.day,
  b.week_no,
  b.product_id,
  b.store_id,
  b.quantity,

  -- ---- 시간 파생 ----
  -- 실제 달력 날짜가 없다. DAY는 1~711 정수이므로 '상대 요일'만 만들 수 있다.
  -- 절대 요일(월/화/…)은 알 수 없으므로 요일명을 붙이지 말 것.
  MOD(b.day - 1, 7)                                   AS rel_dow,
  DIV(b.trans_time, 100)                              AS trans_hour,
  b.trans_time,

  -- ---- 금액 분해 ----
  b.sales_value                                       AS net_sales,   -- 리테일러 수취액 (분석의 주 매출 지표)
  b.sales_value - b.coupon_disc_amt                   AS customer_paid, -- 고객이 실제로 낸 금액
  b.sales_value + b.retail_disc_amt + b.coupon_match_disc_amt
                                                      AS gross_sales, -- 정가 기준 매출
  b.retail_disc_amt,
  b.coupon_disc_amt,
  b.coupon_match_disc_amt,
  b.retail_disc_amt + b.coupon_match_disc_amt         AS retailer_funded_disc, -- 리테일러 부담분
  b.coupon_disc_amt                                   AS vendor_funded_disc,   -- 제조사 부담분

  -- 이상행(아래 is_price_anomaly)은 할인율이 음수로 나와 평균을 오염시키므로 NULL 처리.
  -- 금액 컬럼 자체는 원본을 보존한다(합계가 원본과 어긋나면 안 되므로).
  IF(b.retail_disc_amt < 0 OR b.coupon_match_disc_amt < 0,
     NULL,
     SAFE_DIVIDE(
       b.retail_disc_amt + b.coupon_match_disc_amt,
       b.sales_value + b.retail_disc_amt + b.coupon_match_disc_amt
     ))                                               AS disc_rate,

  -- ---- 단가 ----
  -- QUANTITY=0(약 0.6%)과 중량판매 이상치(QUANTITY>1000)는 단가를 NULL로 둔다.
  -- 0으로 나누거나 말도 안 되는 단가가 평균을 오염시키는 것을 막는다.
  IF(b.quantity BETWEEN 1 AND 1000,
     SAFE_DIVIDE(b.sales_value, b.quantity), NULL)    AS unit_paid_price,
  IF(b.quantity BETWEEN 1 AND 1000,
     SAFE_DIVIDE(b.sales_value + b.retail_disc_amt + b.coupon_match_disc_amt, b.quantity), NULL)
                                                      AS unit_regular_price,

  -- ---- 플래그 ----
  b.retail_disc_amt > 0                               AS has_retail_disc,
  b.coupon_disc_amt > 0                               AS has_coupon,
  b.quantity = 0 OR b.sales_value = 0                 AS is_zero_row,
  b.quantity > 1000                                   AS is_bulk_outlier,

  -- ★ 원본 RETAIL_DISC가 양수인 행이 36건 존재한다(할인이 아니라 가산 = 반품/보정 추정).
  --   내역: 26건은 0.005달러 미만의 부동소수점 노이즈라 실질 영향이 없고,
  --         10건이 실제로 '정가 < 실지불' 모순을 만든다(최대 -$3.99).
  --   36건 중 30건은 QUANTITY=0인 이상행과 중복. 합산 매출은 $20.42로 전체의 0.0003%.
  --   금액 컬럼은 원본을 보존하되(합계 정합성), 단가·할인율 분석에서는 이 플래그로 제외할 것.
  --   COUPON_MATCH_DISC에는 부호 이상이 없다(0건). 조건에 포함한 것은 방어적 목적.
  b.retail_disc_amt < 0 OR b.coupon_match_disc_amt < 0 AS is_price_anomaly,

  -- ---- 상품 속성 비정규화 ----
  -- 2.6M행이라 저장 비용이 미미하고, 다운스트림 쿼리에서 조인 하나를 매번 없애준다.
  p.department,
  p.commodity_desc,
  p.sub_commodity_desc,
  p.brand,
  p.is_private_label,
  p.is_coupon_target

FROM base b
LEFT JOIN `ybigta-505002.dunnhumby_mart.dim_product` p USING (product_id);


-- 검증 1: 행 수 보존 + 금액 합계
--   기대: n=2,595,732 / net≈8,057,463 / gross≈9,463,374 / retailer_disc≈1,405,911
-- SELECT COUNT(*) n, ROUND(SUM(net_sales)) net, ROUND(SUM(gross_sales)) gross,
--        ROUND(SUM(retailer_funded_disc)) retailer_disc, ROUND(SUM(vendor_funded_disc)) vendor_disc,
--        ROUND(SUM(retailer_funded_disc)/SUM(gross_sales), 4) overall_disc_rate
-- FROM `ybigta-505002.dunnhumby_mart.fct_transaction`;

-- 검증 2: 정가 >= 실지불이 100% 성립하는가 (부호 로직 재확인)
-- SELECT COUNTIF(gross_sales < net_sales) AS violations FROM `ybigta-505002.dunnhumby_mart.fct_transaction`;
