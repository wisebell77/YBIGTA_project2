CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_household_disc_quintile` AS
WITH hh AS (
  SELECT
    household_key,
    SUM(gross_sales)                                    AS gross,
    SUM(retailer_funded_disc)                           AS disc_amt,
    SAFE_DIVIDE(SUM(retailer_funded_disc), SUM(gross_sales)) AS dd_value,
    SAFE_DIVIDE(COUNTIF(has_retail_disc), COUNT(*))     AS dd_lines,
    COUNT(*)                                            AS n_lines,
    COUNT(DISTINCT basket_id)                           AS n_visits,
    SUM(net_sales)                                      AS net_sales
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  GROUP BY household_key
)
SELECT *,
  NTILE(5) OVER (ORDER BY dd_value) AS q_value,
  NTILE(5) OVER (ORDER BY dd_lines) AS q_lines
FROM hh;

SELECT
  q_value,
  COUNT(*) AS households,
  ROUND(MIN(dd_value),4) AS dd_min,
  ROUND(MAX(dd_value),4) AS dd_max,
  ROUND(AVG(dd_value),4) AS dd_avg,
  ROUND(AVG(dd_lines),4) AS dd_lines_avg,
  ROUND(AVG(net_sales),0) AS avg_spend,
  ROUND(AVG(n_visits),0)  AS avg_visits,
  ROUND(SUM(net_sales),0) AS total_spend,
  ROUND(100*SUM(net_sales)/SUM(SUM(net_sales)) OVER (),1) AS pct_of_sales
FROM `ybigta-505002.dunnhumby_mart.mart_household_disc_quintile`
GROUP BY q_value ORDER BY q_value;
