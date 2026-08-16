WITH q AS (
  SELECT household_key, q_dd FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
)
SELECT q.q_dd,
  COUNT(DISTINCT f.household_key) AS hh,
  ROUND(SUM(f.net_sales)/COUNT(DISTINCT f.household_key),0)          AS net_per_hh,
  ROUND(SUM(f.retailer_funded_disc)/COUNT(DISTINCT f.household_key),0) AS disc_per_hh,
  ROUND(SUM(f.gross_sales)/COUNT(DISTINCT f.household_key),0)        AS gross_per_hh,
  ROUND(100*SUM(f.retailer_funded_disc)/SUM(f.gross_sales),2)        AS dd_pct,
  ROUND(100*SUM(f.retailer_funded_disc)/SUM(SUM(f.retailer_funded_disc)) OVER (),1) AS pct_of_all_disc,
  ROUND(100*SUM(f.net_sales)/SUM(SUM(f.net_sales)) OVER (),1)        AS pct_of_all_sales
FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
JOIN q USING (household_key)
WHERE f.day <= 547
GROUP BY q.q_dd ORDER BY q.q_dd
