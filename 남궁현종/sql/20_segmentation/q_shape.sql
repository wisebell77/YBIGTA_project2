WITH b AS (
  SELECT household_key, dd_obs, sales_obs, visits_obs,
         NTILE(10) OVER (ORDER BY dd_obs) AS d10
  FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
  WHERE visits_obs >= 10
)
SELECT d10, COUNT(*) AS n,
  ROUND(100*AVG(dd_obs),2) AS dd_avg,
  ROUND(AVG(sales_obs),0)  AS spend,
  ROUND(1.96*STDDEV(sales_obs)/SQRT(COUNT(*)),0) AS ci95,
  ROUND(AVG(visits_obs),1) AS visits,
  ROUND(AVG(sales_obs)/AVG(visits_obs),2) AS basket
FROM b GROUP BY d10 ORDER BY d10;

WITH b AS (
  SELECT dd_obs, sales_obs,
    LEAST(FLOOR(dd_obs*100/2)*2, 30) AS bin2
  FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`
  WHERE visits_obs >= 10
)
SELECT CAST(bin2 AS INT64) AS dd_bin_lo, COUNT(*) AS n,
  ROUND(AVG(sales_obs),0) AS spend,
  ROUND(1.96*STDDEV(sales_obs)/SQRT(COUNT(*)),0) AS ci95
FROM b GROUP BY bin2 HAVING COUNT(*) >= 25 ORDER BY bin2;
