-- 이벤트 스터디: 대조군 주차 평균 차감 → 가구별 기저(-12~-3) 차감 → k별 평균
WITH ctrl AS (SELECT week_no, AVG(net) AS yc FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did`
              WHERE NOT treated GROUP BY 1),
adj AS (SELECT d.household_key, d.week_no, d.net - c.yc AS ya, d.onset_week
        FROM `ybigta-505002.dunnhumby_mart.mart_coupon_did` d JOIN ctrl c USING (week_no)
        WHERE d.treated),
tr AS (SELECT *, week_no - onset_week AS k FROM adj),
base AS (SELECT household_key, AVG(ya) AS y0, COUNT(*) AS nb
         FROM tr WHERE k BETWEEN -12 AND -3 GROUP BY 1 HAVING COUNT(*) >= 8),
ev AS (SELECT t.k, t.ya - b.y0 AS d FROM tr t JOIN base b USING (household_key)
       WHERE t.k BETWEEN -8 AND 16)
SELECT k, COUNT(*) AS n_hh,
  ROUND(AVG(d),3) AS beta,
  ROUND(AVG(d)/(STDDEV(d)/SQRT(COUNT(*))),2) AS t
FROM ev GROUP BY k ORDER BY k
