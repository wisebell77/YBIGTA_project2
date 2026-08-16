import os

def _data(up=6):
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(up):
        c = os.path.join(d, "data")
        if os.path.isfile(os.path.join(c, "transaction_data.csv")):
            return c.replace("\\", "/")
        d = os.path.dirname(d)
    raise SystemExit("data/ 를 찾지 못했습니다. 저장소 최상위의 data/ 에 원본 CSV를 두세요.")

DATA = _data()

import duckdb
con = duckdb.connect()
con.execute(f"CREATE VIEW t AS SELECT * FROM read_csv_auto('{DATA}/transaction_data.csv')")
con.execute(f"CREATE VIEW p AS SELECT * FROM read_csv_auto('{DATA}/product.csv')")
con.execute("""
CREATE TABLE occ AS
WITH lines AS (
  SELECT t.household_key AS hh, p.COMMODITY_DESC AS cat, t.DAY AS day,
         t.QUANTITY AS qty, t.SALES_VALUE AS sales, t.SALES_VALUE - t.RETAIL_DISC AS reg
  FROM t JOIN p USING (PRODUCT_ID)
  WHERE p.COMMODITY_DESC NOT IN ('COUPON','MISC ITEMS')
),
o AS (SELECT hh,cat,day, sum(qty) AS qty, sum(sales) AS sales, sum(reg) AS reg,
       CASE WHEN sum(reg)>0 THEN (sum(reg)-sum(sales))/sum(reg) ELSE 0 END AS dr
      FROM lines GROUP BY 1,2,3)
SELECT *, CASE WHEN dr>=0.30 THEN 1 ELSE 0 END AS deep, CASE WHEN dr<=0.02 THEN 1 ELSE 0 END AS reg_price FROM o
""")
con.execute("""CREATE TABLE pairs AS SELECT hh,cat FROM occ GROUP BY 1,2
HAVING count(*)>=5 AND sum(deep)>=2 AND sum(reg_price)>=2""")
con.execute("CREATE TABLE s AS SELECT o.* FROM occ o JOIN pairs USING (hh,cat)")
# post-window cumulative qty, excluding same day
con.execute("""
CREATE TABLE post AS
SELECT a.hh,a.cat,a.day,a.deep,a.reg_price,
  COALESCE(sum(CASE WHEN b.day> a.day AND b.day<=a.day+28 THEN b.qty END),0) AS q28,
  COALESCE(sum(CASE WHEN b.day> a.day AND b.day<=a.day+56 THEN b.qty END),0) AS q56
FROM s a LEFT JOIN s b ON a.hh=b.hh AND a.cat=b.cat AND b.day>a.day AND b.day<=a.day+56
WHERE a.day <= 711-56
GROUP BY 1,2,3,4,5
""")
print('=== cannibalization test: post-period cumulative quantity (within-pair paired diff) ===')
print(con.sql("""
WITH d AS (SELECT hh,cat,avg(q28) AS a28, avg(q56) AS a56 FROM post WHERE deep=1 GROUP BY 1,2),
     f AS (SELECT hh,cat,avg(q28) AS a28, avg(q56) AS a56 FROM post WHERE reg_price=1 GROUP BY 1,2)
SELECT count(*) AS n_pairs,
  round(avg(f.a28),3) AS full_q28, round(avg(d.a28),3) AS deep_q28, round(avg(d.a28-f.a28),4) AS diff28,
  round(avg(d.a28-f.a28)/(stddev(d.a28-f.a28)/sqrt(count(*))),2) AS t28,
  round(avg(f.a56),3) AS full_q56, round(avg(d.a56),3) AS deep_q56, round(avg(d.a56-f.a56),4) AS diff56,
  round(avg(d.a56-f.a56)/(stddev(d.a56-f.a56)/sqrt(count(*))),2) AS t56
FROM d JOIN f USING (hh,cat)""").df().to_string())
