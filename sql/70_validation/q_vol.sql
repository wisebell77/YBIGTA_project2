CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_occ_vol` AS
WITH sz AS (
  SELECT PRODUCT_ID AS product_id, COMMODITY_DESC AS cat,
    SAFE_CAST(REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^([0-9]+\.?[0-9]*)') AS FLOAT64) AS num,
    REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^[0-9]+\.?[0-9]*\s*([A-Z]+)') AS unit
  FROM `ybigta-505002.sql_study.product`),
conv AS (
  SELECT product_id, cat,
    CASE unit WHEN 'OZ' THEN num WHEN 'LTR' THEN num*33.814 WHEN 'LB' THEN num*16 END AS base_oz
  FROM sz
  WHERE (cat='SOFT DRINKS' AND unit IN ('OZ','LTR'))
     OR (cat='COLD CEREAL' AND unit='OZ')
     OR (cat='GRAPES'      AND unit='LB')),
cstore AS (SELECT DISTINCT store_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
cprod  AS (SELECT DISTINCT product_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
lines AS (
  SELECT f.household_key, conv.cat AS category, f.day,
    LEAST(f.quantity,20) AS qty,
    LEAST(f.quantity,20) * conv.base_oz AS vol_oz,
    f.net_sales AS net, f.gross_sales AS gross,
    COALESCE(c.mailer_ad,0) AS m,
    COALESCE(c.mailer_coupon,0)+COALESCE(c.mailer_free,0) AS x,
    COALESCE(c.display_any,0) AS dp
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN conv USING (product_id)
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN `ybigta-505002.dunnhumby_mart.mart_causal_clean` c
    ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101 AND conv.base_oz IS NOT NULL)
SELECT household_key, category, day, MAX(m) AS exposed,
  SUM(qty) AS qty, SUM(vol_oz) AS vol, SUM(net) AS net, SUM(gross) AS gross
FROM lines GROUP BY 1,2,3 HAVING MAX(x)=0 AND MAX(dp)=0;

WITH p AS (SELECT household_key,category FROM `ybigta-505002.dunnhumby_mart.mart_occ_vol`
           GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM `ybigta-505002.dunnhumby_mart.mart_occ_vol` o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) q,AVG(vol) v,AVG(net) n FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) q,AVG(vol) v,AVG(net) n FROM s WHERE exposed=0 GROUP BY 1,2)
SELECT e.category, COUNT(*) AS n_pairs,
  ROUND(100*(AVG(e.q)-AVG(u.q))/AVG(u.q),1) AS qty_pct,
  ROUND(100*(AVG(e.v)-AVG(u.v))/AVG(u.v),1) AS volume_pct,
  ROUND(100*(AVG(e.n)-AVG(u.n))/AVG(u.n),1) AS net_pct,
  ROUND(AVG(u.v)/AVG(u.q),2) AS unit_size_ctrl,
  ROUND(AVG(e.v)/AVG(e.q),2) AS unit_size_trt,
  ROUND(100*((AVG(e.v)/AVG(e.q))-(AVG(u.v)/AVG(u.q)))/(AVG(u.v)/AVG(u.q)),1) AS pack_upsize_pct
FROM e JOIN u USING (household_key,category) GROUP BY 1 ORDER BY n_pairs DESC;
