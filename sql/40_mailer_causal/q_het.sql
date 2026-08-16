WITH q AS (SELECT household_key, q_dd FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`),
o AS (SELECT o.*, q.q_dd FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN q USING (household_key)),
p AS (SELECT household_key, category, ANY_VALUE(q_dd) AS q_dd FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT p.q_dd, e.q-u.q AS dq, e.n-u.n AS dn, u.q AS uq, u.n AS un, u.dr AS udr, e.dr AS edr
      FROM e JOIN u USING (household_key,category) JOIN p USING (household_key,category))
SELECT q_dd, COUNT(*) AS n_pairs,
  ROUND(100*AVG(udr),1) AS disc_ctrl, ROUND(100*AVG(edr),1) AS disc_trt,
  ROUND(AVG(uq),3) AS qty_ctrl, ROUND(100*AVG(dq)/AVG(uq),1) AS qty_pct,
  ROUND(AVG(dq)/(STDDEV(dq)/SQRT(COUNT(*))),1) AS t_qty,
  ROUND(AVG(un),3) AS net_ctrl, ROUND(AVG(dn),3) AS net_abs,
  ROUND(100*AVG(dn)/AVG(un),1) AS net_pct,
  ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),1) AS t_net,
  ROUND(SAFE_DIVIDE(AVG(dq)/AVG(uq), ABS((1-AVG(edr))/(1-AVG(udr))-1)),2) AS elasticity
FROM d GROUP BY q_dd ORDER BY q_dd;

-- 노출 도달률: 분위별로 전단지에 노출되는 비율이 다른가
WITH q AS (SELECT household_key, q_dd FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`)
SELECT q.q_dd, COUNT(*) AS occasions,
  ROUND(100*AVG(o.exposed),2) AS pct_exposed
FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN q USING (household_key)
GROUP BY 1 ORDER BY 1;
