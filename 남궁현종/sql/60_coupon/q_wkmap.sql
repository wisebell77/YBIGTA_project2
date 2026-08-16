SELECT week_no, MIN(day) AS dmin, MAX(day) AS dmax
FROM `ybigta-505002.dunnhumby_mart.fct_transaction`
WHERE week_no IN (1,2,32,33,102) GROUP BY 1 ORDER BY 1
