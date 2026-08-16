-- 상품-주차 셀 안에 처치/대조 점포가 공존하는가?
SELECT 'display' AS treatment,
  COUNT(*) AS cells,
  COUNTIF(n_treated > 0 AND n_treated < n_stores) AS cells_with_variation,
  ROUND(100*COUNTIF(n_treated > 0 AND n_treated < n_stores)/COUNT(*),2) AS pct_var,
  ROUND(AVG(SAFE_DIVIDE(n_treated,n_stores)),3) AS avg_treat_share
FROM (SELECT product_id, week_no, COUNT(*) AS n_stores, SUM(display_any) AS n_treated
      FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean` GROUP BY 1,2)
UNION ALL
SELECT 'mailer_ad',
  COUNT(*), COUNTIF(n_treated > 0 AND n_treated < n_stores),
  ROUND(100*COUNTIF(n_treated > 0 AND n_treated < n_stores)/COUNT(*),2),
  ROUND(AVG(SAFE_DIVIDE(n_treated,n_stores)),3)
FROM (SELECT product_id, week_no, COUNT(*) AS n_stores, SUM(mailer_ad) AS n_treated
      FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean` GROUP BY 1,2)
UNION ALL
SELECT 'display_strict',
  COUNT(*), COUNTIF(n_treated > 0 AND n_treated < n_stores),
  ROUND(100*COUNTIF(n_treated > 0 AND n_treated < n_stores)/COUNT(*),2),
  ROUND(AVG(SAFE_DIVIDE(n_treated,n_stores)),3)
FROM (SELECT product_id, week_no, COUNT(*) AS n_stores, SUM(display_strict) AS n_treated
      FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean` GROUP BY 1,2)
