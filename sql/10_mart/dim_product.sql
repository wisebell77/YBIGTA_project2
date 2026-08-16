-- =====================================================================
-- 02. dim_product — 상품 마스터 (92,353행)
--
-- 쿠폰 대상 여부를 여기서 미리 붙여둔다. 캠페인 효과 분석에서
-- "쿠폰 대상 상품의 매출만" 보는 쿼리가 반복적으로 필요하기 때문.
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.dim_product`
CLUSTER BY product_id
AS
WITH coupon_agg AS (
  SELECT
    PRODUCT_ID                              AS product_id,
    COUNT(DISTINCT COUPON_UPC)              AS n_coupons,
    COUNT(DISTINCT CAMPAIGN)                AS n_coupon_campaigns,
    ARRAY_AGG(DISTINCT CAMPAIGN ORDER BY CAMPAIGN) AS coupon_campaigns
  FROM `ybigta-505002.sql_study.coupon`
  GROUP BY product_id
)
SELECT
  p.PRODUCT_ID                              AS product_id,
  p.MANUFACTURER                            AS manufacturer,
  TRIM(p.DEPARTMENT)                        AS department,
  TRIM(p.BRAND)                             AS brand,
  TRIM(p.COMMODITY_DESC)                    AS commodity_desc,
  TRIM(p.SUB_COMMODITY_DESC)                AS sub_commodity_desc,
  TRIM(p.CURR_SIZE_OF_PRODUCT)              AS curr_size,

  -- Private(PL) vs National(NB) — 마진 구조가 달라 전략 제안에서 갈리는 축
  TRIM(p.BRAND) = 'Private'                 AS is_private_label,

  -- product.csv에는 설명이 비어 있는 더미 행이 다수 존재한다. 집계 전에 걸러낼 것.
  TRIM(p.COMMODITY_DESC) IN ('NO COMMODITY DESCRIPTION', '')
    OR p.COMMODITY_DESC IS NULL             AS is_placeholder_desc,

  -- ---- 쿠폰 대상 여부 ----
  IFNULL(c.n_coupons, 0)                    AS n_coupons,
  IFNULL(c.n_coupon_campaigns, 0)           AS n_coupon_campaigns,
  c.coupon_campaigns,
  IFNULL(c.n_coupons, 0) > 0                AS is_coupon_target

FROM `ybigta-505002.sql_study.product` p
LEFT JOIN coupon_agg c ON p.PRODUCT_ID = c.product_id;


-- 검증: 92,353행 / is_coupon_target 개수 / department 분포
-- SELECT COUNT(*) n, COUNTIF(is_coupon_target) n_coupon, COUNTIF(is_private_label) n_pl,
--        COUNTIF(is_placeholder_desc) n_placeholder
-- FROM `ybigta-505002.dunnhumby_mart.dim_product`;
