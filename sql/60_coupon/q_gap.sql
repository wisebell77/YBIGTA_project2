-- 공백 A: 쿠폰/캠페인 DiD 설계가 가능한가?
SELECT
  (SELECT COUNT(DISTINCT household_key) FROM `ybigta-505002.sql_study.campaign_table`) AS treated_hh,
  (SELECT COUNT(DISTINCT household_key) FROM `ybigta-505002.dunnhumby_mart.fct_transaction`) AS all_hh,
  (SELECT COUNT(DISTINCT household_key) FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
   WHERE household_key NOT IN (SELECT household_key FROM `ybigta-505002.sql_study.campaign_table`)) AS never_treated,
  (SELECT COUNT(*) FROM `ybigta-505002.sql_study.campaign_desc`) AS campaigns,
  (SELECT MIN(START_DAY) FROM `ybigta-505002.sql_study.campaign_desc`) AS first_start,
  (SELECT MAX(END_DAY) FROM `ybigta-505002.sql_study.campaign_desc`) AS last_end;

-- TypeB/C만 (쿠폰 노출이 완전 관측되는 캠페인)
SELECT d.DESCRIPTION AS type, COUNT(DISTINCT t.household_key) AS hh, COUNT(DISTINCT d.CAMPAIGN) AS n_camp,
  MIN(d.START_DAY) AS min_start, MAX(d.END_DAY) AS max_end
FROM `ybigta-505002.sql_study.campaign_table` t
JOIN `ybigta-505002.sql_study.campaign_desc` d USING (CAMPAIGN, DESCRIPTION)
GROUP BY 1 ORDER BY 1;

-- 첫 캠페인 수신 시점 분포 (staggered DiD 가능성)
SELECT bucket, COUNT(*) AS n_hh FROM (
  SELECT t.household_key, CAST(FLOOR(MIN(d.START_DAY)/100)*100 AS INT64) AS bucket
  FROM `ybigta-505002.sql_study.campaign_table` t
  JOIN `ybigta-505002.sql_study.campaign_desc` d USING (CAMPAIGN)
  GROUP BY 1) GROUP BY 1 ORDER BY 1;
