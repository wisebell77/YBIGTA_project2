WITH pairs AS (
  SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat`
  GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2
),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat` o JOIN pairs USING (household_key,category)),
post AS (
  SELECT a.household_key, a.category, a.day, a.exposed,
    COALESCE(SUM(IF(b.day> a.day AND b.day<=a.day+28, b.qty, 0)),0) AS q28,
    COALESCE(SUM(IF(b.day> a.day AND b.day<=a.day+56, b.qty, 0)),0) AS q56,
    COALESCE(SUM(IF(b.day> a.day AND b.day<=a.day+56, b.net, 0)),0) AS n56
  FROM s a LEFT JOIN s b
    ON a.household_key=b.household_key AND a.category=b.category
   AND b.day>a.day AND b.day<=a.day+56
  WHERE a.day <= 711-56
  GROUP BY 1,2,3,4
),
e AS (SELECT household_key,category, AVG(q28) AS a28, AVG(q56) AS a56, AVG(n56) AS s56 FROM post WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category, AVG(q28) AS a28, AVG(q56) AS a56, AVG(n56) AS s56 FROM post WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.a28-u.a28 AS d28, e.a56-u.a56 AS d56, e.s56-u.s56 AS dn56,
             u.a28 AS u28, u.a56 AS u56 FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) AS n_pairs,
  ROUND(AVG(u28),3) AS ctrl_q28, ROUND(AVG(d28),4) AS diff_q28,
  ROUND(AVG(d28)/(STDDEV(d28)/SQRT(COUNT(*))),2) AS t28,
  ROUND(AVG(u56),3) AS ctrl_q56, ROUND(AVG(d56),4) AS diff_q56,
  ROUND(AVG(d56)/(STDDEV(d56)/SQRT(COUNT(*))),2) AS t56,
  ROUND(AVG(dn56),3) AS diff_net56,
  ROUND(AVG(dn56)/(STDDEV(dn56)/SQRT(COUNT(*))),2) AS t_net56
FROM d GROUP BY category ORDER BY n_pairs DESC
