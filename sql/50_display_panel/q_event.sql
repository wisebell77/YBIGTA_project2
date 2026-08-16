CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.tmp_event` AS
WITH lg AS (
  SELECT product_id, store_id, week_no, net, disp,
    LAG(disp) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS disp_prev,
    LAG(net,3) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_m3,
    LAG(net,2) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_m2,
    LAG(net,1) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_m1,
    net AS y_0,
    LEAD(net,1) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_p1,
    LEAD(net,2) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_p2,
    LEAD(net,3) OVER (PARTITION BY product_id, store_id ORDER BY week_no) AS y_p3
  FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel`),
onset AS (SELECT *, IF(disp=1 AND COALESCE(disp_prev,0)=0, 1, 0) AS x FROM lg
          WHERE y_m3 IS NOT NULL AND y_p3 IS NOT NULL AND COALESCE(disp_prev,0)=0),
long AS (
  SELECT product_id, store_id, week_no, x, k, y FROM onset,
  UNNEST([STRUCT(-3 AS k, y_m3 AS y),(-2,y_m2),(-1,y_m1),(0,y_0),(1,y_p1),(2,y_p2),(3,y_p3)])),
vc AS (SELECT product_id, week_no, k FROM long GROUP BY 1,2,3 HAVING SUM(x)>0 AND SUM(x)<COUNT(*)),
f AS (SELECT l.* FROM long l JOIN vc USING (product_id, week_no, k)),
i1 AS (SELECT *, y-AVG(y) OVER (PARTITION BY product_id,week_no,k) AS y1,
                 x-AVG(x) OVER (PARTITION BY product_id,week_no,k) AS x1 FROM f),
i2 AS (SELECT *, y1-AVG(y1) OVER (PARTITION BY product_id,store_id,k) AS y2,
                 x1-AVG(x1) OVER (PARTITION BY product_id,store_id,k) AS x2 FROM i1),
i3 AS (SELECT *, y2-AVG(y2) OVER (PARTITION BY product_id,week_no,k) AS y3,
                 x2-AVG(x2) OVER (PARTITION BY product_id,week_no,k) AS x3 FROM i2),
i4 AS (SELECT *, y3-AVG(y3) OVER (PARTITION BY product_id,store_id,k) AS y4,
                 x3-AVG(x3) OVER (PARTITION BY product_id,store_id,k) AS x4 FROM i3),
i5 AS (SELECT *, y4-AVG(y4) OVER (PARTITION BY product_id,week_no,k) AS y5,
                 x4-AVG(x4) OVER (PARTITION BY product_id,week_no,k) AS x5 FROM i4)
SELECT product_id, k, y5 AS yd, x5 AS xd FROM i5;

WITH b AS (SELECT k, SUM(yd*xd)/SUM(POW(xd,2)) AS beta, SUM(POW(xd,2)) AS sxx, COUNT(*) AS n
           FROM `ybigta-505002.dunnhumby_mart.tmp_event` GROUP BY k),
r AS (SELECT e.k, e.product_id, e.xd*(e.yd - b.beta*e.xd) AS xe
      FROM `ybigta-505002.dunnhumby_mart.tmp_event` e JOIN b USING (k)),
cl AS (SELECT k, product_id, SUM(xe) AS g FROM r GROUP BY 1,2),
v AS (SELECT k, SUM(POW(g,2)) AS meat FROM cl GROUP BY k)
SELECT b.k AS event_week, b.n AS obs,
  ROUND(b.beta,4) AS beta,
  ROUND(SQRT(v.meat)/b.sxx,4) AS se,
  ROUND(b.beta/(SQRT(v.meat)/b.sxx),2) AS t
FROM b JOIN v USING (k) ORDER BY b.k;
