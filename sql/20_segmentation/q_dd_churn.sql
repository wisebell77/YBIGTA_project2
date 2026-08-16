CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn` AS
WITH obs AS (
  SELECT household_key,
    SAFE_DIVIDE(SUM(retailer_funded_disc), SUM(gross_sales)) AS dd_obs,
    SUM(net_sales)            AS sales_obs,
    COUNT(DISTINCT basket_id) AS visits_obs,
    MAX(day)                  AS last_day_obs
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day <= 547
  GROUP BY household_key
),
hold AS (
  SELECT household_key,
    COUNT(DISTINCT basket_id) AS visits_hold,
    SUM(net_sales)            AS sales_hold
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day > 547
  GROUP BY household_key
)
SELECT o.household_key, o.dd_obs, o.sales_obs, o.visits_obs,
       547 - o.last_day_obs AS recency_obs,
       COALESCE(h.visits_hold,0) AS visits_hold,
       COALESCE(h.sales_hold,0)  AS sales_hold,
       h.household_key IS NOT NULL AS repurchased,
       NTILE(5) OVER (ORDER BY o.dd_obs) AS q_dd
FROM obs o LEFT JOIN hold h USING (household_key);

SELECT q_dd,
  COUNT(*) AS households,
  ROUND(100*MIN(dd_obs),2) AS dd_min,
  ROUND(100*MAX(dd_obs),2) AS dd_max,
  ROUND(100*AVG(dd_obs),2) AS dd_avg,
  ROUND(AVG(sales_obs),0)  AS spend_obs,
  ROUND(AVG(visits_obs),1) AS visits_obs,
  ROUND(AVG(recency_obs),1) AS recency_at_547,
  ROUND(100*AVG(CAST(repurchased AS INT64)),1) AS pct_repurchased,
  ROUND(AVG(visits_hold),1) AS visits_hold,
  ROUND(AVG(sales_hold),0)  AS spend_hold,
  ROUND(100*SAFE_DIVIDE(AVG(sales_hold), AVG(sales_obs))*547/164, 1) AS retention_idx
FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
GROUP BY q_dd ORDER BY q_dd;
