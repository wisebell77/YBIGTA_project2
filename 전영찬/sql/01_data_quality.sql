-- Complete Journey promotion analysis: initial data-quality checks
-- Project: crucial-axon-503903-k2 / Dataset: dunnhumby

-- 1. Table inventory
SELECT table_id AS table_name, row_count, size_bytes
FROM `crucial-axon-503903-k2.dunnhumby.__TABLES__`
ORDER BY table_id;

-- 2. Core schemas
SELECT table_name, ordinal_position, column_name, data_type
FROM `crucial-axon-503903-k2.dunnhumby.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('transaction_data', 'product', 'causal_data', 'hh_demographic')
ORDER BY table_name, ordinal_position;

-- 3. Transaction coverage, signs, and product join integrity
SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT t.household_key) AS households,
  COUNT(DISTINCT t.BASKET_ID) AS baskets,
  COUNT(DISTINCT t.PRODUCT_ID) AS products,
  MIN(t.DAY) AS min_day,
  MAX(t.DAY) AS max_day,
  MIN(t.WEEK_NO) AS min_week,
  MAX(t.WEEK_NO) AS max_week,
  COUNTIF(t.QUANTITY < 0) AS negative_qty,
  COUNTIF(t.QUANTITY = 0) AS zero_qty,
  COUNTIF(t.SALES_VALUE < 0) AS negative_sales,
  COUNTIF(t.SALES_VALUE = 0) AS zero_sales,
  COUNTIF(t.RETAIL_DISC < 0) AS retail_disc_negative,
  COUNTIF(t.RETAIL_DISC > 0) AS retail_disc_positive,
  COUNTIF(t.RETAIL_DISC != 0) AS retail_disc_nonzero,
  MIN(t.RETAIL_DISC) AS retail_disc_min,
  MAX(t.RETAIL_DISC) AS retail_disc_max,
  COUNTIF(t.COUPON_DISC != 0) AS coupon_disc_nonzero,
  COUNTIF(t.COUPON_MATCH_DISC != 0) AS coupon_match_nonzero,
  COUNTIF(p.PRODUCT_ID IS NULL) AS product_join_missing
FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` AS t
LEFT JOIN `crucial-axon-503903-k2.dunnhumby.product` AS p
  ON t.PRODUCT_ID = p.PRODUCT_ID;

-- 4. Causal-data code distributions
SELECT 'mailer' AS variable, mailer AS code, COUNT(*) AS row_count
FROM `crucial-axon-503903-k2.dunnhumby.causal_data`
GROUP BY mailer
UNION ALL
SELECT 'display', display, COUNT(*)
FROM `crucial-axon-503903-k2.dunnhumby.causal_data`
GROUP BY display
ORDER BY variable, row_count DESC;

-- 5. Causal-data key uniqueness
WITH key_counts AS (
  SELECT PRODUCT_ID, STORE_ID, WEEK_NO, COUNT(*) AS n
  FROM `crucial-axon-503903-k2.dunnhumby.causal_data`
  GROUP BY 1, 2, 3
)
SELECT
  SUM(n) AS total_rows,
  COUNT(*) AS distinct_keys,
  SUM(n - 1) AS duplicate_rows,
  MAX(n) AS max_rows_per_key
FROM key_counts;
