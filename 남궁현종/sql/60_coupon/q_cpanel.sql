SELECT COUNT(*) AS rows_, COUNT(DISTINCT household_key) AS hh,
  COUNT(DISTINCT week_no) AS weeks, COUNTIF(net_sales=0 OR net_sales IS NULL) AS zero_rows
FROM `ybigta-505002.dunnhumby_mart.mart_household_week`
