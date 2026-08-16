CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_cat_cann` AS
WITH keep AS (SELECT category FROM `ybigta-505002.dunnhumby_mart.mart_cat_effect`),
p AS (SELECT household_key,category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
      WHERE category IN (SELECT category FROM keep)
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN p USING (household_key,category)),
post AS (
  SELECT a.household_key,a.category,a.day,a.exposed,
    COALESCE(SUM(IF(b.day>a.day AND b.day<=a.day+56, b.qty, 0)),0) AS q56,
    COALESCE(SUM(IF(b.day>a.day AND b.day<=a.day+56, b.net, 0)),0) AS n56
  FROM s a LEFT JOIN s b
    ON a.household_key=b.household_key AND a.category=b.category
   AND b.day>a.day AND b.day<=a.day+56
  WHERE a.day <= 655
  GROUP BY 1,2,3,4),
e AS (SELECT household_key,category,AVG(q56) AS q,AVG(n56) AS n FROM post WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(q56) AS q,AVG(n56) AS n FROM post WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category,e.q-u.q AS dq,e.n-u.n AS dn FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) AS n_pairs_c,
  AVG(dq) AS cann_q56, SAFE_DIVIDE(AVG(dq),STDDEV(dq)/SQRT(COUNT(*))) AS t_cann,
  AVG(dn) AS cann_net56, SAFE_DIVIDE(AVG(dn),STDDEV(dn)/SQRT(COUNT(*))) AS t_cann_net
FROM d GROUP BY category;

SELECT COUNT(*) AS cats FROM `ybigta-505002.dunnhumby_mart.mart_cat_cann`;
