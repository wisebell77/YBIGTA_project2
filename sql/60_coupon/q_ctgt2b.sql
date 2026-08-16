WITH red AS (SELECT DISTINCT household_key, CAMPAIGN AS campaign FROM `ybigta-505002.sql_study.coupon_redempt`),
t AS (SELECT g.*, r.household_key IS NOT NULL AS redeemed
      FROM `ybigta-505002.dunnhumby_mart.tmp_ctgt` g
      LEFT JOIN red r ON r.campaign=g.campaign AND r.household_key=g.household_key),
cm AS (SELECT campaign, AVG(IF(NOT recip, d_rate, NULL)) AS ctrl FROM t GROUP BY 1)
SELECT
  CASE WHEN NOT recip THEN '무수신' WHEN redeemed THEN '수신+사용' ELSE '수신+미사용' END AS grp,
  COUNT(*) AS n,
  ROUND(AVG(t.d_rate - cm.ctrl)*7,4) AS dd_weekly_vs_ctrl,
  ROUND(AVG(t.d_rate - cm.ctrl)/(STDDEV(t.d_rate - cm.ctrl)/SQRT(COUNT(*)))*1,2) AS t
FROM t JOIN cm USING (campaign)
GROUP BY 1 ORDER BY 1;
