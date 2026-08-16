WITH sw AS (SELECT DISTINCT store_id, week_no FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
cstore AS (SELECT DISTINCT store_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
cprod  AS (SELECT DISTINCT product_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
lines AS (
  SELECT f.net_sales, sw.store_id IS NOT NULL AS covered
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN sw ON sw.store_id=f.store_id AND sw.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101)
SELECT COUNT(*) AS lines_in_scope,
  COUNTIF(NOT covered) AS lines_uncovered,
  ROUND(100*COUNTIF(NOT covered)/COUNT(*),3) AS pct_lines,
  ROUND(100*SUM(IF(NOT covered, net_sales, 0))/SUM(net_sales),3) AS pct_sales
FROM lines
