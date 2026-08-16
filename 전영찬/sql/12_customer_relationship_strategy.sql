-- Customer-relationship promotion strategy extension
-- BigQuery Standard SQL. All outputs are diagnostic associations, not causal estimates.

WITH line_base AS (
  SELECT
    t.household_key,
    t.DAY,
    t.WEEK_NO,
    t.BASKET_ID,
    p.COMMODITY_DESC,
    t.QUANTITY,
    t.SALES_VALUE AS spend,
    t.SALES_VALUE - t.RETAIL_DISC AS regular_value,
    SAFE_DIVIDE(-t.RETAIL_DISC, t.SALES_VALUE - t.RETAIL_DISC) AS discount_rate
  FROM `crucial-axon-503903-k2.dunnhumby.transaction_data` t
  JOIN `crucial-axon-503903-k2.dunnhumby.product` p USING (PRODUCT_ID)
  WHERE p.COMMODITY_DESC != 'COUPON/MISC ITEMS'
    AND t.QUANTITY > 0
    AND t.SALES_VALUE - t.RETAIL_DISC > 0
),

daily_store AS (
  SELECT household_key, DAY,
    SUM(spend) AS store_spend,
    COUNT(DISTINCT BASKET_ID) AS baskets,
    COUNT(DISTINCT COMMODITY_DESC) AS categories
  FROM line_base GROUP BY 1,2
),

occasions0 AS (
  SELECT household_key, COMMODITY_DESC, DAY,
    SUM(QUANTITY) AS qty,
    SUM(spend) AS cat_spend,
    SUM(regular_value) AS regular_value,
    SAFE_DIVIDE(SUM(regular_value)-SUM(spend), SUM(regular_value)) AS discount_rate
  FROM line_base GROUP BY 1,2,3
),

occasions AS (
  SELECT o.*,
    discount_rate >= .30 AS deep,
    discount_rate <= .02 AS full_price,
    LEAD(DAY) OVER(PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY)-DAY AS next_days,
    ROW_NUMBER() OVER(PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY) AS cat_order
  FROM occasions0 o
),

occasion_context AS (
  SELECT o.*, d.store_spend, d.categories,
    d.store_spend-o.cat_spend AS other_cat_spend,
    (SELECT COUNT(DISTINCT d2.DAY) FROM daily_store d2
      WHERE d2.household_key=o.household_key AND d2.DAY BETWEEN o.DAY+1 AND o.DAY+28) AS post28_visits,
    (SELECT COALESCE(SUM(d2.store_spend),0) FROM daily_store d2
      WHERE d2.household_key=o.household_key AND d2.DAY BETWEEN o.DAY+1 AND o.DAY+28) AS post28_store_spend,
    (SELECT COALESCE(SUM(o2.qty),0) FROM occasions0 o2
      WHERE o2.household_key=o.household_key AND o2.COMMODITY_DESC=o.COMMODITY_DESC
        AND o2.DAY BETWEEN o.DAY+1 AND o.DAY+56) AS post56_cat_qty
  FROM occasions o JOIN daily_store d USING(household_key,DAY)
  WHERE o.DAY <= 655
),

eligible AS (
  SELECT household_key, COMMODITY_DESC
  FROM occasion_context GROUP BY 1,2
  HAVING COUNT(*) >= 5 AND COUNTIF(deep)>=2 AND COUNTIF(full_price)>=2
),

pair_effect AS (
  SELECT o.household_key, o.COMMODITY_DESC,
    AVG(IF(deep,qty,NULL))-AVG(IF(full_price,qty,NULL)) AS qty_diff,
    AVG(IF(deep,cat_spend,NULL))-AVG(IF(full_price,cat_spend,NULL)) AS cat_spend_diff,
    AVG(IF(deep,other_cat_spend,NULL))-AVG(IF(full_price,other_cat_spend,NULL)) AS halo_diff,
    AVG(IF(deep,post28_visits,NULL))-AVG(IF(full_price,post28_visits,NULL)) AS post28_visit_diff,
    AVG(IF(deep,post28_store_spend,NULL))-AVG(IF(full_price,post28_store_spend,NULL)) AS post28_store_spend_diff,
    AVG(IF(deep,post56_cat_qty,NULL))-AVG(IF(full_price,post56_cat_qty,NULL)) AS post56_cat_qty_diff,
    AVG(IF(deep,next_days,NULL))-AVG(IF(full_price,next_days,NULL)) AS next_days_diff
  FROM occasion_context o JOIN eligible USING(household_key,COMMODITY_DESC)
  GROUP BY 1,2
),

