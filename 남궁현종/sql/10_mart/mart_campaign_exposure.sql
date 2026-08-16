CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.mart_campaign_exposure`
CLUSTER BY household_key, campaign
AS
SELECT
  t.household_key,
  t.CAMPAIGN                                        AS campaign,
  d.DESCRIPTION                                     AS campaign_type,
  d.START_DAY                                       AS start_day,
  d.END_DAY                                         AS end_day,
  d.END_DAY - d.START_DAY                           AS duration_days,

  -- ---- pre 구간 (처치 직전) ----
  d.START_DAY - pre_window_days                     AS pre_start_day,
  d.START_DAY - 1                                   AS pre_end_day,
  d.START_DAY - pre_window_days >= 1                AS has_full_pre,

  -- ---- post 구간 (처치 기간) ----
  d.START_DAY                                       AS post_start_day,
  LEAST(d.END_DAY, max_observed_day)                AS post_end_day,
  LEAST(d.END_DAY, max_observed_day) - d.START_DAY + 1 AS post_observed_days,
  d.END_DAY > max_observed_day                      AS is_post_truncated,

  -- 주차 단위 (mart_household_week 과 조인할 때 사용)
  CAST(CEIL(d.START_DAY / 7) AS INT64)              AS start_week,
  CAST(CEIL(LEAST(d.END_DAY, max_observed_day) / 7) AS INT64) AS end_week

FROM `ybigta-505002.sql_study.campaign_table` t
JOIN `ybigta-505002.sql_study.campaign_desc`  d USING (CAMPAIGN)