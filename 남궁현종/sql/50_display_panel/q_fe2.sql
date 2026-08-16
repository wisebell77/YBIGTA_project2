CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.tmp_dm` AS
WITH cells AS (SELECT product_id, week_no, COUNT(*) AS n, SUM(disp) AS nt
               FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` GROUP BY 1,2),
vc AS (SELECT product_id, week_no FROM cells WHERE nt>0 AND nt<n),
p AS (SELECT pn.* FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` pn JOIN vc USING (product_id,week_no))
SELECT product_id, store_id, week_no, net, disp, gross, disc,
  net  - AVG(net)  OVER (PARTITION BY product_id, week_no) AS net_dm,
  disp - AVG(disp) OVER (PARTITION BY product_id, week_no) AS disp_dm
FROM p;

WITH b AS (SELECT SUM(net_dm*disp_dm)/SUM(POW(disp_dm,2)) AS beta,
                  SUM(POW(disp_dm,2)) AS sxx, COUNT(*) AS n
           FROM `ybigta-505002.dunnhumby_mart.tmp_dm`),
r AS (SELECT d.product_id, d.disp_dm*(d.net_dm - b.beta*d.disp_dm) AS xe
      FROM `ybigta-505002.dunnhumby_mart.tmp_dm` d CROSS JOIN b),
cl AS (SELECT product_id, SUM(xe) AS g FROM r GROUP BY 1),
v AS (SELECT SUM(POW(g,2)) AS meat, COUNT(*) AS nclust FROM cl)
SELECT
  (SELECT n FROM b) AS panel_rows,
  (SELECT nclust FROM v) AS n_clusters,
  ROUND((SELECT beta FROM b),4) AS beta_fe,
  ROUND(SQRT((SELECT meat FROM v))/(SELECT sxx FROM b),4) AS se_cluster,
  ROUND((SELECT beta FROM b)/(SQRT((SELECT meat FROM v))/(SELECT sxx FROM b)),1) AS t_cluster,
  ROUND((SELECT AVG(IF(disp=0,net,NULL)) FROM `ybigta-505002.dunnhumby_mart.tmp_dm`),4) AS ctrl_base,
  ROUND(1+(SELECT beta FROM b)/(SELECT AVG(IF(disp=0,net,NULL)) FROM `ybigta-505002.dunnhumby_mart.tmp_dm`),3) AS fe_lift,
  ROUND((SELECT AVG(IF(disp=1,net,NULL))/AVG(IF(disp=0,net,NULL)) FROM `ybigta-505002.dunnhumby_mart.tmp_dm`),3) AS naive_lift,
  ROUND((SELECT AVG(IF(disp=1,net,NULL))/AVG(IF(disp=0,net,NULL)) FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel`),3) AS naive_lift_full;
