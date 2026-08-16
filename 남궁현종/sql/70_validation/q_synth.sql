CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_fwd28` AS
WITH hhday AS (
  SELECT household_key, day, SUM(net_sales) AS net, COUNT(DISTINCT basket_id) AS visits
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1,2),
p AS (SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
a AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN p USING (household_key,category)
      WHERE o.day <= 683)
SELECT a.household_key, a.category, a.day, a.exposed, a.disc_rate,
  COALESCE(SUM(h.net),0)    AS fwd28_spend,
  COALESCE(SUM(h.visits),0) AS fwd28_visits
FROM a LEFT JOIN hhday h
  ON h.household_key=a.household_key AND h.day > a.day AND h.day <= a.day+28
GROUP BY 1,2,3,4,5;

-- (1) 처치 = 전단지 노출 (사전 집행, 외생성 높음)
WITH e AS (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
           FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
      FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.s-u.s AS ds, e.v-u.v AS dv, u.s AS us, u.v AS uv FROM e JOIN u USING (household_key,category))
SELECT 'mailer_exposure' AS treatment, COUNT(*) AS n_pairs,
  ROUND(AVG(us),1) AS ctrl_spend, ROUND(AVG(ds),3) AS spend_diff,
  ROUND(AVG(ds)/(STDDEV(ds)/SQRT(COUNT(*))),2) AS t_spend,
  ROUND(AVG(uv),2) AS ctrl_visits, ROUND(AVG(dv),4) AS visit_diff,
  ROUND(AVG(dv)/(STDDEV(dv)/SQRT(COUNT(*))),2) AS t_visit
FROM d
UNION ALL
-- (2) 처치 = 실현 딥할인 (팀원 방식, 내생적)
SELECT 'realized_deep_discount', COUNT(*),
  ROUND(AVG(us),1), ROUND(AVG(ds),3), ROUND(AVG(ds)/(STDDEV(ds)/SQRT(COUNT(*))),2),
  ROUND(AVG(uv),2), ROUND(AVG(dv),4), ROUND(AVG(dv)/(STDDEV(dv)/SQRT(COUNT(*))),2)
FROM (
  SELECT e.s-u.s AS ds, e.v-u.v AS dv, u.s AS us, u.v AS uv
  FROM (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE disc_rate>=0.30 GROUP BY 1,2) e
  JOIN (SELECT household_key,category,AVG(fwd28_spend) AS s,AVG(fwd28_visits) AS v
        FROM `ybigta-505002.dunnhumby_mart.mart_fwd28` WHERE disc_rate<=0.02 GROUP BY 1,2) u
  USING (household_key,category));
