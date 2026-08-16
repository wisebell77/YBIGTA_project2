SELECT churn_status, COUNT(*) AS n,
       ROUND(AVG(median_gap),1) AS avg_median_gap,
       ROUND(AVG(recency_days),1) AS avg_recency,
       ROUND(AVG(n_visits),1) AS avg_visits
FROM `ybigta-505002.dunnhumby_mart.mart_household_churn`
GROUP BY churn_status ORDER BY n DESC;

SELECT churn_status_at_547, COUNT(*) AS n,
       ROUND(100*AVG(CAST(purchased_in_holdout AS INT64)),1) AS pct_repurchased,
       ROUND(AVG(n_visits_holdout),1) AS avg_holdout_visits,
       ROUND(AVG(sales_holdout),0) AS avg_holdout_sales,
       ROUND(AVG(recency_obs),1) AS avg_recency_at_547,
       ROUND(AVG(median_gap_obs),1) AS avg_gap_at_547
FROM `ybigta-505002.dunnhumby_mart.mart_household_churn`
GROUP BY churn_status_at_547 ORDER BY n DESC;

SELECT MIN(first_day) AS min_first, MAX(last_day) AS max_last,
       ROUND(AVG(median_gap),1) AS gap_all, APPROX_QUANTILES(median_gap,4) AS gap_quartiles
FROM `ybigta-505002.dunnhumby_mart.mart_household_churn`;
