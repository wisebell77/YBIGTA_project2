-- A-1: PURE MAILER effect (display=0 both arms)
WITH s0 AS (SELECT * FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` WHERE has_display=0),
p AS (SELECT household_key,category FROM s0 GROUP BY 1,2
      HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT s0.* FROM s0 JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(gross) AS g FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n,AVG(gross) AS g FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category,e.q-u.q AS dq,e.n-u.n AS dn,u.q AS uq,u.n AS un,e.q AS eq,e.n AS en
      FROM e JOIN u USING (household_key,category))
SELECT 'pure_mailer' AS spec, category, COUNT(*) AS n_pairs,
  ROUND(AVG(uq),3) AS qty_ctrl, ROUND(AVG(eq),3) AS qty_trt, ROUND(100*AVG(dq)/AVG(uq),1) AS qty_pct,
  ROUND(AVG(un),3) AS net_ctrl, ROUND(AVG(en),3) AS net_trt, ROUND(100*AVG(dn)/AVG(un),1) AS net_pct,
  ROUND(AVG(dn),3) AS net_abs,
  ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),2) AS t_net
FROM d GROUP BY category ORDER BY n_pairs DESC;

-- A-2: PURE DISPLAY effect (mailer=0 both arms)
WITH s0 AS (SELECT * FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` WHERE exposed=0),
p AS (SELECT household_key,category FROM s0 GROUP BY 1,2
      HAVING COUNT(*)>=5 AND SUM(has_display)>=2 AND SUM(1-has_display)>=2),
s AS (SELECT s0.* FROM s0 JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE has_display=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE has_display=0 GROUP BY 1,2),
d AS (SELECT e.category,e.q-u.q AS dq,e.n-u.n AS dn,u.q AS uq,u.n AS un,e.q AS eq,e.n AS en
      FROM e JOIN u USING (household_key,category))
SELECT 'pure_display' AS spec, category, COUNT(*) AS n_pairs,
  ROUND(AVG(uq),3) AS qty_ctrl, ROUND(AVG(eq),3) AS qty_trt, ROUND(100*AVG(dq)/AVG(uq),1) AS qty_pct,
  ROUND(AVG(un),3) AS net_ctrl, ROUND(AVG(en),3) AS net_trt, ROUND(100*AVG(dn)/AVG(un),1) AS net_pct,
  ROUND(AVG(dn),3) AS net_abs,
  ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),2) AS t_net
FROM d GROUP BY category ORDER BY n_pairs DESC;
