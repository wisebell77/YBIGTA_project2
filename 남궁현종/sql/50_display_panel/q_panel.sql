CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_psw_panel` AS
WITH cstore AS (SELECT DISTINCT store_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`),
wk AS (SELECT week_no FROM UNNEST(GENERATE_ARRAY(9,101)) AS week_no),
topprod AS (
  SELECT f.product_id
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` f
  JOIN cstore USING (store_id)
  WHERE f.week_no BETWEEN 9 AND 101
    AND f.product_id IN (SELECT DISTINCT product_id FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`)
  GROUP BY 1 ORDER BY SUM(f.net_sales) DESC LIMIT 500
),
grid AS (SELECT product_id, store_id, week_no FROM topprod CROSS JOIN cstore CROSS JOIN wk),
sales AS (
  SELECT product_id, store_id, week_no,
    SUM(net_sales) AS net, SUM(LEAST(quantity,20)) AS qty,
    SUM(gross_sales) AS gross, SUM(retailer_funded_disc) AS disc
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE week_no BETWEEN 9 AND 101
  GROUP BY 1,2,3
)
SELECT g.product_id, g.store_id, g.week_no,
  COALESCE(s.net,0) AS net, COALESCE(s.qty,0) AS qty,
  COALESCE(s.gross,0) AS gross, COALESCE(s.disc,0) AS disc,
  COALESCE(c.display_strict,0) AS disp,
  COALESCE(c.mailer_ad,0)      AS mail
FROM grid g
LEFT JOIN sales s USING (product_id, store_id, week_no)
LEFT JOIN `ybigta-505002.dunnhumby_mart.mart_causal_clean` c USING (product_id, store_id, week_no);

SELECT COUNT(*) AS rows_,
  ROUND(100*AVG(disp),2) AS pct_disp,
  ROUND(100*AVG(mail),2) AS pct_mail,
  ROUND(100*COUNTIF(net>0)/COUNT(*),2) AS pct_nonzero,
  ROUND(AVG(net),4) AS avg_net,
  ROUND(SUM(net),0) AS total_net
FROM `ybigta-505002.dunnhumby_mart.mart_psw_panel`;
