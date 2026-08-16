CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_household_treatment`
CLUSTER BY household_key
AS
WITH first_exposure AS (
  SELECT
    household_key,
    MIN(start_day)                                       AS first_treat_day,
    ARRAY_AGG(campaign_type ORDER BY start_day LIMIT 1)[OFFSET(0)] AS first_campaign_type,
    COUNT(DISTINCT campaign)                             AS n_campaigns,
    MAX(post_end_day)                                    AS last_treat_day
  FROM `ybigta-505002.dunnhumby_mart.mart_campaign_exposure`
  GROUP BY household_key
)
SELECT
  h.household_key,
  f.household_key IS NOT NULL                            AS is_treated,
  f.first_treat_day,
  CAST(CEIL(f.first_treat_day / 7) AS INT64)             AS first_treat_week,
  f.first_campaign_type,
  IFNULL(f.n_campaigns, 0)                               AS n_campaigns,
  f.last_treat_day
FROM `ybigta-505002.dunnhumby_mart.dim_household` h
LEFT JOIN first_exposure f USING (household_key)