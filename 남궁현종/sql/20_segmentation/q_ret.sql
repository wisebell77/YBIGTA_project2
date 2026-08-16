WITH b AS (
  SELECT *,
    SAFE_DIVIDE(visits_hold/164.0, visits_obs/547.0) AS visit_retention,
    SAFE_DIVIDE(sales_hold/164.0,  sales_obs/547.0)  AS spend_retention
  FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
  WHERE visits_obs >= 10
)
SELECT q_dd,
  COUNT(*) AS n,
  ROUND(100*AVG(dd_obs),2)          AS dd_avg,
  ROUND(AVG(visit_retention),3)     AS visit_ret,
  ROUND(STDDEV(visit_retention)/SQRT(COUNT(*)),3) AS visit_ret_se,
  ROUND(AVG(spend_retention),3)     AS spend_ret,
  ROUND(STDDEV(spend_retention)/SQRT(COUNT(*)),3) AS spend_ret_se,
  ROUND(100*AVG(CAST(visit_retention < 0.5 AS INT64)),1) AS pct_decline50,
  ROUND(100*AVG(CAST(visits_hold = 0 AS INT64)),1)       AS pct_zero_holdout
FROM b GROUP BY q_dd ORDER BY q_dd;

WITH b AS (
  SELECT *, SAFE_DIVIDE(visits_hold/164.0, visits_obs/547.0) AS vr
  FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn` WHERE visits_obs >= 10
)
SELECT
  ROUND(CORR(dd_obs, vr),4)          AS corr_dd_visitret,
  ROUND(CORR(dd_obs, sales_obs),4)   AS corr_dd_spend,
  ROUND(CORR(dd_obs, visits_obs),4)  AS corr_dd_visits,
  COUNT(*) AS n
FROM b;
