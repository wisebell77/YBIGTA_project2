CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_cat_effect` AS
WITH p AS (SELECT household_key,category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
           GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.q-u.q AS dq, e.n-u.n AS dn,
             u.q AS uq,u.n AS un,u.dr AS udr, e.q AS eq,e.n AS en,e.dr AS edr
      FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) AS n_pairs,
  AVG(udr) AS disc_ctrl, AVG(edr) AS disc_trt,
  AVG(uq) AS qty_ctrl, AVG(dq) AS qty_lift,
  SAFE_DIVIDE(AVG(dq),AVG(uq)) AS qty_pct,
  SAFE_DIVIDE(AVG(dq),STDDEV(dq)/SQRT(COUNT(*))) AS t_qty,
  AVG(un) AS net_ctrl, AVG(dn) AS net_abs,
  SAFE_DIVIDE(AVG(dn),AVG(un)) AS net_pct,
  SAFE_DIVIDE(AVG(dn),STDDEV(dn)/SQRT(COUNT(*))) AS t_net
FROM d GROUP BY category HAVING COUNT(*)>=100;

SELECT COUNT(*) AS categories, SUM(n_pairs) AS total_pairs FROM `ybigta-505002.dunnhumby_mart.mart_cat_effect`;
