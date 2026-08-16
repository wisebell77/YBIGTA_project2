WITH q AS (SELECT household_key, q_dd FROM `ybigta-505002.dunnhumby_mart.mart_hh_dd_churn`),
o AS (SELECT o.*, q.q_dd FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o JOIN q USING (household_key)),
p AS (SELECT household_key, category, ANY_VALUE(q_dd) AS q_dd FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key,category)),
e AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) AS q,AVG(net) AS n FROM s WHERE exposed=0 GROUP BY 1,2),
pairdiff AS (SELECT p.q_dd, p.category, e.n-u.n AS dn, u.n AS un
             FROM e JOIN u USING (household_key,category) JOIN p USING (household_key,category)),
cell AS (SELECT q_dd, category, COUNT(*) AS n_pairs, AVG(dn) AS dn, AVG(un) AS un
         FROM pairdiff GROUP BY 1,2 HAVING COUNT(*)>=20),
-- 5개 분위 모두에 존재하는 카테고리만 (공정 비교)
common AS (SELECT category, SUM(n_pairs) AS w FROM cell GROUP BY 1 HAVING COUNT(DISTINCT q_dd)=5)
SELECT c.q_dd,
  COUNT(*) AS n_cats,
  SUM(c.n_pairs) AS pairs,
  -- 원래 방식 (각 분위 자체 구성으로 가중)
  ROUND(100*SUM(c.dn*c.n_pairs)/SUM(c.un*c.n_pairs),2) AS net_pct_own_mix,
  -- 공통 카테고리 가중치로 재가중 (구성 효과 제거)
  ROUND(100*SUM(c.dn*cm.w)/SUM(c.un*cm.w),2)           AS net_pct_common_mix
FROM cell c JOIN common cm USING (category)
GROUP BY c.q_dd ORDER BY c.q_dd
