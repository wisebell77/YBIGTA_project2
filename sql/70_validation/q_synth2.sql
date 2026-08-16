WITH mail AS (
  SELECT e.s-u.s AS ds, e.v-u.v AS dv, u.s AS us, u.v AS uv
  FROM (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE exposed=1 GROUP BY 1,2) e
  JOIN (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE exposed=0 GROUP BY 1,2) u
  USING (household_key,category)),
deep AS (
  SELECT e.s-u.s AS ds, e.v-u.v AS dv, u.s AS us, u.v AS uv
  FROM (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE disc_rate>=0.30 GROUP BY 1,2) e
  JOIN (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE disc_rate<=0.02 GROUP BY 1,2) u
  USING (household_key,category))
SELECT 'mailer_exposure' AS treatment, COUNT(*) AS n_pairs,
  ROUND(AVG(us),1) AS ctrl_spend, ROUND(AVG(ds),3) AS spend_diff,
  ROUND(AVG(ds)/(STDDEV(ds)/SQRT(COUNT(*))),2) AS t_spend,
  ROUND(AVG(uv),2) AS ctrl_visits, ROUND(AVG(dv),4) AS visit_diff,
  ROUND(AVG(dv)/(STDDEV(dv)/SQRT(COUNT(*))),2) AS t_visit
FROM mail
UNION ALL
SELECT 'realized_deep_discount', COUNT(*),
  ROUND(AVG(us),1), ROUND(AVG(ds),3), ROUND(AVG(ds)/(STDDEV(ds)/SQRT(COUNT(*))),2),
  ROUND(AVG(uv),2), ROUND(AVG(dv),4), ROUND(AVG(dv)/(STDDEV(dv)/SQRT(COUNT(*))),2)
FROM deep
