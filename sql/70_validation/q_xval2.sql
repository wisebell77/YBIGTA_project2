WITH cb AS (
  SELECT category,
    SUM(yd*xd)/NULLIF(SUM(POW(xd,2)),0) AS beta,
    AVG(IF(mail=0, net, NULL)) AS ctrl_mean,
    COUNT(DISTINCT product_id) AS n_prods, COUNTIF(mail=1) AS n_treated_rows
  FROM `ybigta-505002.dunnhumby_mart.tmp_xval`
  GROUP BY 1 HAVING COUNT(DISTINCT product_id) >= 3 AND COUNTIF(mail=1) >= 500)
SELECT category, n_prods,
  ROUND(100*beta/NULLIF(ctrl_mean,0),1) AS panel_lift_pct
FROM cb ORDER BY category