hh_effect AS (
  SELECT household_key, COUNT(*) AS eligible_categories,
    AVG(qty_diff) AS qty_diff, AVG(cat_spend_diff) AS cat_spend_diff,
    AVG(halo_diff) AS halo_diff, AVG(post28_visit_diff) AS post28_visit_diff,
    AVG(post28_store_spend_diff) AS post28_store_spend_diff,
    AVG(post56_cat_qty_diff) AS post56_cat_qty_diff,
    AVG(next_days_diff) AS next_days_diff
  FROM pair_effect GROUP BY 1
),

hh_affinity AS (
  SELECT household_key, AVG(discount_rate) AS avg_discount,
    SAFE_DIVIDE(COUNTIF(deep),COUNT(*)) AS deep_share
  FROM occasions GROUP BY 1
),

hh_scored AS (
  SELECT e.*, a.deep_share, a.avg_discount,
    PERCENT_RANK() OVER(ORDER BY post28_store_spend_diff) AS spend_pr,
    PERCENT_RANK() OVER(ORDER BY halo_diff) AS halo_pr,
    PERCENT_RANK() OVER(ORDER BY deep_share) AS affinity_pr
  FROM hh_effect e JOIN hh_affinity a USING(household_key)
),

hh_segment AS (
  SELECT *, CASE
    WHEN post56_cat_qty_diff < 0 AND next_days_diff > 0 THEN 'S1 Stock-up risk'
    WHEN spend_pr >= .60 AND post28_visit_diff > 0 THEN 'S2 Relationship amplifier'
    WHEN halo_pr >= .60 AND post28_store_spend_diff <= 0 THEN 'S3 Basket-only expander'
    WHEN affinity_pr >= .80 AND cat_spend_diff <= 0 THEN 'S4 Discount dependent'
    ELSE 'S5 Low/unclear response' END AS segment
  FROM hh_scored
),

-- First category purchase and subsequent regular-price conversion.
trial AS (
  SELECT f.household_key, f.COMMODITY_DESC, f.deep AS first_deep,
    COUNTIF(r.DAY BETWEEN f.DAY+1 AND f.DAY+56)>0 AS any_repeat_56,
    COUNTIF(r.DAY BETWEEN f.DAY+1 AND f.DAY+56 AND r.full_price)>0 AS regular_repeat_56
  FROM occasions f
  LEFT JOIN occasions r USING(household_key,COMMODITY_DESC)
  WHERE f.cat_order=1 AND f.DAY<=655
  GROUP BY 1,2,3
),

category_basic AS (
  SELECT COMMODITY_DESC,
    COUNT(DISTINCT household_key) AS buyer_hh,
    SAFE_DIVIDE(COUNT(DISTINCT household_key),2500) AS penetration,
    SAFE_DIVIDE(COUNT(*),COUNT(DISTINCT household_key)) AS occasions_per_buyer,
    AVG(next_days) AS mean_gap,
    AVG(discount_rate) AS avg_discount
  FROM occasions GROUP BY 1
  HAVING COUNT(DISTINCT household_key)>=100
),

category_coshop AS (
  SELECT o.COMMODITY_DESC,
    AVG(IF(d.categories>1,1,0)) AS coshop_rate,
    AVG(SAFE_DIVIDE(o.cat_spend,d.store_spend)) AS basket_value_share
  FROM occasions0 o JOIN daily_store d USING(household_key,DAY)
  GROUP BY 1
),

