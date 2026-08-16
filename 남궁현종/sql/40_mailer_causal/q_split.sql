-- 할인의존도는 1~350일로 산출, 효과는 351일 이후 구매기회로만 추정 (완전 분리)
WITH dd AS (
  SELECT household_key,
    SAFE_DIVIDE(SUM(retailer_funded_disc), SUM(gross_sales)) AS dd_early
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day <= 350 GROUP BY 1 HAVING COUNT(DISTINCT basket_id) >= 10),
q AS (SELECT household_key, NTILE(5) OVER (ORDER BY dd_early) AS q_early FROM dd),
o AS (SELECT o.*, q.q_early FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o
      JOIN q USING (household_key) WHERE o.day > 350),
p AS (SELECT household_key, category, ANY_VALUE(q_early) AS q_early FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(disc_rate) AS dr FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT p.q_early, e.q-u.q AS dq, e.n-u.n AS dn, u.q AS uq, u.n AS un, u.dr AS udr, e.dr AS edr
      FROM e JOIN u USING (household_key,category) JOIN p USING (household_key,category))
SELECT q_early, COUNT(*) AS n_pairs,
  ROUND(100*AVG(udr),1) AS disc_ctrl, ROUND(100*AVG(edr),1) AS disc_trt,
  ROUND(100*AVG(dq)/AVG(uq),1) AS qty_pct,
  ROUND(AVG(un),3) AS net_ctrl, ROUND(AVG(dn),3) AS net_abs,
  ROUND(100*AVG(dn)/AVG(un),1) AS net_pct,
  ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),2) AS t_net,
  ROUND(SAFE_DIVIDE(AVG(dq)/AVG(uq), ABS((1-AVG(edr))/(1-AVG(udr))-1)),2) AS elasticity
FROM d GROUP BY q_early ORDER BY q_early
