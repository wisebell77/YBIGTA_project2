SELECT m.category, m.n_pairs, m.qty_pct, m.net_pct, m.net_now, m.t_net,
       m.net_later, c.t_cann, m.elasticity
FROM `ybigta-505002.dunnhumby_mart.mart_cat_matrix` m
JOIN `ybigta-505002.dunnhumby_mart.mart_cat_cann` c USING (category)
