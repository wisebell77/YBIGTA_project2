-- Run after substituting 03_purchase_occasions.sql for purchase_occasions,
-- or after materializing it as a table/view with that name.
WITH pair_stats AS (
  SELECT
    household_key,
    COMMODITY_DESC,
    COUNT(*) AS occasions,
    COUNTIF(is_deep_discount) AS deep_n,
    COUNTIF(is_full_price) AS full_n
  FROM purchase_occasions
  GROUP BY 1, 2
)
SELECT
  COUNTIF(occasions >= 5) AS pairs_ge5,
  COUNTIF(occasions >= 5 AND deep_n >= 1 AND full_n >= 1) AS pairs_loose,
  COUNTIF(occasions >= 5 AND deep_n >= 2 AND full_n >= 2) AS pairs_main,
  COUNT(DISTINCT IF(
    occasions >= 5 AND deep_n >= 2 AND full_n >= 2,
    household_key,
    NULL
  )) AS main_households,
  COUNT(DISTINCT IF(
    occasions >= 5 AND deep_n >= 2 AND full_n >= 2,
    COMMODITY_DESC,
    NULL
  )) AS main_categories
FROM pair_stats;
