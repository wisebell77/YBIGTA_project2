-- Discount-rate sensitivity checks.
WITH x AS (
  SELECT
    SAFE_DIVIDE(-RETAIL_DISC, SALES_VALUE - RETAIL_DISC) AS discount_rate,
    SALES_VALUE
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data`
  WHERE RETAIL_DISC < 0
    AND SALES_VALUE - RETAIL_DISC > 0
)
SELECT
  COUNT(*) AS valid_discount_lines,
  APPROX_QUANTILES(discount_rate, 100)[OFFSET(25)] AS p25,
  APPROX_QUANTILES(discount_rate, 100)[OFFSET(50)] AS median,
  APPROX_QUANTILES(discount_rate, 100)[OFFSET(75)] AS p75,
  APPROX_QUANTILES(discount_rate, 100)[OFFSET(90)] AS p90,
  APPROX_QUANTILES(discount_rate, 100)[OFFSET(99)] AS p99,
  COUNTIF(discount_rate >= 0.20) AS ge_20pct,
  COUNTIF(discount_rate >= 0.30) AS ge_30pct,
  COUNTIF(discount_rate >= 0.40) AS ge_40pct,
  COUNTIF(discount_rate > 1) AS over_100pct
FROM x;
