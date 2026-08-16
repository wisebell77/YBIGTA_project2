SELECT category, n_pairs, disc_ctrl_pct, disc_trt_pct, qty_pct, net_pct, net_now, t_net,
       net_later, net_total, elasticity, incrementality_pct
FROM `ybigta-505002.dunnhumby_mart.mart_cat_matrix`
ORDER BY net_total DESC
