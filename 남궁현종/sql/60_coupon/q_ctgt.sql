CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.tmp_ctgt` AS
WITH camp AS (
  SELECT CAMPAIGN AS campaign, START_DAY AS sd, END_DAY AS ed
  FROM `ybigta-505002.sql_study.campaign_desc`
  WHERE DESCRIPTION IN ('TypeB','TypeC') AND START_DAY >= 57),
prods AS (SELECT DISTINCT c.CAMPAIGN AS campaign, c.PRODUCT_ID AS product_id
          FROM `ybigta-505002.sql_study.coupon` c JOIN camp ON c.CAMPAIGN = camp.campaign),
hh AS (SELECT DISTINCT household_key FROM `ybigta-505002.dunnhumby_mart.fct_transaction`),
grid AS (SELECT h.household_key, c.campaign, c.sd, c.ed FROM hh h CROSS JOIN camp c),
sp AS (
  SELECT p.campaign, f.household_key,
    SUM(IF(f.day BETWEEN c.sd AND c.ed, f.net_sales, 0)) AS y_dur,
    SUM(IF(f.day BETWEEN c.sd-56 AND c.sd-1, f.net_sales, 0)) AS y_pre
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN prods p USING (product_id)
  JOIN camp c ON c.campaign = p.campaign
  WHERE f.day BETWEEN c.sd-56 AND c.ed
  GROUP BY 1,2),
recip AS (SELECT DISTINCT household_key, CAMPAIGN AS campaign FROM `ybigta-505002.sql_study.campaign_table`)
SELECT g.household_key, g.campaign,
  COALESCE(s.y_dur,0)/(g.ed-g.sd+1) - COALESCE(s.y_pre,0)/56 AS d_rate,
  r.household_key IS NOT NULL AS recip
FROM grid g
LEFT JOIN sp s ON s.campaign=g.campaign AND s.household_key=g.household_key
LEFT JOIN recip r ON r.campaign=g.campaign AND r.household_key=g.household_key;
