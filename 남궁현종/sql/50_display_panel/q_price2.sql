WITH s AS (SELECT * FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` WHERE gross > 0),
dm AS (SELECT disp, SAFE_DIVIDE(disc,gross) AS dr,
         SAFE_DIVIDE(disc,gross) - AVG(SAFE_DIVIDE(disc,gross)) OVER (PARTITION BY product_id, week_no) AS dr_dm,
         disp - AVG(disp) OVER (PARTITION BY product_id, week_no) AS disp_dm
       FROM s)
SELECT
  ROUND(100*AVG(IF(disp=1,dr,NULL)),2) AS pooled_treated_pct,
  ROUND(100*AVG(IF(disp=0,dr,NULL)),2) AS pooled_control_pct,
  ROUND(100*(AVG(IF(disp=1,dr,NULL))-AVG(IF(disp=0,dr,NULL))),2) AS pooled_gap_pp,
  ROUND(100*SUM(dr_dm*disp_dm)/NULLIF(SUM(POW(disp_dm,2)),0),2) AS within_cell_gap_pp
FROM dm
