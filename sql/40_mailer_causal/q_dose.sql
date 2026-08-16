CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_occ_pos` AS
WITH cpos AS (
  SELECT PRODUCT_ID AS product_id, STORE_ID AS store_id, WEEK_NO AS week_no,
    MAX(IF(mailer='D',1,0))           AS m_front,
    MAX(IF(mailer IN ('A','C'),1,0))  AS m_interior,
    MAX(IF(mailer IN ('F','H','L'),1,0)) AS m_other,
    MAX(IF(mailer IN ('J','P','X','Z'),1,0)) AS m_excl,
    MAX(IF(display<>'0',1,0))         AS disp
  FROM `ybigta-505002.sql_study.causal_data` GROUP BY 1,2,3),
cstore AS (SELECT DISTINCT store_id FROM cpos), cprod AS (SELECT DISTINCT product_id FROM cpos),
lines AS (
  SELECT f.household_key, f.commodity_desc AS category, f.day,
    LEAST(f.quantity,20) AS qty, f.net_sales AS net,
    COALESCE(c.m_front,0) AS mf, COALESCE(c.m_interior,0) AS mi,
    COALESCE(c.m_other,0) AS mo, COALESCE(c.m_excl,0) AS mx, COALESCE(c.disp,0) AS dp
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN cpos c ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101
    AND f.commodity_desc NOT IN ('COUPON','MISC ITEMS','NO COMMODITY DESCRIPTION'))
SELECT household_key, category, day, SUM(qty) AS qty, SUM(net) AS net,
  MAX(mf) AS front, MAX(mi) AS interior, MAX(mo) AS other_pos
FROM lines GROUP BY 1,2,3
HAVING MAX(mx)=0 AND MAX(dp)=0;

-- 가구-카테고리 내부 비교: 대조 / 내지 / 1면
WITH p AS (SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_pos`
           GROUP BY 1,2
           HAVING COUNT(*)>=6 AND SUM(front)>=1 AND SUM(interior)>=1
              AND SUM(IF(front=0 AND interior=0 AND other_pos=0,1,0))>=2),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_pos` o JOIN p USING (household_key,category)),
c AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE front=0 AND interior=0 AND other_pos=0 GROUP BY 1,2),
i AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE interior=1 AND front=0 GROUP BY 1,2),
fr AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE front=1 GROUP BY 1,2)
SELECT COUNT(*) AS n_pairs,
  ROUND(AVG(c.q),3) AS qty_control, ROUND(AVG(i.q),3) AS qty_interior, ROUND(AVG(fr.q),3) AS qty_front,
  ROUND(100*(AVG(i.q)-AVG(c.q))/AVG(c.q),1)  AS interior_pct,
  ROUND(100*(AVG(fr.q)-AVG(c.q))/AVG(c.q),1) AS front_pct,
  ROUND(AVG(fr.q-i.q)/(STDDEV(fr.q-i.q)/SQRT(COUNT(*))),2) AS t_front_vs_interior,
  ROUND(AVG(c.n),3) AS net_control, ROUND(AVG(i.n),3) AS net_interior, ROUND(AVG(fr.n),3) AS net_front,
  ROUND(100*(AVG(i.n)-AVG(c.n))/AVG(c.n),1)  AS net_interior_pct,
  ROUND(100*(AVG(fr.n)-AVG(c.n))/AVG(c.n),1) AS net_front_pct
FROM c JOIN i USING (household_key,category) JOIN fr USING (household_key,category);
