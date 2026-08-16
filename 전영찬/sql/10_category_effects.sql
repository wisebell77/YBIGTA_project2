-- Category-level heterogeneous effects; retain categories with >=100 pairs.
WITH eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM purchase_occasions GROUP BY 1, 2
  HAVING COUNT(*) >= 5
     AND COUNTIF(is_deep_discount) >= 2
     AND COUNTIF(is_full_price) >= 2
),
pair_means AS (
  SELECT household_key, COMMODITY_DESC,
    AVG(IF(is_deep_discount, quantity, NULL)) - AVG(IF(is_full_price, quantity, NULL)) AS qty_diff,
    AVG(IF(is_deep_discount, actual_spend, NULL)) - AVG(IF(is_full_price, actual_spend, NULL)) AS spend_diff,
    AVG(IF(is_deep_discount, days_to_next_purchase, NULL)) - AVG(IF(is_full_price, days_to_next_purchase, NULL)) AS days_diff
  FROM purchase_occasions JOIN eligible USING (household_key, COMMODITY_DESC)
  GROUP BY 1, 2
)
SELECT COMMODITY_DESC, COUNT(*) AS pairs,
  AVG(qty_diff) AS qty_diff, AVG(spend_diff) AS spend_diff, AVG(days_diff) AS days_diff
FROM pair_means
GROUP BY 1 HAVING COUNT(*) >= 100
ORDER BY spend_diff;

