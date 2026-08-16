-- Customer discount-affinity quintiles and heterogeneous deep-discount effects.
WITH affinity_base AS (
  SELECT household_key,
    AVG(retail_discount_rate) AS avg_discount_rate,
    COUNTIF(is_deep_discount) / COUNT(*) AS deep_share
  FROM purchase_occasions GROUP BY 1
),
affinity AS (
  SELECT *, NTILE(5) OVER (ORDER BY deep_share, avg_discount_rate) AS affinity_q
  FROM affinity_base
),
eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM purchase_occasions GROUP BY 1, 2
  HAVING COUNT(*) >= 5
     AND COUNTIF(is_deep_discount) >= 2
     AND COUNTIF(is_full_price) >= 2
),
pair_means AS (
  SELECT o.household_key, o.COMMODITY_DESC, ANY_VALUE(a.affinity_q) AS affinity_q,
    AVG(IF(is_deep_discount, quantity, NULL)) - AVG(IF(is_full_price, quantity, NULL)) AS qty_diff,
    AVG(IF(is_deep_discount, actual_spend, NULL)) - AVG(IF(is_full_price, actual_spend, NULL)) AS spend_diff,
    AVG(IF(is_deep_discount, days_to_next_purchase, NULL)) - AVG(IF(is_full_price, days_to_next_purchase, NULL)) AS days_diff
  FROM purchase_occasions o
  JOIN eligible USING (household_key, COMMODITY_DESC)
  JOIN affinity a USING (household_key)
  GROUP BY 1, 2
)
SELECT affinity_q, COUNT(*) AS pairs, COUNT(DISTINCT household_key) AS households,
  AVG(qty_diff) AS qty_diff, AVG(spend_diff) AS spend_diff, AVG(days_diff) AS days_diff
FROM pair_means GROUP BY 1 ORDER BY 1;

