-- 검증 1: causal_data의 (점포 × 주차) 커버리지가 완전한가?
SELECT COUNT(DISTINCT store_id) AS stores,
       COUNT(DISTINCT week_no) AS weeks,
       COUNT(DISTINCT store_id)*COUNT(DISTINCT week_no) AS expected_sw,
       COUNT(DISTINCT CONCAT(CAST(store_id AS STRING),'_',CAST(week_no AS STRING))) AS observed_sw,
       ROUND(100*COUNT(DISTINCT CONCAT(CAST(store_id AS STRING),'_',CAST(week_no AS STRING)))
             / (COUNT(DISTINCT store_id)*COUNT(DISTINCT week_no)),2) AS pct_covered
FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean`;

-- 점포별 관측 주차 수 분포 (전부 93주여야 정상)
SELECT n_weeks, COUNT(*) AS n_stores FROM (
  SELECT store_id, COUNT(DISTINCT week_no) AS n_weeks
  FROM `ybigta-505002.dunnhumby_mart.mart_causal_clean` GROUP BY 1)
GROUP BY 1 ORDER BY 1;
