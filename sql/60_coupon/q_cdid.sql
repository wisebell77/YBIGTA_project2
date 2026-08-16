CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_coupon_did` AS
WITH onset AS (
  SELECT household_key, MIN(start_week) AS onset_week, MIN(start_day) AS onset_day
  FROM `ybigta-505002.dunnhumby_mart.mart_campaign_exposure` GROUP BY 1),
ddpre AS (
  SELECT household_key,
    SAFE_DIVIDE(SUM(retailer_funded_disc), SUM(gross_sales)) AS dd_pre,
    COUNT(DISTINCT basket_id) AS visits_pre
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
  WHERE day <= 223 GROUP BY 1),
q AS (SELECT household_key, dd_pre,
        NTILE(5) OVER (ORDER BY dd_pre) AS q_pre
      FROM ddpre WHERE visits_pre >= 5)
SELECT p.household_key, p.week_no,
  COALESCE(p.net_sales,0) AS net, p.n_baskets AS visits,
  o.onset_week, o.household_key IS NOT NULL AS treated,
  q.q_pre, q.dd_pre
FROM `ybigta-505002.dunnhumby_mart.mart_household_week` p
LEFT JOIN onset o USING (household_key)
LEFT JOIN q USING (household_key);
