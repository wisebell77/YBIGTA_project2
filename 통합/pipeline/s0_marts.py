"""s0 — 표준 마트 구축. 이후 모든 스테이지가 이 테이블만 사용한다.

  fct          정제 거래 팩트 (표준 정가 공식: gross = sales − retail − coupon_match)
  causal_flag  상품×매장×주 프로모션 플래그 (광고/쿠폰/무료/진열 분리)
  cat_flag     카테고리×매장×주 플래그 (s1 기회 패널용 집계)
  occ          가구×카테고리×일 구매기회 (표준 범위: causal 매장·상품, WEEK 9~101)

검증 기준(스크립트 말미에 자동 확인):
  net 8,057,463 / gross 9,463,374 / retailer_disc 1,405,911 / occ 1,405,014
"""
import time
from standards import (connect, find_data, junk_sql, codes_sql,
                       MAILER_AD, MAILER_COUPON, MAILER_FREE, WEEK_MIN, WEEK_MAX, WINSOR)

DATA = find_data()
con = connect()
t0 = time.time()

con.execute(f"""
CREATE OR REPLACE TABLE causal_flag AS
SELECT PRODUCT_ID AS product_id, STORE_ID AS store_id, WEEK_NO AS week_no,
  MAX(CASE WHEN mailer IN {codes_sql(MAILER_AD)}     THEN 1 ELSE 0 END) AS mailer_ad,
  MAX(CASE WHEN mailer IN {codes_sql(MAILER_COUPON)} THEN 1 ELSE 0 END) AS mailer_coupon,
  MAX(CASE WHEN mailer IN {codes_sql(MAILER_FREE)}   THEN 1 ELSE 0 END) AS mailer_free,
  MAX(CASE WHEN mailer = 'D'                         THEN 1 ELSE 0 END) AS mailer_front,
  MAX(CASE WHEN mailer <> '0'                        THEN 1 ELSE 0 END) AS mailer_any,
  MAX(CASE WHEN display <> '0'                       THEN 1 ELSE 0 END) AS display_any
FROM read_csv_auto('{DATA}/causal_data.csv', types={{'display':'VARCHAR','mailer':'VARCHAR'}})
GROUP BY 1,2,3
""")
print(f"[{time.time()-t0:5.0f}s] causal_flag :", con.execute("SELECT COUNT(*) FROM causal_flag").fetchone()[0])

con.execute(f"""
CREATE OR REPLACE TABLE dim_product AS
SELECT PRODUCT_ID AS product_id, TRIM(DEPARTMENT) AS department,
       TRIM(COMMODITY_DESC) AS commodity_desc
FROM read_csv_auto('{DATA}/product.csv')
""")

con.execute(f"""
CREATE OR REPLACE TABLE fct AS
SELECT t.household_key, t.BASKET_ID AS basket_id, t.DAY AS day, t.WEEK_NO AS week_no,
  t.PRODUCT_ID AS product_id, t.STORE_ID AS store_id, t.QUANTITY AS quantity,
  LEAST(t.QUANTITY, {WINSOR}) AS qty_w,
  t.SALES_VALUE AS net_sales,
  -t.RETAIL_DISC AS retail_disc_amt,
  t.SALES_VALUE - t.RETAIL_DISC - t.COUPON_MATCH_DISC AS gross_sales,
  -t.RETAIL_DISC - t.COUPON_MATCH_DISC AS retailer_disc,
  p.department, p.commodity_desc
FROM read_csv_auto('{DATA}/transaction_data.csv') t
LEFT JOIN dim_product p USING (PRODUCT_ID)
""")
print(f"[{time.time()-t0:5.0f}s] fct         :", con.execute("SELECT COUNT(*) FROM fct").fetchone()[0])

con.execute(f"""
CREATE OR REPLACE TABLE cat_flag AS
SELECT p.commodity_desc, c.store_id, c.week_no,
  MAX(c.mailer_ad) AS mailer_ad, MAX(c.mailer_any) AS mailer_any,
  MAX(c.mailer_coupon) AS mailer_coupon, MAX(c.mailer_free) AS mailer_free,
  MAX(c.display_any) AS display_any, MAX(c.mailer_front) AS mailer_front
FROM causal_flag c JOIN dim_product p USING (product_id)
WHERE {junk_sql('p.commodity_desc')}
GROUP BY 1,2,3
""")