category_week AS (
  SELECT COMMODITY_DESC, WEEK_NO, SUM(spend) AS spend
  FROM line_base GROUP BY 1,2
),

category_season AS (
  SELECT COMMODITY_DESC,
    SAFE_DIVIDE(SUM(IF(week_rank<=13,spend,0)),SUM(spend)) AS top13_week_share
  FROM (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY COMMODITY_DESC ORDER BY spend DESC) AS week_rank
    FROM category_week
  ) GROUP BY 1
),

category_metric AS (
  SELECT b.*, c.coshop_rate, c.basket_value_share, s.top13_week_share,
    PERCENT_RANK() OVER(ORDER BY penetration) AS pen_pr,
    PERCENT_RANK() OVER(ORDER BY occasions_per_buyer) AS freq_pr,
    PERCENT_RANK() OVER(ORDER BY top13_week_share) AS season_pr,
    PERCENT_RANK() OVER(ORDER BY basket_value_share) AS share_pr
  FROM category_basic b JOIN category_coshop c USING(COMMODITY_DESC)
  JOIN category_season s USING(COMMODITY_DESC)
),

category_roles AS (
  SELECT *, CASE
    WHEN season_pr>=.85 THEN 'R3 Seasonal/Occasional proxy'
    WHEN pen_pr>=.70 AND share_pr>=.60 THEN 'R1 Destination/Traffic proxy'
    WHEN freq_pr>=.65 AND mean_gap<=45 THEN 'R2 Routine proxy'
    ELSE 'R4 Convenience/Complement proxy' END AS role_label
  FROM category_metric
),

segment_demo AS (
  SELECT s.segment, COUNT(*) AS households,
    AVG(s.deep_share) AS deep_share,
    AVG(s.post28_visit_diff) AS visit_diff,
    AVG(s.post28_store_spend_diff) AS store_spend_diff,
    AVG(s.halo_diff) AS halo_diff,
    AVG(s.post56_cat_qty_diff) AS post56_qty_diff,
    AVG(s.next_days_diff) AS gap_diff,
    APPROX_TOP_COUNT(d.INCOME_DESC,1)[SAFE_OFFSET(0)].value AS top_income,
    APPROX_TOP_COUNT(d.AGE_DESC,1)[SAFE_OFFSET(0)].value AS top_age,
    APPROX_TOP_COUNT(d.HH_COMP_DESC,1)[SAFE_OFFSET(0)].value AS top_hh_comp
  FROM hh_segment s LEFT JOIN `crucial-axon-503903-k2.dunnhumby.hh_demographic` d USING(household_key)
  GROUP BY 1
)

SELECT 'A_SEGMENT' AS section, segment AS label, households AS n,
  ROUND(deep_share,4) AS m1, ROUND(visit_diff,4) AS m2,
  ROUND(store_spend_diff,3) AS m3, ROUND(halo_diff,3) AS m4,
  ROUND(post56_qty_diff,3) AS m5, ROUND(gap_diff,3) AS m6,
  CONCAT(COALESCE(top_income,'NA'),' | ',COALESCE(top_age,'NA'),' | ',COALESCE(top_hh_comp,'NA')) AS note
FROM segment_demo

UNION ALL
SELECT 'B_TRIAL', IF(first_deep,'First purchase: deep discount','First purchase: not deep'), COUNT(*),
  ROUND(AVG(IF(any_repeat_56,1,0)),4), ROUND(AVG(IF(regular_repeat_56,1,0)),4),
  NULL,NULL,NULL,NULL,'m1=any repeat 56d; m2=regular-price repeat 56d'
FROM trial GROUP BY first_deep

UNION ALL
SELECT 'C_ROLE', cr.role_label, COUNT(*),
  ROUND(AVG(penetration),4), ROUND(AVG(occasions_per_buyer),2),
  ROUND(AVG(mean_gap),2), ROUND(AVG(coshop_rate),4),
  ROUND(AVG(basket_value_share),4), ROUND(AVG(top13_week_share),4),
  'role-level averages; proxy classification'
FROM category_roles cr GROUP BY cr.role_label

ORDER BY section,label;
