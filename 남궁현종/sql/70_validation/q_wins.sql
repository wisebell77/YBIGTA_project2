WITH cstore AS (SELECT DISTINCT store_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
     cprod  AS (SELECT DISTINCT product_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
lines AS (
  SELECT f.household_key, f.commodity_desc AS category, f.day, f.quantity, f.net_sales,
    COALESCE(c.mailer_ad,0) AS m, COALESCE(c.mailer_coupon,0)+COALESCE(c.mailer_free,0) AS x,
    COALESCE(c.display_any,0) AS dp
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN `ybigta-505002.dunnhumby_mart.mart_causal_clean` c
    ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101
    AND f.commodity_desc NOT IN ('COUPON','MISC ITEMS','NO COMMODITY DESCRIPTION')),
occ AS (
  SELECT household_key, category, day, MAX(m) AS exposed,
    SUM(LEAST(quantity,10)) AS q10, SUM(LEAST(quantity,20)) AS q20,
    SUM(LEAST(quantity,50)) AS q50, SUM(quantity) AS qraw, SUM(net_sales) AS net
  FROM lines GROUP BY 1,2,3 HAVING MAX(x)=0 AND MAX(dp)=0),
p AS (SELECT household_key,category FROM occ GROUP BY 1,2
      HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT occ.* FROM occ JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(q10) a,AVG(q20) b,AVG(q50) c,AVG(qraw) d,AVG(net) n FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(q10) a,AVG(q20) b,AVG(q50) c,AVG(qraw) d,AVG(net) n FROM s WHERE exposed=0 GROUP BY 1,2)
SELECT COUNT(*) AS n_pairs,
  ROUND(100*(AVG(e.a)-AVG(u.a))/AVG(u.a),2) AS qty_pct_cap10,
  ROUND(100*(AVG(e.b)-AVG(u.b))/AVG(u.b),2) AS qty_pct_cap20,
  ROUND(100*(AVG(e.c)-AVG(u.c))/AVG(u.c),2) AS qty_pct_cap50,
  ROUND(100*(AVG(e.d)-AVG(u.d))/AVG(u.d),2) AS qty_pct_nocap,
  ROUND(100*(AVG(e.n)-AVG(u.n))/AVG(u.n),2) AS net_pct_invariant
FROM e JOIN u USING (household_key,category)
