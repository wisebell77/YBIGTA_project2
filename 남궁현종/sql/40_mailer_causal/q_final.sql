CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_cat_matrix` AS
SELECT e.category, e.n_pairs,
  ROUND(100*e.disc_ctrl,1) AS disc_ctrl_pct,
  ROUND(100*e.disc_trt,1)  AS disc_trt_pct,
  ROUND(100*e.qty_pct,1)   AS qty_pct,
  ROUND(100*e.net_pct,1)   AS net_pct,
  ROUND(e.net_abs,3)       AS net_now,
  ROUND(e.t_net,2)         AS t_net,
  ROUND(c.cann_net56,3)    AS net_later,
  ROUND(e.net_abs + c.cann_net56, 3) AS net_total,
  ROUND(SAFE_DIVIDE(e.qty_pct, ABS((1-e.disc_trt)/(1-e.disc_ctrl) - 1)), 2) AS elasticity,
  ROUND(100*(1 + SAFE_DIVIDE(c.cann_q56, e.qty_lift)), 0) AS incrementality_pct,
  ROUND(c.t_cann,2) AS t_cann
FROM `ybigta-505002.dunnhumby_mart.mart_cat_effect` e
JOIN `ybigta-505002.dunnhumby_mart.mart_cat_cann` c USING (category);

SELECT
  COUNTIF(net_total > 0 AND t_net > 2)  AS expand,
  COUNTIF(net_total > 0 AND t_net <= 2) AS hold,
  COUNTIF(net_total <= 0)               AS cut,
  COUNTIF(elasticity > 1)               AS elastic,
  COUNTIF(elasticity <= 1)              AS inelastic,
  ROUND(AVG(elasticity),2)              AS avg_elasticity,
  ROUND(AVG(incrementality_pct),0)      AS avg_increm
FROM `ybigta-505002.dunnhumby_mart.mart_cat_matrix`;
