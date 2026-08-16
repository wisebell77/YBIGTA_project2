SELECT CURR_SIZE_OF_PRODUCT AS sz, COUNT(*) AS n_products
FROM `ybigta-505002.sql_study.product`
GROUP BY 1 ORDER BY n_products DESC LIMIT 40
