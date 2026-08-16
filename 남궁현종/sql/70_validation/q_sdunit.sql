WITH p AS (
  SELECT PRODUCT_ID AS product_id, COMMODITY_DESC AS cat,
    SAFE_CAST(REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^([0-9]+\.?[0-9]*)') AS FLOAT64) AS num,
    REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^[0-9]+\.?[0-9]*\s*([A-Z]+)') AS unit
  FROM `ybigta-505002.sql_study.product`),
s AS (SELECT product_id, SUM(net_sales) AS sales FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1)
SELECT p.cat, p.unit, COUNT(*) AS n_prod, ROUND(SUM(COALESCE(s.sales,0)),0) AS sales,
  ROUND(100*SUM(COALESCE(s.sales,0))/SUM(SUM(COALESCE(s.sales,0))) OVER (PARTITION BY p.cat),1) AS pct_in_cat
FROM p LEFT JOIN s USING (product_id)
WHERE p.cat IN ('SOFT DRINKS','COLD CEREAL','CHICKEN','GRAPES','BEEF')
GROUP BY 1,2 HAVING SUM(COALESCE(s.sales,0)) > 0
QUALIFY ROW_NUMBER() OVER (PARTITION BY p.cat ORDER BY sales DESC) <= 4
ORDER BY p.cat, sales DESC
