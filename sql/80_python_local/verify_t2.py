import duckdb
con = duckdb.connect()
con.execute("CREATE VIEW t AS SELECT * FROM read_csv_auto('data/transaction_data.csv')")
con.execute("CREATE VIEW p AS SELECT * FROM read_csv_auto('data/product.csv')")

# 1. discount density at line level
print('=== 1. line-level discount density ===')
print(con.sql("""
WITH x AS (
  SELECT SALES_VALUE, RETAIL_DISC,
         SALES_VALUE - RETAIL_DISC AS reg_price,
         CASE WHEN SALES_VALUE - RETAIL_DISC > 0
              THEN -RETAIL_DISC / (SALES_VALUE - RETAIL_DISC) ELSE 0 END AS disc_rate
  FROM t
)
SELECT count(*) AS lines,
       sum(CASE WHEN disc_rate > 0 THEN 1 ELSE 0 END) AS disc_lines,
       round(100.0*sum(CASE WHEN disc_rate>0 THEN 1 ELSE 0 END)/count(*),2) AS disc_pct,
       round(median(CASE WHEN disc_rate>0 THEN disc_rate END),4) AS med_disc_rate_of_disc,
       sum(CASE WHEN disc_rate>=0.30 THEN 1 ELSE 0 END) AS deep_lines,
       round(100.0*sum(CASE WHEN disc_rate>=0.30 THEN 1 ELSE 0 END)/count(*),2) AS deep_pct,
       round(100.0*sum(CASE WHEN disc_rate>=0.30 THEN SALES_VALUE ELSE 0 END)/sum(SALES_VALUE),2) AS deep_sales_pct
FROM x""").df().to_string())

# 2. build purchase occasions
con.execute("""
CREATE TABLE occ AS
WITH lines AS (
  SELECT t.household_key AS hh, p.COMMODITY_DESC AS cat, t.DAY AS day,
         t.QUANTITY AS qty, t.SALES_VALUE AS sales, t.RETAIL_DISC AS rdisc,
         t.SALES_VALUE - t.RETAIL_DISC AS reg
  FROM t JOIN p USING (PRODUCT_ID)
  WHERE p.COMMODITY_DESC NOT IN ('COUPON','MISC ITEMS')
),
o AS (
  SELECT hh, cat, day,
         sum(qty) AS qty, sum(sales) AS sales, sum(reg) AS reg,
         CASE WHEN sum(reg)>0 THEN (sum(reg)-sum(sales))/sum(reg) ELSE 0 END AS disc_rate
  FROM lines GROUP BY 1,2,3
)
SELECT *,
       CASE WHEN disc_rate>=0.30 THEN 1 ELSE 0 END AS deep,
       CASE WHEN disc_rate<=0.02 THEN 1 ELSE 0 END AS fullp,
       LEAD(day) OVER (PARTITION BY hh,cat ORDER BY day) - day AS gap
FROM o
""")
print()
print('=== 2. purchase occasions ===')
print(con.sql("SELECT count(*) AS occasions, count(DISTINCT hh) AS hh, count(DISTINCT cat) AS cats, sum(deep) AS deep_occ, sum(fullp) AS full_occ, sum(CASE WHEN gap IS NULL THEN 1 ELSE 0 END) AS censored FROM occ").df().to_string())

# 3. sample filter -> pairs
con.execute("""
CREATE TABLE pairs AS
SELECT hh, cat, count(*) AS n_occ, sum(deep) AS n_deep, sum(fullp) AS n_full
FROM occ GROUP BY 1,2
HAVING count(*)>=5 AND sum(deep)>=2 AND sum(fullp)>=2
""")
print()
print('=== 3. main-spec sample (occ>=5 & deep>=2 & fullp>=2) ===')
print(con.sql("SELECT count(*) AS pairs, count(DISTINCT hh) AS households, count(DISTINCT cat) AS categories, sum(n_occ) AS observed_occasions FROM pairs").df().to_string())

# 4. headline within-pair diffs
print()
print('=== 4. within-pair deep vs fullp (paired means) ===')
print(con.sql("""
WITH s AS (SELECT o.* FROM occ o JOIN pairs USING (hh,cat)),
d AS (SELECT hh,cat, avg(gap) AS g, avg(qty) AS q, avg(reg) AS r, avg(sales) AS sp FROM s WHERE deep=1 AND gap IS NOT NULL GROUP BY 1,2),
f AS (SELECT hh,cat, avg(gap) AS g, avg(qty) AS q, avg(reg) AS r, avg(sales) AS sp FROM s WHERE fullp=1 AND gap IS NOT NULL GROUP BY 1,2)
SELECT count(*) AS n_pairs,
       round(avg(f.g),3) AS full_gap_days, round(avg(d.g),3) AS deep_gap_days, round(avg(d.g-f.g),3) AS diff_days,
       round(avg(d.g-f.g)/(stddev(d.g-f.g)/sqrt(count(*))),2) AS t_days,
       round(avg(f.q),3) AS full_qty, round(avg(d.q),3) AS deep_qty, round(avg(d.q-f.q),3) AS diff_qty,
       round(avg(f.r),3) AS full_regamt, round(avg(d.r),3) AS deep_regamt,
       round(avg(f.sp),3) AS full_spend, round(avg(d.sp),3) AS deep_spend, round(avg(d.sp-f.sp),3) AS diff_spend
FROM d JOIN f USING (hh,cat)""").df().to_string())
