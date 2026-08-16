-- Marginal Kaplan-Meier curves. These are descriptive because occasions repeat
-- within households and the deep/full groups differ in category composition.
WITH eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM purchase_occasions
  GROUP BY 1, 2
  HAVING COUNT(*) >= 5
     AND COUNTIF(is_deep_discount) >= 2
     AND COUNTIF(is_full_price) >= 2
),
survival_rows AS (
  SELECT
    IF(is_deep_discount, 'deep', 'full') AS grp,
    LEAST(COALESCE(DAY + days_to_next_purchase, 711), 711) - DAY AS duration,
    days_to_next_purchase IS NOT NULL AS event
  FROM purchase_occasions
  JOIN eligible USING (household_key, COMMODITY_DESC)
  WHERE is_deep_discount OR is_full_price
),
time_counts AS (
  SELECT grp, duration, COUNT(*) AS total, COUNTIF(event) AS deaths
  FROM survival_rows GROUP BY 1, 2
),
hazards AS (
  SELECT *,
    SUM(total) OVER (
      PARTITION BY grp ORDER BY duration
      ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
    ) AS at_risk
  FROM time_counts
)
SELECT
  grp, duration,
  EXP(SUM(IF(deaths = 0, 0, IF(deaths = at_risk, -999,
    LN(1 - deaths / at_risk)))) OVER (PARTITION BY grp ORDER BY duration)) AS survival
FROM hazards
ORDER BY grp, duration;

