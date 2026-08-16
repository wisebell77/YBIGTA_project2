CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_causal_clean` AS
SELECT PRODUCT_ID AS product_id, STORE_ID AS store_id, WEEK_NO AS week_no,
  MAX(IF(mailer IN ('A','C','D','F','H','L'), 1, 0)) AS mailer_ad,
  MAX(IF(mailer IN ('J','P'),               1, 0)) AS mailer_coupon,
  MAX(IF(mailer IN ('X','Z'),               1, 0)) AS mailer_free,
  MAX(IF(mailer = 'D',                      1, 0)) AS mailer_frontpage,
  MAX(IF(display <> '0',                    1, 0)) AS display_any,
  MAX(IF(display NOT IN ('0','A'),          1, 0)) AS display_strict
FROM `ybigta-505002.sql_study.causal_data`
GROUP BY 1,2,3;

SELECT
  COUNT(*) AS psw_cells,
  SUM(mailer_ad) AS ad, SUM(mailer_coupon) AS coupon, SUM(mailer_free) AS free_gift,
  SUM(mailer_frontpage) AS frontpage, SUM(display_any) AS disp_any, SUM(display_strict) AS disp_strict,
  COUNTIF(mailer_ad=0 AND mailer_coupon=0 AND mailer_free=0 AND display_any=0) AS nothing
FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`;
