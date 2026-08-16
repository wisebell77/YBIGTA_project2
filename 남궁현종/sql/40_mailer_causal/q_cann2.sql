WITH s0 AS (SELECT * FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` WHERE has_display=0),
p AS (SELECT household_key,category FROM s0 GROUP BY 1,2
      HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
anchor AS (SELECT s0.* FROM s0 JOIN p USING (household_key,category) WHERE s0.day <= 711-56),
allocc AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` o JOIN p USING (household_key,category)),
post AS (
  SELECT a.household_key,a.category,a.day,a.exposed,
    COALESCE(SUM(IF(b.day>a.day AND b.day<=a.day+56, b.qty, 0)),0) AS q56,
    COALESCE(SUM(IF(b.day>a.day AND b.day<=a.day+56, b.net, 0)),0) AS n56
  FROM anchor a LEFT JOIN allocc b
    ON a.household_key=b.household_key AND a.category=b.category
   AND b.day>a.day AND b.day<=a.day+56
  GROUP BY 1,2,3,4),
e AS (SELECT household_key,category,AVG(q56) AS q,AVG(n56) AS n FROM post WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(q56) AS q,AVG(n56) AS n FROM post WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category,e.q-u.q AS dq,e.n-u.n AS dn,u.q AS uq FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) AS n_pairs,
  ROUND(AVG(uq),3) AS ctrl_q56,
  ROUND(AVG(dq),4) AS diff_q56, ROUND(AVG(dq)/(STDDEV(dq)/SQRT(COUNT(*))),2) AS t_q56,
  ROUND(AVG(dn),4) AS diff_net56, ROUND(AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))),2) AS t_net56
FROM d GROUP BY category ORDER BY n_pairs DESC
