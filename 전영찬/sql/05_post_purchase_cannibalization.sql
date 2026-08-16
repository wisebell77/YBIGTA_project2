-- Requires the output of 03_purchase_occasions.sql as `purchase_occasions`.
-- Restrict focal occasions to DAY <= 655 so every row has a full 56-day window.
WITH eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM purchase_occasions
  GROUP BY 1, 2
  HAVING COUNT(*) >= 5
     AND COUNTIF(is_deep_discount) >= 2
     AND COUNTIF(is_full_price) >= 2
),
focal AS (
  SELECT o.*
  FROM purchase_occasions o
  JOIN eligible USING (household_key, COMMODITY_DESC)
  WHERE DAY <= 655 AND (is_deep_discount OR is_full_price)
),
post AS (
  SELECT
    f.household_key, f.COMMODITY_DESC, f.DAY,
    f.is_deep_discount, f.is_full_price, f.quantity,
    SUM(IF(o.DAY > f.DAY AND o.DAY <= f.DAY + 28, o.quantity, 0)) AS post28,
    SUM(IF(o.DAY > f.DAY AND o.DAY <= f.DAY + 56, o.quantity, 0)) AS post56
  FROM focal f
  LEFT JOIN purchase_occasions o
    ON f.household_key = o.household_key
   AND f.COMMODITY_DESC = o.COMMODITY_DESC
   AND o.DAY > f.DAY AND o.DAY <= f.DAY + 56
  GROUP BY 1, 2, 3, 4, 5, 6
),
pair_means AS (
  SELECT
    household_key, COMMODITY_DESC,
    AVG(IF(is_deep_discount, quantity, NULL)) AS deep_now,
    AVG(IF(is_full_price, quantity, NULL)) AS full_now,
    AVG(IF(is_deep_discount, post28, NULL)) AS deep_post28,
    AVG(IF(is_full_price, post28, NULL)) AS full_post28,
    AVG(IF(is_deep_discount, post56, NULL)) AS deep_post56,
    AVG(IF(is_full_price, post56, NULL)) AS full_post56
  FROM post
  GROUP BY 1, 2
  HAVING COUNTIF(is_deep_discount) > 0 AND COUNTIF(is_full_price) > 0
)
SELECT
  COUNT(*) AS pairs,
  AVG(deep_now - full_now) AS immediate_increment,
  AVG(deep_post28 - full_post28) AS post28_diff,
  AVG(deep_post56 - full_post56) AS post56_diff,
  SAFE_DIVIDE(-AVG(deep_post56 - full_post56), AVG(deep_now - full_now)) AS cannibalization_56,
  1 - SAFE_DIVIDE(-AVG(deep_post56 - full_post56), AVG(deep_now - full_now)) AS incrementality_56
FROM pair_means;

