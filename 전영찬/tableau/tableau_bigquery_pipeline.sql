-- Period-split, event-time validation for CRM promotion strategy.
-- Decisions reflected here:
--   * event unit: household x category x purchase day
--   * treatment: deep discount >=30%; control: full price <=2%
--   * symmetric clean-event rule: no OTHER deep-discount event in the same
--     household-category within +/-28 days
--   * training events DAY 169-355; validation events DAY 356-683
--   * 84-day RFM plus prior-84-day trend; thresholds learned on training only
--   * four value tiers, three RFM weighting schemes
--   * five rule-based household-category behaviors using only pre-event data
--   * outcomes: next-28-day store visits and store spend

CREATE OR REPLACE TABLE `crucial-axon-503903-k2.dunnhumby.crm_event_validation`
OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) AS
WITH line_base AS (
  SELECT t.household_key, t.DAY, t.WEEK_NO, t.BASKET_ID,
    p.COMMODITY_DESC, t.QUANTITY, t.SALES_VALUE AS spend,
    t.SALES_VALUE - t.RETAIL_DISC AS regular_value,
    SAFE_DIVIDE(-t.RETAIL_DISC, t.SALES_VALUE - t.RETAIL_DISC) AS discount_rate
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` t
  JOIN `crucial-axon-503903-k2.dunnhumby.product` p USING(PRODUCT_ID)
  WHERE p.COMMODITY_DESC != 'COUPON/MISC ITEMS'
    AND t.QUANTITY > 0 AND t.SALES_VALUE - t.RETAIL_DISC > 0
),
daily_store AS (
  SELECT household_key, DAY, SUM(spend) store_spend,
    COUNT(DISTINCT BASKET_ID) baskets,
    COUNT(DISTINCT COMMODITY_DESC) categories
  FROM line_base GROUP BY 1,2
),
occasion0 AS (
  SELECT household_key, COMMODITY_DESC, DAY,
    SUM(QUANTITY) qty, SUM(spend) cat_spend, SUM(regular_value) regular_value,
    SAFE_DIVIDE(SUM(regular_value)-SUM(spend),SUM(regular_value)) discount_rate
  FROM line_base GROUP BY 1,2,3
),
occasion AS (
  SELECT *, discount_rate>=.30 deep, discount_rate<=.02 full_price,
    LEAD(DAY) OVER(PARTITION BY household_key,COMMODITY_DESC ORDER BY DAY) next_day
  FROM occasion0
),
candidate AS (
  SELECT *, CONCAT(CAST(household_key AS STRING),'|',COMMODITY_DESC,'|',CAST(DAY AS STRING)) event_id,
    IF(DAY<=355,'TRAIN','VALID') sample
  FROM occasion o
  WHERE DAY BETWEEN 169 AND 683 AND (deep OR full_price)
    AND NOT EXISTS (
      SELECT 1 FROM occasion d
      WHERE d.household_key=o.household_key AND d.COMMODITY_DESC=o.COMMODITY_DESC
        AND d.deep AND d.DAY!=o.DAY AND ABS(d.DAY-o.DAY)<=28
    )
),
store_hist AS (
  SELECT e.event_id,
    e.DAY-MAX(IF(d.DAY BETWEEN e.DAY-84 AND e.DAY-1,d.DAY,NULL)) recency84,
    COUNT(DISTINCT IF(d.DAY BETWEEN e.DAY-84 AND e.DAY-1,d.DAY,NULL)) frequency84,
    COALESCE(SUM(IF(d.DAY BETWEEN e.DAY-84 AND e.DAY-1,d.store_spend,0)),0) monetary84,
    COUNT(DISTINCT IF(d.DAY BETWEEN e.DAY-168 AND e.DAY-85,d.DAY,NULL)) frequency_prev84,
    COALESCE(SUM(IF(d.DAY BETWEEN e.DAY-168 AND e.DAY-85,d.store_spend,0)),0) monetary_prev84
  FROM candidate e LEFT JOIN daily_store d
    ON d.household_key=e.household_key AND d.DAY BETWEEN e.DAY-168 AND e.DAY-1
  GROUP BY 1,e.DAY
),
cat_hist AS (
  SELECT e.event_id,
    COUNTIF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1) pre_cat_count,
    COUNTIF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.deep) pre_deep_count,
    COUNTIF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.full_price) pre_full_count,
    SAFE_DIVIDE(COUNTIF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.deep),
      COUNTIF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1)) pre_deep_share,
    AVG(IF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1,c.next_day-c.DAY,NULL)) pre_avg_gap,
    AVG(IF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.deep AND c.next_day<e.DAY,c.next_day-c.DAY,NULL)) deep_gap,
    AVG(IF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.full_price AND c.next_day<e.DAY,c.next_day-c.DAY,NULL)) full_gap,
    AVG(IF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.deep,c.qty,NULL)) deep_qty,
    AVG(IF(c.DAY BETWEEN e.DAY-168 AND e.DAY-1 AND c.full_price,c.qty,NULL)) full_qty
  FROM candidate e LEFT JOIN occasion c
    ON c.household_key=e.household_key AND c.COMMODITY_DESC=e.COMMODITY_DESC
   AND c.DAY BETWEEN e.DAY-168 AND e.DAY-1
  GROUP BY 1
),
outcome AS (
  SELECT e.event_id,
    COUNT(DISTINCT d.DAY) post28_visits,
    COALESCE(SUM(d.store_spend),0) post28_store_spend
  FROM candidate e LEFT JOIN daily_store d
    ON d.household_key=e.household_key AND d.DAY BETWEEN e.DAY+1 AND e.DAY+28
  GROUP BY 1
),
feature0 AS (
  SELECT e.*, s.* EXCEPT(event_id), c.* EXCEPT(event_id), y.* EXCEPT(event_id),
    SAFE_DIVIDE(s.frequency84-s.frequency_prev84,NULLIF(s.frequency_prev84,0)) frequency_trend,
    SAFE_DIVIDE(s.monetary84-s.monetary_prev84,NULLIF(s.monetary_prev84,0)) monetary_trend
  FROM candidate e JOIN store_hist s USING(event_id)
  JOIN cat_hist c USING(event_id) JOIN outcome y USING(event_id)
),
rfm_cut AS (
  SELECT
    APPROX_QUANTILES(COALESCE(recency84,999),5) r,
    APPROX_QUANTILES(frequency84,5) f,
    APPROX_QUANTILES(monetary84,5) m
  FROM feature0 WHERE sample='TRAIN'
),
rfm_score AS (
  SELECT x.*,
    6-(1+CAST(COALESCE(recency84,999)>r[OFFSET(1)] AS INT64)
       +CAST(COALESCE(recency84,999)>r[OFFSET(2)] AS INT64)
       +CAST(COALESCE(recency84,999)>r[OFFSET(3)] AS INT64)
       +CAST(COALESCE(recency84,999)>r[OFFSET(4)] AS INT64)) r_score,
    1+CAST(frequency84>f[OFFSET(1)] AS INT64)+CAST(frequency84>f[OFFSET(2)] AS INT64)
     +CAST(frequency84>f[OFFSET(3)] AS INT64)+CAST(frequency84>f[OFFSET(4)] AS INT64) f_score,
    1+CAST(monetary84>m[OFFSET(1)] AS INT64)+CAST(monetary84>m[OFFSET(2)] AS INT64)
     +CAST(monetary84>m[OFFSET(3)] AS INT64)+CAST(monetary84>m[OFFSET(4)] AS INT64) m_score
  FROM feature0 x CROSS JOIN rfm_cut
),
weighted AS (
  SELECT *,
    (r_score+f_score+m_score)/3 equal_score,
    .3*r_score+.4*f_score+.3*m_score visit_score,
    .2*r_score+.3*f_score+.5*m_score spend_score
  FROM rfm_score
),
value_cut AS (
  SELECT APPROX_QUANTILES(equal_score,4) eq,
    APPROX_QUANTILES(visit_score,4) vi, APPROX_QUANTILES(spend_score,4) sp
  FROM weighted WHERE sample='TRAIN'
),
cat_cut AS (
  SELECT COMMODITY_DESC,
    APPROX_QUANTILES(pre_avg_gap,2)[SAFE_OFFSET(1)] median_gap,
    APPROX_QUANTILES(pre_deep_share,2)[SAFE_OFFSET(1)] median_deep_share
  FROM weighted WHERE sample='TRAIN' GROUP BY 1
),
classified AS (
  SELECT w.*,
    CASE WHEN equal_score<=eq[OFFSET(1)] THEN 'V4 Low engagement'
      WHEN equal_score<=eq[OFFSET(2)] THEN 'V3 Maintain'
      WHEN equal_score<=eq[OFFSET(3)] THEN 'V2 Growth potential'
      ELSE 'V1 Core' END equal_value_tier,
    CASE WHEN visit_score<=vi[OFFSET(1)] THEN 'V4 Low engagement'
      WHEN visit_score<=vi[OFFSET(2)] THEN 'V3 Maintain'
      WHEN visit_score<=vi[OFFSET(3)] THEN 'V2 Growth potential'
      ELSE 'V1 Core' END visit_value_tier,
    CASE WHEN spend_score<=sp[OFFSET(1)] THEN 'V4 Low engagement'
      WHEN spend_score<=sp[OFFSET(2)] THEN 'V3 Maintain'
      WHEN spend_score<=sp[OFFSET(3)] THEN 'V2 Growth potential'
      ELSE 'V1 Core' END spend_value_tier,
    frequency84<frequency_prev84 AS churn_risk,
    CASE
      WHEN pre_cat_count>=3 AND deep_qty>full_qty*1.2 AND deep_gap>full_gap*1.15
        THEN 'C1 Stock-up risk'
      WHEN pre_cat_count=0 THEN 'C2 New trial'
      WHEN pre_cat_count>=3 AND SAFE_DIVIDE(pre_full_count,pre_cat_count)>=.5
        AND pre_avg_gap<=cc.median_gap THEN 'C3 Regular-price repeat'
      WHEN pre_cat_count>=3 AND pre_deep_share>=cc.median_deep_share
        AND deep_qty>full_qty THEN 'C4 Promotion responsive'
      ELSE 'C5 Low-frequency/irregular' END cat_behavior
  FROM weighted w CROSS JOIN value_cut
  LEFT JOIN cat_cut cc USING(COMMODITY_DESC)
)
SELECT * FROM classified;

-- Segment KPI extract. Household-level differences make the main uncertainty
-- calculation equivalent to household-clustered inference.
CREATE OR REPLACE TABLE `crucial-axon-503903-k2.dunnhumby.tableau_segment_kpi`
OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) AS
WITH long_tier AS (
  SELECT v.*,'Equal RFM' AS weight_method,equal_value_tier AS value_tier
  FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation` v WHERE sample='VALID'
  UNION ALL
  SELECT v.*,'Visit weighted' AS weight_method,visit_value_tier AS value_tier
  FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation` v WHERE sample='VALID'
  UNION ALL
  SELECT v.*,'Spend weighted' AS weight_method,spend_value_tier AS value_tier
  FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation` v WHERE sample='VALID'
),
hh AS (
  SELECT weight_method,value_tier,churn_risk,cat_behavior,household_key,
    COUNTIF(deep) deep_events,COUNTIF(full_price) full_events,
    AVG(IF(deep,post28_visits,NULL))-AVG(IF(full_price,post28_visits,NULL)) visit_diff,
    AVG(IF(deep,post28_store_spend,NULL))-AVG(IF(full_price,post28_store_spend,NULL)) spend_diff
  FROM long_tier GROUP BY 1,2,3,4,5
  HAVING deep_events>0 AND full_events>0
),
agg AS (
  SELECT weight_method,value_tier,churn_risk,cat_behavior,
    COUNT(*) households,SUM(deep_events) deep_events,SUM(full_events) full_events,
    AVG(visit_diff) visit_diff,STDDEV_SAMP(visit_diff)/SQRT(COUNT(*)) visit_se,
    AVG(spend_diff) spend_diff,STDDEV_SAMP(spend_diff)/SQRT(COUNT(*)) spend_se
  FROM hh GROUP BY 1,2,3,4
)
SELECT *,visit_diff-1.96*visit_se visit_ci_low,visit_diff+1.96*visit_se visit_ci_high,
  spend_diff-1.96*spend_se spend_ci_low,spend_diff+1.96*spend_se spend_ci_high,
  CASE WHEN visit_diff>=0 AND spend_diff>=0 THEN 'Q1 Relationship strengthened'
    WHEN visit_diff>=0 AND spend_diff<0 THEN 'Q2 More low-value visits'
    WHEN visit_diff<0 AND spend_diff>=0 THEN 'Q3 Fewer high-value visits'
    ELSE 'Q4 Relationship weakened' END performance_quadrant
