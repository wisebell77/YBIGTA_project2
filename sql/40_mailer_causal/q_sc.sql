WITH cd AS (SELECT commodity_desc AS category, ANY_VALUE(department) AS dept
            FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1)
SELECT m.category, cd.dept, m.n_pairs, m.elasticity, m.net_pct, m.net_now, m.t_net, m.disc_trt_pct, m.qty_pct
FROM `ybigta-505002.dunnhumby_mart.mart_cat_matrix` m JOIN cd USING (category)
ORDER BY m.net_pct DESC