con.execute(f"""
CREATE OR REPLACE TABLE occ AS
WITH cstore AS (SELECT DISTINCT store_id FROM causal_flag),
     cprod  AS (SELECT DISTINCT product_id FROM causal_flag),
lines AS (
  SELECT f.household_key, f.commodity_desc AS category, f.day, f.week_no,
    f.qty_w, f.net_sales, f.gross_sales, f.retailer_disc,
    COALESCE(c.mailer_ad,0) AS mailer_ad, COALESCE(c.mailer_coupon,0) AS mailer_coupon,
    COALESCE(c.mailer_free,0) AS mailer_free, COALESCE(c.display_any,0) AS display_any,
    COALESCE(c.mailer_front,0) AS mailer_front
  FROM fct f
  JOIN cstore USING (store_id) JOIN cprod USING (product_id)
  LEFT JOIN causal_flag c
    ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
  WHERE f.week_no BETWEEN {WEEK_MIN} AND {WEEK_MAX} AND {junk_sql('f.commodity_desc')})
SELECT household_key, category, day, MIN(week_no) AS week_no,
  SUM(qty_w) AS qty, SUM(net_sales) AS net, SUM(gross_sales) AS gross,
  SUM(retailer_disc) AS disc,
  SUM(retailer_disc) / NULLIF(SUM(gross_sales),0) AS disc_rate,
  MAX(mailer_ad) AS exposed, MAX(mailer_front) AS front,
  MAX(mailer_coupon) AS has_coupon, MAX(mailer_free) AS has_free,
  MAX(display_any) AS has_display
FROM lines GROUP BY 1,2,3
""")
print(f"[{time.time()-t0:5.0f}s] occ         :", con.execute("SELECT COUNT(*) FROM occ").fetchone()[0])

# ── 자동 검증 ──────────────────────────────────────────────────────
v = con.execute("""SELECT ROUND(SUM(net_sales)), ROUND(SUM(gross_sales)), ROUND(SUM(retailer_disc))
                   FROM fct""").fetchone()
occ_n = con.execute("SELECT COUNT(*) FROM occ WHERE has_coupon=0 AND has_free=0 AND has_display=0").fetchone()[0]
# 표준 정크 필터는 기존(남궁현종) 3종에 'COUPON/MISC ITEMS'(전영찬)를 합친 것.
# 기존 기준으로 재계산한 값이 1,405,014와 일치해야 하고, 추가 제외분은 그 카테고리뿐이어야 한다.
junk_extra = con.execute("""
  SELECT COUNT(*) FROM (
    SELECT household_key, commodity_desc, day
    FROM fct f
    JOIN (SELECT DISTINCT store_id FROM causal_flag) USING (store_id)
    JOIN (SELECT DISTINCT product_id FROM causal_flag) USING (product_id)
    LEFT JOIN causal_flag c
      ON c.product_id=f.product_id AND c.store_id=f.store_id AND c.week_no=f.week_no
    WHERE f.week_no BETWEEN 9 AND 101 AND f.commodity_desc = 'COUPON/MISC ITEMS'
    GROUP BY 1,2,3
    HAVING MAX(COALESCE(c.mailer_coupon,0))=0 AND MAX(COALESCE(c.mailer_free,0))=0
       AND MAX(COALESCE(c.display_any,0))=0)
""").fetchone()[0]
exp = dict(net=8057463, gross=9463374, disc=1405911, occ_clean_legacy=1405014)
got = dict(net=int(v[0]), gross=int(v[1]), disc=int(v[2]), occ_clean_legacy=occ_n + junk_extra)
print(f"  표준 구매기회(clean) {occ_n:,} = 기존 1,405,014 - 'COUPON/MISC ITEMS' {junk_extra}건 (표준 정크 필터 확대)")
for k in exp:
    flag = "OK " if exp[k] == got[k] else "FAIL"
    print(f"  [{flag}] {k}: {got[k]:,} (기대 {exp[k]:,})")
assert exp == got, "s0 검증 실패"
con.close()
print("s0 DONE")
