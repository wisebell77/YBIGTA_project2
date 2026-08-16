-- 공백 2-b: 카테고리별 halo 분해 (여정 §10.3 확장)
-- q_halo.sql은 전 카테고리를 통합한 값 하나(+$2.05)만 냈다. 이 쿼리는 그것을
-- 카테고리 단위로 쪼개, "농산물은 집객 상품이라 손실을 감수해야 한다"는 반론을
-- 검정 가능한 형태로 만든다.
--
-- focal_eff  = 그 카테고리 자체 순수취액 효과 (기존 판정의 근거)
-- halo_eff   = 같은 날 장바구니의 '나머지' 지출 효과  ← 신규
-- basket_total = focal + halo = 장바구니 전체 효과      ← 의사결정에 쓸 값
--
-- ⚠️ halo는 상한이다. "전단지를 보고 큰 장보기를 계획했다"는 트립 타이밍 내생성을
--    제거하지 못한다. 따라서 절대 수준이 아니라 카테고리·부서 간 상대 비교로 읽을 것.
WITH hhday AS (
  SELECT household_key, day, SUM(net_sales) AS total
  FROM `ybigta-505002.dunnhumby_mart.fct_transaction` GROUP BY 1,2),
dept AS (
  SELECT category, department FROM (
    SELECT commodity_desc AS category, department,
      ROW_NUMBER() OVER (PARTITION BY commodity_desc ORDER BY COUNT(*) DESC) rn
    FROM `ybigta-505002.dunnhumby_mart.dim_product`
    WHERE department IS NOT NULL GROUP BY 1,2)
  WHERE rn=1),
p AS (SELECT household_key, category FROM `ybigta-505002.dunnhumby_mart.mart_occ_all`
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2),
s AS (SELECT o.household_key, o.category, o.day, o.exposed,
        h.total - o.net AS rest_spend, o.net AS focal_spend
      FROM `ybigta-505002.dunnhumby_mart.mart_occ_all` o
      JOIN p USING (household_key, category)
      JOIN hhday h USING (household_key, day)),
e AS (SELECT household_key,category,AVG(rest_spend) AS r,AVG(focal_spend) AS f
      FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(rest_spend) AS r,AVG(focal_spend) AS f
      FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.r-u.r AS dr, e.f-u.f AS df, u.r AS ur, u.f AS uf
      FROM e JOIN u USING (household_key,category))
SELECT d.category, dept.department, COUNT(*) AS n_pairs,
  ROUND(AVG(d.df),3)  AS focal_eff,
  ROUND(AVG(d.df)/(STDDEV(d.df)/SQRT(COUNT(*))),2) AS t_focal,
  ROUND(AVG(d.ur),2)  AS rest_ctrl,
  ROUND(AVG(d.dr),3)  AS halo_eff,
  ROUND(100*AVG(d.dr)/AVG(d.ur),2) AS halo_pct,
  ROUND(AVG(d.dr)/(STDDEV(d.dr)/SQRT(COUNT(*))),2) AS t_halo,
  ROUND(AVG(d.df)+AVG(d.dr),3) AS basket_total,
  ROUND(AVG(d.df+d.dr)/(STDDEV(d.df+d.dr)/SQRT(COUNT(*))),2) AS t_basket
FROM d LEFT JOIN dept ON dept.category = d.category
GROUP BY 1,2 HAVING COUNT(*)>=100
ORDER BY halo_eff DESC;

-- 부서 롤업 (쌍 가중). 핵심 결과: PRODUCE halo가 식품 부서 중 최저.
-- MEAT +3.13(t=5.17) / GROCERY +2.72(t=10.53) / PRODUCE +0.83(t=1.83, 비유의)
