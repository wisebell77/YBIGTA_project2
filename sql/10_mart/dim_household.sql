-- =====================================================================
-- 01. dim_household — 가구 마스터 (2,500행)
--
-- 설계 원칙: 거래에 등장하는 2,500가구 전체를 기준으로 삼고,
--            인구통계(801가구, 32%)는 LEFT JOIN으로 붙인다.
--            demographic을 기준 테이블로 쓰면 1,699가구가 조용히 사라진다.
-- =====================================================================
CREATE OR REPLACE TABLE `ybigta-505002.dunnhumby_mart.dim_household`
CLUSTER BY household_key
AS
WITH tx_households AS (
  -- 기준 = 거래 기록이 있는 모든 가구
  SELECT DISTINCT household_key
  FROM `ybigta-505002.sql_study.transaction_data`
),
campaign_agg AS (
  SELECT
    t.household_key,
    COUNT(DISTINCT t.CAMPAIGN)                                        AS n_campaigns,
    COUNTIF(t.DESCRIPTION = 'TypeA')                                  AS n_campaign_a,
    COUNTIF(t.DESCRIPTION = 'TypeB')                                  AS n_campaign_b,
    COUNTIF(t.DESCRIPTION = 'TypeC')                                  AS n_campaign_c,
    MIN(d.START_DAY)                                                  AS first_campaign_day,
    MAX(d.END_DAY)                                                    AS last_campaign_day
  FROM `ybigta-505002.sql_study.campaign_table` t
  LEFT JOIN `ybigta-505002.sql_study.campaign_desc` d USING (CAMPAIGN)
  GROUP BY t.household_key
),
redempt_agg AS (
  SELECT
    household_key,
    COUNT(*)                        AS n_redemptions,
    COUNT(DISTINCT CAMPAIGN)        AS n_campaigns_redeemed,
    MIN(DAY)                        AS first_redempt_day
  FROM `ybigta-505002.sql_study.coupon_redempt`
  GROUP BY household_key
)
SELECT
  h.household_key,

  -- ---- 인구통계 (801가구만 존재, 나머지는 NULL) ----
  d.AGE_DESC                                  AS age_desc,
  d.MARITAL_STATUS_CODE                       AS marital_status_code,
  d.INCOME_DESC                               AS income_desc,
  d.HOMEOWNER_DESC                            AS homeowner_desc,
  d.HH_COMP_DESC                              AS hh_comp_desc,
  d.HOUSEHOLD_SIZE_DESC                       AS household_size_desc,
  d.KID_CATEGORY_DESC                         AS kid_category_desc,
  d.household_key IS NOT NULL                 AS has_demographic,

  -- 인구통계 결측을 명시 레이블로. GROUP BY 시 NULL이 조용히 빠지는 것을 막는다.
  IFNULL(d.INCOME_DESC, 'Unknown')            AS income_desc_filled,
  IFNULL(d.AGE_DESC,    'Unknown')            AS age_desc_filled,

  -- ---- 캠페인 노출 ----
  IFNULL(c.n_campaigns, 0)                    AS n_campaigns,
  IFNULL(c.n_campaign_a, 0)                   AS n_campaign_a,
  IFNULL(c.n_campaign_b, 0)                   AS n_campaign_b,
  IFNULL(c.n_campaign_c, 0)                   AS n_campaign_c,
  c.first_campaign_day,
  c.last_campaign_day,
  IFNULL(c.n_campaigns, 0) > 0                AS is_targeted,

  -- ---- 쿠폰 사용 ----
  IFNULL(r.n_redemptions, 0)                  AS n_redemptions,
  IFNULL(r.n_campaigns_redeemed, 0)           AS n_campaigns_redeemed,
  r.first_redempt_day,
  IFNULL(r.n_redemptions, 0) > 0              AS is_redeemer

FROM tx_households h
LEFT JOIN `ybigta-505002.sql_study.hh_demographic` d USING (household_key)
LEFT JOIN campaign_agg            c USING (household_key)
LEFT JOIN redempt_agg             r USING (household_key);


-- 검증: 2,500행 / has_demographic=TRUE 801 / is_targeted=TRUE 1,584
-- SELECT COUNT(*) n, COUNTIF(has_demographic) n_demo, COUNTIF(is_targeted) n_targeted,
--        COUNTIF(is_redeemer) n_redeemer
-- FROM `ybigta-505002.dunnhumby_mart.dim_household`;
