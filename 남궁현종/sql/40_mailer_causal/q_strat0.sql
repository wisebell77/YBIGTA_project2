SELECT category, exposed AS mailer, has_display AS disp,
  COUNT(*) AS occasions,
  ROUND(AVG(disc_rate),4) AS disc_rate,
  ROUND(AVG(qty),3) AS qty,
  ROUND(AVG(net),3) AS net
FROM `ybigta-505002.dunnhumby_mart.mart_occ_3cat`
GROUP BY 1,2,3 ORDER BY category, mailer, disp
