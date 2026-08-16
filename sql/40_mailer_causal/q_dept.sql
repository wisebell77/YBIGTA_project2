WITH cd AS (
  SELECT commodity_desc AS category, ANY_VALUE(department) AS dept
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1
)
SELECT cd.dept, COUNT(*) AS n_cats, SUM(m.n_pairs) AS pairs,
  ROUND(AVG(m.elasticity),2) AS avg_elast,
  ROUND(AVG(m.disc_trt_pct),1) AS avg_disc,
  ROUND(AVG(m.qty_pct),1) AS avg_qty_lift,
  ROUND(AVG(m.net_pct),1) AS avg_net_pct,
  ROUND(AVG(m.net_now),3) AS avg_net_now,
  COUNTIF(m.net_now > 0) AS n_positive,
  COUNTIF(m.net_now <= 0) AS n_negative
FROM `ybigta-505002.dunnhumby_mart.mart_cat_matrix` m
JOIN cd USING (category)
GROUP BY dept HAVING COUNT(*) >= 3
ORDER BY avg_net_pct DESC
