"""카테고리별 halo 분해. q_halo.sql(통합)을 카테고리 단위로 확장."""
import duckdb, os
import pandas as pd

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 120)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.duckdb")
DATA = r"C:\Users\nk233\Desktop\YBIGTA\26-2학기\여름방학\project2\data"
con = duckdb.connect(DB, read_only=False)
con.execute("PRAGMA threads=8")

# 가구-일자 전체 지출 (causal 필터 없이 fct 전체 — q_halo.sql과 동일)
con.execute("""
CREATE OR REPLACE TEMP TABLE pairs AS
  SELECT household_key, category FROM occ_all GROUP BY 1,2
  HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2;
CREATE OR REPLACE TEMP TABLE hhday AS
  SELECT household_key, day, SUM(net_sales) AS total FROM fct GROUP BY 1,2;
CREATE OR REPLACE TEMP TABLE s AS
  SELECT o.household_key, o.category, o.day, o.exposed,
         h.total - o.net AS rest_spend, o.net AS focal_spend
  FROM occ_all o JOIN pairs USING (household_key, category)
                 JOIN hhday h USING (household_key, day);
CREATE OR REPLACE TEMP TABLE d AS
  SELECT e.category, e.r-u.r AS dr, e.f-u.f AS df, u.r AS ur, u.f AS uf
  FROM (SELECT household_key,category,AVG(rest_spend) r,AVG(focal_spend) f
        FROM s WHERE exposed=1 GROUP BY 1,2) e
  JOIN (SELECT household_key,category,AVG(rest_spend) r,AVG(focal_spend) f
        FROM s WHERE exposed=0 GROUP BY 1,2) u USING (household_key,category);
""")

print("=" * 100)
print("[검증] 통합 halo — 문서 기대치: rest +$2.05 (+3.0%, t=10.7), focal +$0.19")
print(con.execute("""
SELECT COUNT(*) n_pairs, ROUND(AVG(ur),2) rest_ctrl, ROUND(AVG(dr),3) rest_diff,
       ROUND(100*AVG(dr)/AVG(ur),2) rest_pct,
       ROUND(AVG(dr)/(STDDEV(dr)/SQRT(COUNT(*))),2) t_rest,
       ROUND(AVG(df),3) focal_diff, ROUND(100*AVG(df)/AVG(uf),2) focal_pct
FROM d""").df().to_string(index=False))

# 카테고리별 분해
cat = con.execute("""
WITH dept AS (
  SELECT commodity_desc AS category, ANY_VALUE(department) AS department
  FROM dim_product WHERE department IS NOT NULL AND department <> '' GROUP BY 1)
SELECT d.category, dept.department, COUNT(*) n_pairs,
  ROUND(AVG(d.df),3) focal_eff,
  ROUND(AVG(d.df)/(STDDEV(d.df)/SQRT(COUNT(*))),2) t_focal,
  ROUND(AVG(d.ur),2) rest_ctrl,
  ROUND(AVG(d.dr),3) halo_eff,
  ROUND(100*AVG(d.dr)/AVG(d.ur),2) halo_pct,
  ROUND(AVG(d.dr)/(STDDEV(d.dr)/SQRT(COUNT(*))),2) t_halo,
  ROUND(AVG(d.df)+AVG(d.dr),3) basket_total,
  ROUND(AVG(d.df+d.dr)/(STDDEV(d.df+d.dr)/SQRT(COUNT(*))),2) t_basket
FROM d LEFT JOIN dept ON dept.category=d.category
GROUP BY 1,2 HAVING COUNT(*)>=100 ORDER BY halo_eff DESC
""").df()
cat.to_csv(os.path.join(os.path.dirname(DB), "halo_by_category.csv"), index=False, encoding="utf-8-sig")

print("\n" + "=" * 100)
print(f"[검증] 카테고리 수 {len(cat)}개, 총 쌍 {cat.n_pairs.sum():,} — 문서 기대치 72개 / 27,625쌍")
print("  focal 효과 대조 (문서: GRAPES -1.07 t=-19.9 / TOMATOES -0.70 / SOFT DRINKS +1.28 t=13.9 / BEEF +1.67):")
print(cat[cat.category.isin(['GRAPES','TOMATOES','ONIONS','APPLES','SOFT DRINKS','BEEF'])]
      [['category','n_pairs','focal_eff','t_focal']].to_string(index=False))

print("\n" + "=" * 100)
print("[신규] 부서별 halo 롤업 (쌍 가중)")
dep = con.execute("""
WITH dept AS (
  SELECT commodity_desc AS category, ANY_VALUE(department) AS department
  FROM dim_product WHERE department IS NOT NULL AND department <> '' GROUP BY 1),
j AS (SELECT d.*, dept.department FROM d LEFT JOIN dept ON dept.category=d.category
      WHERE d.category IN (SELECT category FROM d GROUP BY 1 HAVING COUNT(*)>=100))
SELECT department, COUNT(DISTINCT category) n_cats, COUNT(*) n_pairs,
  ROUND(AVG(df),3) focal_eff, ROUND(AVG(dr),3) halo_eff,
  ROUND(100*AVG(dr)/AVG(ur),2) halo_pct,
  ROUND(AVG(dr)/(STDDEV(dr)/SQRT(COUNT(*))),2) t_halo,
  ROUND(AVG(df)+AVG(dr),3) basket_total,
  ROUND(AVG(df+dr)/(STDDEV(df+dr)/SQRT(COUNT(*))),2) t_basket
FROM j GROUP BY 1 HAVING COUNT(*)>=200 ORDER BY halo_eff DESC
""").df()
print(dep.to_string(index=False))

print("\n" + "=" * 100)
print("[핵심] PRODUCE 카테고리 전체")
print(cat[cat.department == 'PRODUCE'].sort_values('focal_eff').to_string(index=False))

print("\n" + "=" * 100)
print("[참고] halo 상위 10 / 하위 10")
print(cat.head(10).to_string(index=False))
print("...")
print(cat.tail(10).to_string(index=False))
con.close()
