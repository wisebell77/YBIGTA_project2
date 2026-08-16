-- Deduplicate causal_data before joining. A non-zero mailer code is exposure.
WITH causal AS (
  SELECT PRODUCT_ID, STORE_ID, WEEK_NO,
    LOGICAL_OR(mailer != '0') AS mailer_exposed
  FROM `crucial-axon-503903-k2.dunnhumby.causal_data`
  GROUP BY 1, 2, 3
),
lines AS (
  SELECT t.household_key, t.DAY, t.QUANTITY, t.SALES_VALUE, t.RETAIL_DISC,
    p.COMMODITY_DESC, COALESCE(c.mailer_exposed, FALSE) AS mailer_exposed
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` t
  JOIN `crucial-axon-503903-k2.dunnhumby.product` p USING (PRODUCT_ID)
  LEFT JOIN causal c
    ON t.PRODUCT_ID = c.PRODUCT_ID AND t.STORE_ID = c.STORE_ID
   AND t.WEEK_NO = c.WEEK_NO
  WHERE p.COMMODITY_DESC != 'COUPON/MISC ITEMS'
    AND t.QUANTITY > 0 AND t.SALES_VALUE - t.RETAIL_DISC > 0
),
occasions AS (
  SELECT household_key, COMMODITY_DESC, DAY,
    SUM(QUANTITY) AS quantity,
    SUM(SALES_VALUE) AS spend,
    SUM(SALES_VALUE - RETAIL_DISC) AS regular_value,
    SAFE_DIVIDE(-SUM(RETAIL_DISC), SUM(SALES_VALUE - RETAIL_DISC)) AS discount_rate,
    LOGICAL_OR(mailer_exposed) AS exposed
  FROM lines GROUP BY 1, 2, 3
),
eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM occasions GROUP BY 1, 2
  HAVING COUNT(*) >= 5 AND COUNTIF(exposed) >= 2 AND COUNTIF(NOT exposed) >= 2
),
pair_means AS (
  SELECT household_key, COMMODITY_DESC,
    AVG(IF(exposed, quantity, NULL)) - AVG(IF(NOT exposed, quantity, NULL)) AS qty_diff,
    AVG(IF(exposed, spend, NULL)) - AVG(IF(NOT exposed, spend, NULL)) AS spend_diff,
    AVG(IF(exposed, regular_value, NULL)) - AVG(IF(NOT exposed, regular_value, NULL)) AS regular_diff,
    AVG(IF(exposed, discount_rate, NULL)) - AVG(IF(NOT exposed, discount_rate, NULL)) AS first_stage
  FROM occasions JOIN eligible USING (household_key, COMMODITY_DESC)
  GROUP BY 1, 2
)
SELECT COUNT(*) AS pairs, AVG(qty_diff) AS qty_diff,
  AVG(spend_diff) AS spend_diff, AVG(regular_diff) AS regular_diff,
  AVG(first_stage) AS first_stage
FROM pair_means;

