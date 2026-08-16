-- (1) 선택 진단: 사전기간(주차 1~31) 주당 지출, 처치 vs 무처치
SELECT treated, COUNT(DISTINCT household_key) AS hh,
  ROUND(AVG(net),2) AS avg_weekly_spend_pre
FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did`
WHERE week_no <= 31 GROUP BY 1;

-- (2) 타겟팅 현황 + 사용 퍼널: 사전 할인의존도 분위별
WITH red AS (SELECT DISTINCT household_key FROM `ybigta-505002.sql_study.coupon_redempt`)
SELECT d.q_pre, COUNT(DISTINCT d.household_key) AS hh,
  ROUND(100*COUNT(DISTINCT IF(d.treated, d.household_key, NULL))/COUNT(DISTINCT d.household_key),1) AS pct_targeted,
  ROUND(100*COUNT(DISTINCT IF(d.treated AND r.household_key IS NOT NULL, d.household_key, NULL))
        /COUNT(DISTINCT IF(d.treated, d.household_key, NULL)),1) AS pct_redeem_of_targeted
FROM (SELECT DISTINCT household_key, q_pre, treated FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did` WHERE q_pre IS NOT NULL) d
LEFT JOIN red r USING (household_key)
GROUP BY 1 ORDER BY 1;

-- (3) 캠페인 중 효과(k 0~7)의 분위별 이질성
WITH ctrl AS (SELECT week_no, AVG(net) AS yc FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did`
              WHERE NOT treated GROUP BY 1),
adj AS (SELECT d.household_key, d.q_pre, d.week_no - d.onset_week AS k, d.net - c.yc AS ya
        FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did` d JOIN ctrl c USING (week_no)
        WHERE d.treated AND d.q_pre IS NOT NULL),
base AS (SELECT household_key, AVG(ya) AS y0 FROM adj WHERE k BETWEEN -12 AND -3 GROUP BY 1 HAVING COUNT(*)>=8),
post AS (SELECT a.household_key, ANY_VALUE(a.q_pre) AS q_pre, AVG(a.ya) - ANY_VALUE(b.y0) AS d
         FROM adj a JOIN base b USING (household_key) WHERE a.k BETWEEN 0 AND 7 GROUP BY 1)
SELECT q_pre, COUNT(*) AS hh, ROUND(AVG(d),2) AS beta_weekly,
  ROUND(AVG(d)/(STDDEV(d)/SQRT(COUNT(*))),2) AS t
FROM post GROUP BY 1 ORDER BY 1;
