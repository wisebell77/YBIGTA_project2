-- 앵커 당일 가구의 매장 전체 지출: 딥할인 구매기회 vs 정가 구매기회
WITH hhday AS (
  SELECT household_key, day, SUM(net_sales) AS day_spend
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1,2),
a AS (SELECT f.*, h.day_spend
      FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` f
      JOIN hhday h USING (household_key, day)),
deep AS (SELECT household_key,category,AVG(day_spend) AS s FROM a WHERE disc_rate>=0.30 GROUP BY 1,2),
reg AS (SELECT household_key,category,AVG(day_spend) AS s FROM a WHERE disc_rate<=0.02 GROUP BY 1,2),
ex   AS (SELECT household_key,category,AVG(day_spend) AS s FROM a WHERE exposed=1 GROUP BY 1,2),
un   AS (SELECT household_key,category,AVG(day_spend) AS s FROM a WHERE exposed=0 GROUP BY 1,2)
SELECT 'realized_deep_vs_full' AS comparison, COUNT(*) AS n_pairs,
  ROUND(AVG(reg.s),2) AS ctrl_dayspend, ROUND(AVG(deep.s),2) AS trt_dayspend,
  ROUND(AVG(deep.s-reg.s),3) AS diff,
  ROUND(100*AVG(deep.s-reg.s)/AVG(reg.s),1) AS pct,
  ROUND(AVG(deep.s-reg.s)/(STDDEV(deep.s-reg.s)/SQRT(COUNT(*))),1) AS t
FROM deep JOIN reg USING (household_key,category)
UNION ALL
SELECT 'mailer_exposed_vs_not', COUNT(*),
  ROUND(AVG(un.s),2), ROUND(AVG(ex.s),2), ROUND(AVG(ex.s-un.s),3),
  ROUND(100*AVG(ex.s-un.s)/AVG(un.s),1),
  ROUND(AVG(ex.s-un.s)/(STDDEV(ex.s-un.s)/SQRT(COUNT(*))),1)
FROM ex JOIN un USING (household_key,category)
