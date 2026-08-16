import duckdb
con = duckdb.connect()
con.execute("CREATE VIEW t AS SELECT * FROM read_csv_auto('data/transaction_data.csv')")
con.execute("CREATE VIEW p AS SELECT * FROM read_csv_auto('data/product.csv')")
con.execute("""CREATE TABLE cz AS
  SELECT PRODUCT_ID, STORE_ID, WEEK_NO, max(display) AS display, max(mailer) AS mailer
  FROM read_csv_auto('data/causal_data.csv') GROUP BY 1,2,3""")

print('=== join match rate: transaction lines -> causal_data on (P,S,W) ===')
print(con.sql("""
SELECT count(*) AS lines,
       sum(CASE WHEN cz.PRODUCT_ID IS NOT NULL THEN 1 ELSE 0 END) AS matched,
       round(100.0*sum(CASE WHEN cz.PRODUCT_ID IS NOT NULL THEN 1 ELSE 0 END)/count(*),2) AS match_pct
FROM t LEFT JOIN cz USING (PRODUCT_ID, STORE_ID, WEEK_NO)""").df().to_string())

con.execute("""
CREATE TABLE occ AS
WITH lines AS (
  SELECT t.household_key AS hh, p.COMMODITY_DESC AS cat, t.DAY AS day,
         t.QUANTITY AS qty, t.SALES_VALUE AS sales, t.SALES_VALUE - t.RETAIL_DISC AS reg,
         CASE WHEN cz.mailer IS NOT NULL AND cz.mailer<>'0' THEN 1 ELSE 0 END AS mail
  FROM t JOIN p USING (PRODUCT_ID)
         LEFT JOIN cz USING (PRODUCT_ID, STORE_ID, WEEK_NO)
  WHERE p.COMMODITY_DESC NOT IN ('COUPON','MISC ITEMS')
),
o AS (SELECT hh,cat,day, sum(qty) AS qty, sum(sales) AS sales, sum(reg) AS reg, max(mail) AS exposed,
       CASE WHEN sum(reg)>0 THEN (sum(reg)-sum(sales))/sum(reg) ELSE 0 END AS dr
      FROM lines GROUP BY 1,2,3)
SELECT *, LEAD(day) OVER (PARTITION BY hh,cat ORDER BY day) - day AS gap FROM o
""")
print()
print('=== first stage: does mailer exposure raise realized discount? ===')
print(con.sql("""SELECT exposed, count(*) AS n, round(avg(dr),4) AS mean_disc_rate FROM occ GROUP BY 1 ORDER BY 1""").df().to_string())

con.execute("""CREATE TABLE mpairs AS SELECT hh,cat FROM occ GROUP BY 1,2
  HAVING count(*)>=5 AND sum(exposed)>=2 AND sum(1-exposed)>=2""")
print()
print('=== mailer-design sample ===')
print(con.sql("SELECT count(*) AS pairs, count(DISTINCT hh) AS households, count(DISTINCT cat) AS cats FROM mpairs").df().to_string())

print()
print('=== mailer design headline (within-pair: exposed vs not) ===')
print(con.sql("""
WITH s AS (SELECT o.* FROM occ o JOIN mpairs USING (hh,cat)),
e AS (SELECT hh,cat,avg(gap) AS g,avg(qty) AS q,avg(sales) AS sp FROM s WHERE exposed=1 AND gap IS NOT NULL GROUP BY 1,2),
n AS (SELECT hh,cat,avg(gap) AS g,avg(qty) AS q,avg(sales) AS sp FROM s WHERE exposed=0 AND gap IS NOT NULL GROUP BY 1,2)
SELECT count(*) AS n_pairs,
 round(avg(n.g),3) AS unexp_days, round(avg(e.g),3) AS exp_days, round(avg(e.g-n.g),3) AS diff_days,
 round(avg(e.g-n.g)/(stddev(e.g-n.g)/sqrt(count(*))),2) AS t_days,
 round(avg(n.q),3) AS unexp_qty, round(avg(e.q),3) AS exp_qty, round(100.0*(avg(e.q)-avg(n.q))/avg(n.q),1) AS qty_pct,
 round(avg(n.sp),3) AS unexp_spend, round(avg(e.sp),3) AS exp_spend, round(100.0*(avg(e.sp)-avg(n.sp))/avg(n.sp),1) AS spend_pct
FROM e JOIN n USING (hh,cat)""").df().to_string())
