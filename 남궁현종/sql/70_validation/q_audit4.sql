WITH p AS (SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
           GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,SAFE_DIVIDE(SUM(gross),SUM(qty)) AS up FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,SAFE_DIVIDE(SUM(gross),SUM(qty)) AS up FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, AVG(u.up) AS up_ctrl, AVG(e.up) AS up_trt, COUNT(*) AS n
      FROM e JOIN u USING (household_key,category) GROUP BY 1 HAVING COUNT(*)>=100)
SELECT m.category, d.n,
  ROUND(d.up_ctrl,3) AS unit_price_ctrl, ROUND(d.up_trt,3) AS unit_price_trt,
  ROUND(100*(d.up_trt-d.up_ctrl)/d.up_ctrl,1) AS mix_shift_pct,
  m.elasticity, m.qty_pct, m.net_pct, m.net_now, m.t_net, m.net_total
FROM d JOIN `ybigta-505002.dunnhumby_mart.mart_cat_matrix` m USING (category)
ORDER BY mix_shift_pct DESC
