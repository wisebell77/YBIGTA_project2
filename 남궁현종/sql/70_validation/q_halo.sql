-- 공백 2: 프로모션 노출 구매기회의 "당일 나머지 매장 지출" (focal 카테고리 제외)
WITH hhday AS (
  SELECT household_key, day, SUM(net_sales) AS total
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1,2),
p AS (SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.household_key, o.category, o.day, o.exposed,
        h.total - o.net AS rest_spend, o.net AS focal_spend
      FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o
      JOIN p USING (household_key, category)
      JOIN hhday h USING (household_key, day)),
e AS (SELECT household_key,category,AVG(rest_spend) AS r,AVG(focal_spend) AS f FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(rest_spend) AS r,AVG(focal_spend) AS f FROM s WHERE exposed=0 GROUP BY 1,2)
SELECT COUNT(*) AS n_pairs,
  ROUND(AVG(u.r),2) AS rest_ctrl, ROUND(AVG(e.r),2) AS rest_trt,
  ROUND(AVG(e.r-u.r),3) AS rest_diff,
  ROUND(100*AVG(e.r-u.r)/AVG(u.r),2) AS rest_pct,
  ROUND(AVG(e.r-u.r)/(STDDEV(e.r-u.r)/SQRT(COUNT(*))),2) AS t_rest,
  ROUND(AVG(e.f-u.f),3) AS focal_diff,
  ROUND(100*AVG(e.f-u.f)/AVG(u.f),2) AS focal_pct
FROM e JOIN u USING (household_key,category)
