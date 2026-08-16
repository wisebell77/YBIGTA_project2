WITH pairs AS (
  SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat`
  GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2
),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` o JOIN pairs USING (household_key,category)),
e AS (SELECT household_key,category, AVG(qty) AS q, AVG(gross) AS g, AVG(net) AS n FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category, AVG(qty) AS q, AVG(gross) AS g, AVG(net) AS n FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.q-u.q AS dq, e.g-u.g AS dg, e.n-u.n AS dn,
             u.q AS uq, u.g AS ug, u.n AS un, e.q AS eq, e.g AS eg, e.n AS en
      FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) AS n_pairs,
  ROUND(AVG(uq),3) AS qty_ctrl, ROUND(AVG(eq),3) AS qty_trt, ROUND(100*AVG(dq)/AVG(uq),1) AS qty_pct,
  ROUND(AVG(dq)/(STDDEV(dq)/SQRT(COUNT(*))),1) AS t_qty,
  ROUND(AVG(ug),3) AS grs_ctrl, ROUND(AVG(eg),3) AS grs_trt, ROUND(100*AVG(dg)/AVG(ug),1) AS grs_pct,
  ROUND(AVG(un),3) AS net_ctrl, ROUND(AVG(en),3) AS net_trt, ROUND(100*AVG(dn)/AVG(un),1) AS net_pct,
  ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),1) AS t_net
FROM d GROUP BY category ORDER BY n_pairs DESC