FROM agg;

CREATE OR REPLACE TABLE `crucial-axon-503903-k2.dunnhumby.tableau_category_kpi`
OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) AS
WITH hh AS (
  SELECT COMMODITY_DESC,household_key,
    COUNTIF(deep) deep_events,COUNTIF(full_price) full_events,
    AVG(IF(deep,post28_visits,NULL))-AVG(IF(full_price,post28_visits,NULL)) visit_diff,
    AVG(IF(deep,post28_store_spend,NULL))-AVG(IF(full_price,post28_store_spend,NULL)) spend_diff
  FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation`
  WHERE sample='VALID' GROUP BY 1,2
  HAVING deep_events>0 AND full_events>0
)
SELECT COMMODITY_DESC,COUNT(*) households,SUM(deep_events) deep_events,SUM(full_events) full_events,
  AVG(visit_diff) visit_diff,STDDEV_SAMP(visit_diff)/SQRT(COUNT(*)) visit_se,
  AVG(spend_diff) spend_diff,STDDEV_SAMP(spend_diff)/SQRT(COUNT(*)) spend_se,
  CASE WHEN AVG(visit_diff)>=0 AND AVG(spend_diff)>=0 THEN 'Q1 Relationship strengthened'
    WHEN AVG(visit_diff)>=0 AND AVG(spend_diff)<0 THEN 'Q2 More low-value visits'
    WHEN AVG(visit_diff)<0 AND AVG(spend_diff)>=0 THEN 'Q3 Fewer high-value visits'
    ELSE 'Q4 Relationship weakened' END performance_quadrant
FROM hh GROUP BY 1 HAVING households>=20;

CREATE OR REPLACE TABLE `crucial-axon-503903-k2.dunnhumby.tableau_rfm_stability`
OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)) AS
SELECT sample,equal_value_tier,visit_value_tier,spend_value_tier,COUNT(*) events,
  COUNT(DISTINCT household_key) households
FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation`
GROUP BY 1,2,3,4;

-- Compact dashboard headline KPIs.
SELECT 'validation_events' metric,CAST(COUNT(*) AS STRING) value
FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation` WHERE sample='VALID'
UNION ALL SELECT 'validation_households',CAST(COUNT(DISTINCT household_key) AS STRING)
FROM `crucial-axon-503903-k2.dunnhumby.crm_event_validation` WHERE sample='VALID'
UNION ALL SELECT 'segment_kpi_rows',CAST(COUNT(*) AS STRING)
FROM `crucial-axon-503903-k2.dunnhumby.tableau_segment_kpi`
UNION ALL SELECT 'category_kpi_rows',CAST(COUNT(*) AS STRING)
FROM `crucial-axon-503903-k2.dunnhumby.tableau_category_kpi`;
