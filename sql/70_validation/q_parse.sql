WITH p AS (
  SELECT PRODUCT_ID AS product_id, TRIM(CURR_SIZE_OF_PRODUCT) AS sz,
    REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^([0-9]+\.?[0-9]*)') AS num,
    REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^[0-9]+\.?[0-9]*\s*([A-Z]+)') AS unit
  FROM `ybigta-505002.sql_study.product`)
SELECT unit, COUNT(*) AS n_products,
  ROUND(100*SUM(COALESCE(s.sales,0))/SUM(SUM(COALESCE(s.sales,0))) OVER (),2) AS pct_sales
FROM p LEFT JOIN (SELECT product_id, SUM(net_sales) AS sales
                  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1) s USING (product_id)
GROUP BY unit ORDER BY pct_sales DESC LIMIT 18;

WITH p AS (
  SELECT PRODUCT_ID AS product_id,
    REGEXP_EXTRACT(TRIM(CURR_SIZE_OF_PRODUCT), r'^[0-9]+\.?[0-9]*\s*([A-Z]+)') AS unit
  FROM `ybigta-505002.sql_study.product`),
s AS (SELECT product_id, SUM(net_sales) AS sales FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1)
SELECT
  ROUND(100*SUM(IF(p.unit IS NOT NULL, COALESCE(s.sales,0), 0))/SUM(COALESCE(s.sales,0)),2) AS pct_sales_parseable,
  ROUND(100*SUM(IF(p.unit IN ('OZ','LB','ML','LT','LTR','L','GAL','QT','PT','GM','G','KG','CT','PK','EA','IN','FT','YD','SQ','ROLL'),
        COALESCE(s.sales,0),0))/SUM(COALESCE(s.sales,0)),2) AS pct_sales_known_unit
FROM p LEFT JOIN s USING (product_id);
