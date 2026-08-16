WITH b AS (
  SELECT *,
    SAFE_DIVIDE(visits_hold/164.0, visits_obs/547.0) AS vr,
    SAFE_DIVIDE(sales_hold/164.0,  sales_obs/547.0)  AS sr
  FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
  WHERE visits_obs >= 10
)
SELECT q_dd, COUNT(*) AS n,
  ROUND(100*AVG(dd_obs),2) AS dd_avg,
  ROUND(AVG(vr),3) AS visit_ret,
  ROUND(1.96*STDDEV(vr)/SQRT(COUNT(*)),3) AS vr_ci95,
  ROUND(AVG(sr),3) AS spend_ret,
  ROUND(100*AVG(CAST(vr<0.5 AS INT64)),1) AS pct_decline50,
  ROUND(AVG(sales_obs),0) AS spend_obs,
  ROUND(AVG(recency_obs),1) AS recency
FROM b GROUP BY q_dd ORDER BY q_dd
