CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_occ_all` AS
WITH cstore AS (SELECT DISTINCT store_id   FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
     cprod  AS (SELECT DISTINCT product_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
lines AS (
  SELECT f.household_key, f.commodity_desc AS category, f.day,
    LEAST(f.quantity, 20) AS qty_w, f.net_sales, f.gross_sales, f.retailer_funded_disc,
    COALESCE(c.mailer_ad,0)     AS mailer_ad,
    COALESCE(c.mailer_coupon,0) AS mailer_coupon,
    COALESCE(c.mailer_free,0)   AS mailer_free,
    COALESCE(c.display_any,0)   AS display_any
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN cstore USING (store_id)
  JOIN cprod  USING (product_id)
  LEFT JOIN `ybigta-505002.dunnhumby_mart.mart_causal_clean` c
    ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101
    AND f.commodity_desc NOT IN ('COUPON','MISC ITEMS','NO COMMODITY DESCRIPTION')
),
occ AS (
  SELECT household_key, category, day,
    SUM(qty_w) AS qty, SUM(net_sales) AS net, SUM(gross_sales) AS gross,
    SUM(retailer_funded_disc) AS disc,
    MAX(mailer_ad) AS exposed, MAX(mailer_coupon) AS has_coupon,
    MAX(mailer_free) AS has_free, MAX(display_any) AS has_display
  FROM lines GROUP BY 1,2,3
)
SELECT *, SAFE_DIVIDE(disc,gross) AS disc_rate
FROM occ WHERE has_coupon=0 AND has_free=0 AND has_display=0;

SELECT COUNT(*) AS occasions, COUNT(DISTINCT category) AS cats,
       COUNT(DISTINCT household_key) AS hh, ROUND(100*AVG(exposed),1) AS pct_exposed
FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`;
