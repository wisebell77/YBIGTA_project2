-- Template: cross join thresholds [0.20, 0.30, 0.40] to test robustness.
-- Customer affinity quintile is based on each household's deep-discount share.
WITH thresholds AS (SELECT x AS threshold FROM UNNEST([0.20, 0.30, 0.40]) x),
eligible AS (
  SELECT threshold, household_key, COMMODITY_DESC
  FROM purchase_occasions CROSS JOIN thresholds
  GROUP BY 1, 2, 3
  HAVING COUNT(*) >= 5
     AND COUNTIF(retail_discount_rate >= threshold) >= 2
     AND COUNTIF(is_full_price) >= 2
)
SELECT threshold, COUNT(*) AS eligible_pairs
FROM eligible GROUP BY threshold ORDER BY threshold;

