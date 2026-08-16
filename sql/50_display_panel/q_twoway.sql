CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.tmp_dd` AS
WITH cells AS (SELECT product_id, week_no, COUNT(*) AS n, SUM(disp) AS nt
               FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` GROUP BY 1,2),
vc AS (SELECT product_id, week_no FROM cells WHERE nt>0 AND nt<n),
p AS (SELECT pn.* FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel` pn JOIN vc USING (product_id,week_no)),
i1 AS (SELECT product_id, store_id, week_no, net, disp,
        net  - AVG(net)  OVER (PARTITION BY product_id, week_no) AS y,
        disp - AVG(disp) OVER (PARTITION BY product_id, week_no) AS x FROM p),
i2 AS (SELECT *, y - AVG(y) OVER (PARTITION BY product_id, store_id) AS y2,
                 x - AVG(x) OVER (PARTITION BY product_id, store_id) AS x2 FROM i1),
i3 AS (SELECT *, y2 - AVG(y2) OVER (PARTITION BY product_id, week_no) AS y3,
                 x2 - AVG(x2) OVER (PARTITION BY product_id, week_no) AS x3 FROM i2),
i4 AS (SELECT *, y3 - AVG(y3) OVER (PARTITION BY product_id, store_id) AS y4,
                 x3 - AVG(x3) OVER (PARTITION BY product_id, store_id) AS x4 FROM i3),
i5 AS (SELECT *, y4 - AVG(y4) OVER (PARTITION BY product_id, week_no) AS y5,
                 x4 - AVG(x4) OVER (PARTITION BY product_id, week_no) AS x5 FROM i4)
SELECT product_id, store_id, week_no, net, disp, y5 AS y_dd, x5 AS x_dd FROM i5;

WITH b AS (SELECT SUM(y_dd*x_dd)/SUM(POW(x_dd,2)) AS beta, SUM(POW(x_dd,2)) AS sxx
           FROM `ybigta-505002.dunnhumby_mart.tmp_dd`),
r AS (SELECT d.product_id, d.x_dd*(d.y_dd - b.beta*d.x_dd) AS xe
      FROM `ybigta-505002.dunnhumby_mart.tmp_dd` d CROSS JOIN b),
cl AS (SELECT product_id, SUM(xe) AS g FROM r GROUP BY 1),
v AS (SELECT SUM(POW(g,2)) AS meat FROM cl)
SELECT ROUND((SELECT beta FROM b),4) AS beta_dd,
  ROUND(SQRT((SELECT meat FROM v))/(SELECT sxx FROM b),4) AS se_cluster,
  ROUND((SELECT beta FROM b)/(SQRT((SELECT meat FROM v))/(SELECT sxx FROM b)),1) AS t_dd,
  ROUND(1+(SELECT beta FROM b)/(SELECT AVG(IF(disp=0,net,NULL)) FROM `ybigta-505002.dunnhumby_mart.tmp_dd`),3) AS dd_lift;
