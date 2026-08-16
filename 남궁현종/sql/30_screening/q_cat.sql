WITH q AS (SELECT household_key, q_dd FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`),
agg AS (
  SELECT f.commodity_desc AS category,
    SUM(f.net_sales)  AS net,
    SUM(f.gross_sales) AS gross,
    SUM(f.retailer_funded_disc) AS disc,
    SUM(IF(q.q_dd=1, f.retailer_funded_disc, 0))/500 AS disc_q1_hh,
    SUM(IF(q.q_dd=5, f.retailer_funded_disc, 0))/499 AS disc_q5_hh,
    SUM(IF(q.q_dd=1, f.net_sales, 0))/500 AS net_q1_hh,
    SUM(IF(q.q_dd=5, f.net_sales, 0))/499 AS net_q5_hh
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN q USING (household_key)
  WHERE f.day <= 547
  GROUP BY 1
)
SELECT category,
  ROUND(100*disc/gross,1)                     AS disc_rate,
  ROUND(100*disc/SUM(disc) OVER (),2)         AS pct_disc,
  ROUND(100*net/SUM(net) OVER (),2)           AS pct_sales,
  ROUND(SAFE_DIVIDE(net/SUM(net) OVER (), disc/SUM(disc) OVER ()),2) AS efficiency,
  ROUND(disc_q1_hh,1) AS disc_q1,
  ROUND(disc_q5_hh,1) AS disc_q5,
  ROUND(disc_q5_hh-disc_q1_hh,1) AS disc_gap,
  ROUND(net_q5_hh-net_q1_hh,1)   AS net_gap
FROM agg
WHERE disc > 3000
ORDER BY disc_gap DESC
LIMIT 20
