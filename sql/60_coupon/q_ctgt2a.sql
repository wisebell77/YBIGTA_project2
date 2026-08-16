-- 캠페인 FE + 가구 클러스터 SE (일일 지출율 기준, $/일)
WITH dm AS (
  SELECT household_key, campaign,
    d_rate - AVG(d_rate) OVER (PARTITION BY campaign) AS y,
    CAST(recip AS INT64) - AVG(CAST(recip AS INT64)) OVER (PARTITION BY campaign) AS x
  FROM `ybigta-505002.dunnhumby_mart.tmp_ctgt`),
b AS (SELECT SUM(y*x)/SUM(POW(x,2)) AS beta, SUM(POW(x,2)) AS sxx FROM dm),
r AS (SELECT d.household_key, d.x*(d.y - b.beta*d.x) AS xe FROM dm d CROSS JOIN b),
cl AS (SELECT household_key, SUM(xe) AS g FROM r GROUP BY 1),
v AS (SELECT SUM(POW(g,2)) AS meat FROM cl)
SELECT
  ROUND((SELECT beta FROM b),5) AS beta_daily,
  ROUND((SELECT beta FROM b)*7,4) AS beta_weekly,
  ROUND((SELECT beta FROM b)/(SQRT((SELECT meat FROM v))/(SELECT sxx FROM b)),2) AS t_cluster,
  (SELECT COUNT(*) FROM dm) AS n_obs,
  (SELECT ROUND(AVG(IF(recip, NULL, d_rate)),5) FROM `ybigta-505002.dunnhumby_mart.tmp_ctgt`) AS ctrl_mean_change;

