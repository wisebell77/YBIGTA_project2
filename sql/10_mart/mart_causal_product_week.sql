CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_causal_product_week`
PARTITION BY RANGE_BUCKET(week_no, GENERATE_ARRAY(0, 110, 1))
CLUSTER BY product_id
AS
SELECT
  product_id,
  week_no,
  COUNT(DISTINCT store_id)                                  AS n_stores_carried,
  COUNTIF(is_on_display)                                    AS n_stores_display,
  COUNTIF(is_on_mailer)                                     AS n_stores_mailer,
  COUNTIF(is_premium_display)                               AS n_stores_premium_display,
  SAFE_DIVIDE(COUNTIF(is_on_display), COUNT(DISTINCT store_id)) AS display_penetration,
  SAFE_DIVIDE(COUNTIF(is_on_mailer),  COUNT(DISTINCT store_id)) AS mailer_penetration
FROM `ybigta-505002.dunnhumby_mart.mart_causal_psw`
GROUP BY product_id, week_no