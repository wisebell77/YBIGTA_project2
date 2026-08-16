-- Purchase occasions and within-household/category repurchase intervals.
-- Grain: household x commodity x day.

WITH line_base AS (
  SELECT
    t.household_key,
    t.DAY,
    t.WEEK_NO,
    t.BASKET_ID,
    t.QUANTITY,
    t.SALES_VALUE,
    t.RETAIL_DISC,
    p.COMMODITY_DESC
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` AS t
  JOIN `crucial-axon-503903-k2.dunnhumby.product` AS p USING (PRODUCT_ID)
  WHERE p.COMMODITY_DESC != 'COUPON/MISC ITEMS'
    AND t.QUANTITY > 0
    AND t.SALES_VALUE - t.RETAIL_DISC > 0
),

-- A visit is a distinct shopping day for a household. This avoids counting
-- multiple baskets recorded on the same day as separate trips.
visits AS (
  SELECT
    household_key,
    DAY,
    DENSE_RANK() OVER (PARTITION BY household_key ORDER BY DAY) AS visit_no
  FROM (SELECT DISTINCT household_key, DAY FROM line_base)
),

occasion_base AS (
  SELECT
    l.household_key,
    l.COMMODITY_DESC,
    l.DAY,
    ANY_VALUE(v.visit_no) AS visit_no,
    SUM(l.QUANTITY) AS quantity,
    SUM(l.SALES_VALUE) AS actual_spend,
    SUM(l.SALES_VALUE - l.RETAIL_DISC) AS regular_price_value,
    SAFE_DIVIDE(
      -SUM(l.RETAIL_DISC),
      SUM(l.SALES_VALUE - l.RETAIL_DISC)
    ) AS retail_discount_rate
  FROM line_base AS l
  JOIN visits AS v USING (household_key, DAY)
  GROUP BY 1, 2, 3
)

SELECT
  *,
  retail_discount_rate >= 0.30 AS is_deep_discount,
  retail_discount_rate <= 0.02 AS is_full_price,
  LEAD(DAY) OVER (
    PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY
  ) - DAY AS days_to_next_purchase,
  LEAD(visit_no) OVER (
    PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY
  ) - visit_no AS visits_to_next_purchase
FROM occasion_base;

