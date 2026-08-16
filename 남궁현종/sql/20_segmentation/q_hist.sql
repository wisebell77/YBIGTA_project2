SELECT household_key, ROUND(dd_value,5) AS dd_value, ROUND(dd_lines,5) AS dd_lines,
       q_value, q_lines, ROUND(net_sales,0) AS net_sales, n_visits
FROM `ybigta-505002.dunnhumby_mart.mart_household_disc_quintile`
ORDER BY dd_value
