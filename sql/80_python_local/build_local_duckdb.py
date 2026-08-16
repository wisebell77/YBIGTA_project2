"""BigQuery 마트를 로컬 DuckDB로 재구축.
sql/10_mart/fct_transaction.sql, dim_product.sql, 40_mailer_causal/q_causal_clean.sql,
q_occ_all.sql 의 정의를 그대로 옮긴 것. 검증 목표는 문서에 기록된 BigQuery 결과.
"""
import duckdb, os, time

DATA = r"C:\Users\nk233\Desktop\YBIGTA\26-2학기\여름방학\project2\data"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.duckdb")

con = duckdb.connect(DB)
con.execute("PRAGMA threads=8")

t0 = time.time()
print("causal_data.csv 헤더:", flush=True)
print(con.execute(
    f"SELECT * FROM read_csv_auto('{DATA}/causal_data.csv') LIMIT 1").df().columns.tolist(), flush=True)

# ---- mart_causal_clean (q_causal_clean.sql) ----
con.execute(f"""
CREATE OR REPLACE TABLE causal_clean AS
SELECT PRODUCT_ID AS product_id, STORE_ID AS store_id, WEEK_NO AS week_no,
  MAX(CASE WHEN mailer IN ('A','C','D','F','H','L') THEN 1 ELSE 0 END) AS mailer_ad,
  MAX(CASE WHEN mailer IN ('J','P')                 THEN 1 ELSE 0 END) AS mailer_coupon,
  MAX(CASE WHEN mailer IN ('X','Z')                 THEN 1 ELSE 0 END) AS mailer_free,
  MAX(CASE WHEN mailer = 'D'                        THEN 1 ELSE 0 END) AS mailer_frontpage,
  MAX(CASE WHEN display <> '0'                      THEN 1 ELSE 0 END) AS display_any
FROM read_csv_auto('{DATA}/causal_data.csv', types={{'display':'VARCHAR','mailer':'VARCHAR'}})
GROUP BY 1,2,3
""")
print(f"[{time.time()-t0:.0f}s] causal_clean:",
      con.execute("SELECT COUNT(*) FROM causal_clean").fetchone()[0], "cells", flush=True)

# ---- dim_product (TRIM 적용) ----
con.execute(f"""
CREATE OR REPLACE TABLE dim_product AS
SELECT PRODUCT_ID AS product_id, TRIM(DEPARTMENT) AS department,
       TRIM(COMMODITY_DESC) AS commodity_desc
FROM read_csv_auto('{DATA}/product.csv')
""")

# ---- fct_transaction (금액 분해) ----
con.execute(f"""
CREATE OR REPLACE TABLE fct AS
SELECT t.household_key, t.DAY AS day, t.WEEK_NO AS week_no,
  t.PRODUCT_ID AS product_id, t.STORE_ID AS store_id, t.QUANTITY AS quantity,
  t.SALES_VALUE AS net_sales,
  t.SALES_VALUE - t.RETAIL_DISC - t.COUPON_MATCH_DISC AS gross_sales,
  -t.RETAIL_DISC - t.COUPON_MATCH_DISC AS retailer_funded_disc,
  p.department, p.commodity_desc
FROM read_csv_auto('{DATA}/transaction_data.csv') t
LEFT JOIN dim_product p USING (PRODUCT_ID)
""")
print(f"[{time.time()-t0:.0f}s] fct:", con.execute("SELECT COUNT(*) FROM fct").fetchone()[0], flush=True)
print("  검증(문서 기대치 net 8,057,463 / gross 9,463,374 / disc 1,405,911):")
print(con.execute("""SELECT ROUND(SUM(net_sales)) net, ROUND(SUM(gross_sales)) gross,
                     ROUND(SUM(retailer_funded_disc)) disc FROM fct""").df().to_string(index=False), flush=True)

# ---- mart_occ_all (q_occ_all.sql) ----
con.execute("""
CREATE OR REPLACE TABLE occ_all AS
WITH cstore AS (SELECT DISTINCT store_id FROM causal_clean),
     cprod  AS (SELECT DISTINCT product_id FROM causal_clean),
lines AS (
  SELECT f.household_key, f.commodity_desc AS category, f.day,
    LEAST(f.quantity,20) AS qty_w, f.net_sales, f.gross_sales, f.retailer_funded_disc,
    COALESCE(c.mailer_ad,0) AS mailer_ad, COALESCE(c.mailer_coupon,0) AS mailer_coupon,
    COALESCE(c.mailer_free,0) AS mailer_free, COALESCE(c.display_any,0) AS display_any
  FROM fct f
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN causal_clean c
    ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN 9 AND 101
    AND f.commodity_desc NOT IN ('COUPON','MISC ITEMS','NO COMMODITY DESCRIPTION')),
occ AS (
  SELECT household_key, category, day,
    SUM(qty_w) AS qty, SUM(net_sales) AS net, SUM(gross_sales) AS gross,
    SUM(retailer_funded_disc) AS disc,
    MAX(mailer_ad) AS exposed, MAX(mailer_coupon) AS has_coupon,
    MAX(mailer_free) AS has_free, MAX(display_any) AS has_display
  FROM lines GROUP BY 1,2,3)
SELECT *, disc/NULLIF(gross,0) AS disc_rate
FROM occ WHERE has_coupon=0 AND has_free=0 AND has_display=0
""")
print(f"[{time.time()-t0:.0f}s] occ_all (문서 기대치 1,405,014건 / 290 카테고리):")
print(con.execute("""SELECT COUNT(*) occasions, COUNT(DISTINCT category) cats,
                     COUNT(DISTINCT household_key) hh, ROUND(100*AVG(exposed),1) pct_exposed
                     FROM occ_all""").df().to_string(index=False), flush=True)
con.close()
print("DONE")
