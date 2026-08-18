"""s1b — 56일 payback, 시간통제 스펙 (장준한 M3=⑧ 재현)

naive payback(+0.042, t 19)은 노출 주간이 고수요 시기와 겹치는 시간 교란의 산물이다.
pair(가구×카테고리) FE 에 WEEK, cat×month FE 를 교대 사영(FWL)으로 추가 흡수하면
payback 이 소멸하는지 확인한다. 목표: 장준한 M3 +0.000158 (t 0.16).
출력: ../outputs/s1_payback56_m3.csv
"""
import os, time
import numpy as np, pandas as pd
from standards import connect, OUT

con = connect()
log = []
say = lambda s: log.append(str(s))
t0 = time.time()

# fut 테이블은 s1이 TEMP로 만들었으므로 여기서 재구성 (s1과 동일 정의)
con.execute("""
CREATE OR REPLACE TEMP TABLE hcday AS
SELECT household_key, commodity_desc AS category, day, SUM(qty_w) q
FROM fct
WHERE week_no BETWEEN 9 AND 101
  AND store_id IN (SELECT DISTINCT store_id FROM causal_flag)
  AND commodity_desc <> 'COUPON/MISC ITEMS' AND commodity_desc IS NOT NULL
  AND net_sales > 0
GROUP BY 1,2,3
""")
con.execute("""
CREATE OR REPLACE TEMP VIEW tx1 AS
SELECT household_key, store_id, day, week_no, commodity_desc AS category,
       qty_w, net_sales
FROM fct
WHERE week_no BETWEEN 9 AND 101
  AND store_id IN (SELECT DISTINCT store_id FROM causal_flag)
  AND commodity_desc <> 'COUPON/MISC ITEMS' AND commodity_desc IS NOT NULL
  AND net_sales > 0
""")
con.execute("""
CREATE OR REPLACE TEMP TABLE cats AS
SELECT DISTINCT category FROM (
  SELECT t.household_key, t.category, COUNT(*) n,
         SUM(COALESCE(cf.mailer_any,0)) ne
  FROM (SELECT household_key, store_id, day, week_no, category
        FROM tx1 GROUP BY 1,2,3,4,5) t
  LEFT JOIN cat_flag cf ON cf.commodity_desc=t.category AND cf.store_id=t.store_id
                       AND cf.week_no=t.week_no
  GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(COALESCE(cf.mailer_any,0))>=2
     AND COUNT(*)-SUM(COALESCE(cf.mailer_any,0))>=2)
""")
con.execute("""
CREATE OR REPLACE TEMP TABLE fut AS
WITH trips AS (SELECT DISTINCT household_key, store_id, day, week_no FROM tx1),
grid AS (
  SELECT t.household_key, t.store_id, t.day, t.week_no, c.category,
    COALESCE(cf.mailer_any,0) exp_any, COALESCE(cf.mailer_ad,0) exp_ad,
    COALESCE(cf.mailer_coupon,0) exp_coupon, COALESCE(cf.mailer_free,0) exp_free,
    COALESCE(cf.display_any,0) exp_disp
  FROM trips t CROSS JOIN cats c
  LEFT JOIN cat_flag cf ON cf.commodity_desc=c.category AND cf.store_id=t.store_id
                       AND cf.week_no=t.week_no
  WHERE t.day <= 655)
SELECT g.household_key, g.category, g.day, g.week_no,
  g.exp_any, g.exp_ad, g.exp_coupon, g.exp_free, g.exp_disp,
  COALESCE(SUM(h.q),0) fq56
FROM grid g
LEFT JOIN hcday h
  ON h.household_key=g.household_key AND h.category=g.category
 AND h.day > g.day AND h.day <= g.day + 56
GROUP BY 1,2,3,4,5,6,7,8,9
""")
say(f"[준비] fut {con.execute('SELECT COUNT(*) FROM fut').fetchone()[0]:,}행 [{time.time()-t0:.0f}s]")


def fe_multi(where, treat, n_iter=12):
    """pair + WEEK + cat×month FE 교대 사영 후 FWL 회귀 (hh 클러스터 SE)."""
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE w AS
    SELECT household_key hh,
           household_key::VARCHAR || '|' || category AS pair,
           week_no wk, category || '|' || ((week_no-1)/4)::INT AS cm,
           {treat}::DOUBLE x, fq56::DOUBLE y
    FROM fut {where}
    """)
    for i in range(n_iter):
        for g in ["pair", "wk", "cm"]:
            con.execute(f"""
            CREATE OR REPLACE TEMP TABLE w AS
            SELECT hh, pair, wk, cm,
                   x - AVG(x) OVER (PARTITION BY {g}) AS x,
                   y - AVG(y) OVER (PARTITION BY {g}) AS y
            FROM w
            """)
    r = con.execute("""
    WITH b AS (SELECT SUM(x*y)/SUM(x*x) beta FROM w),
    s AS (SELECT hh, SUM(x*(y - (SELECT beta FROM b)*x)) sc FROM w GROUP BY hh)
    SELECT (SELECT beta FROM b) beta,
           SQRT(SUM(sc*sc)) / (SELECT SUM(x*x) FROM w) se
    FROM s
    """).fetchone()
    return r[0], r[0] / r[1]


rows = []
for label, where, treat in [("legacy(검증)", "", "exp_any"),
                            ("standard", "WHERE exp_coupon=0 AND exp_free=0 AND exp_disp=0", "exp_ad")]:
    b, t = fe_multi(where, treat)
    rows.append(dict(mode=label, beta=b, t=t))
    say(f"[M3:{label}] 56일 future qty {b:+.6f}/기회 (t {t:.2f}) — 장준한 M3 +0.000158 (t 0.16) "
        f"[{time.time()-t0:.0f}s]")
pd.DataFrame(rows).to_csv(os.path.join(OUT, "s1_payback56_m3.csv"), index=False, encoding="utf-8-sig")

con.close()
with open(os.path.join(OUT, "s1b_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s1b DONE")
