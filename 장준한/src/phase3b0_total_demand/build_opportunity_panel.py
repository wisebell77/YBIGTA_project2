"""Phase 3B-0-1 — shopping opportunity panel 생성

단위: household_key × STORE_ID × DAY × COMMODITY_DESC
  * trip = 실제 장보기 방문 (household × store × day). 방문하지 않은 날은 만들지 않는다.
  * 주 설계 222개 COMMODITY_DESC 와 CROSS JOIN
  * 그 trip에서 그 카테고리 구매가 없으면 purchase=0, quantity=0, sales=0, reg_value=0
  * exposure 는 기존과 동일하게 category × store × week 수준에서 부여
표본: causal 115점포 × WEEK 9-101, COUPON/MISC ITEMS 제외, SALES_VALUE>0
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os

ROOT = str(PROJECT_ROOT)
DB = os.path.join(ROOT, "data", "interim", "dunn.duckdb")
MART = os.path.join(ROOT, "data", "marts", "occasion.parquet").replace("\\", "/")
OUT = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")

con = duckdb.connect(DB)
con.execute("SET memory_limit='8GB'")
con.execute("SET preserve_insertion_order=false")
FEAT = "('A','C','D','F','H','L')"

con.execute(f"""
CREATE OR REPLACE TEMP VIEW tx AS
SELECT t.household_key, t.DAY, t.WEEK_NO, t.STORE_ID, p.COMMODITY_DESC,
       t.QUANTITY, t.SALES_VALUE, t.RETAIL_DISC, t.COUPON_DISC, t.COUPON_MATCH_DISC
FROM transaction_data t JOIN product p ON t.PRODUCT_ID = p.PRODUCT_ID
WHERE t.WEEK_NO BETWEEN 9 AND 101
  AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
  AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
  AND t.SALES_VALUE > 0
""")

# 주 설계 222개 카테고리 (Phase 3A 표본)
con.execute(f"""
CREATE OR REPLACE TEMP VIEW cats AS
WITH o AS (SELECT * FROM '{MART}'),
pair AS (SELECT household_key, COMMODITY_DESC, COUNT(*) n, SUM(exp_any) ne,
                COUNT(*)-SUM(exp_any) nu FROM o GROUP BY 1,2)
SELECT DISTINCT COMMODITY_DESC FROM pair WHERE n>=5 AND ne>=2 AND nu>=2
""")

# Phase 3A 주 표본 pair (비교용 플래그)
con.execute(f"""
CREATE OR REPLACE TEMP VIEW main_pair AS
WITH o AS (SELECT * FROM '{MART}'),
pair AS (SELECT household_key, COMMODITY_DESC, COUNT(*) n, SUM(exp_any) ne,
                COUNT(*)-SUM(exp_any) nu FROM o GROUP BY 1,2)
SELECT household_key, COMMODITY_DESC FROM pair WHERE n>=5 AND ne>=2 AND nu>=2
""")

print("패널 생성 중...")
con.execute(f"""
COPY (
WITH trips AS (
    SELECT DISTINCT household_key, STORE_ID, DAY, WEEK_NO FROM tx
),
buy AS (
    SELECT household_key, STORE_ID, DAY, COMMODITY_DESC,
           SUM(QUANTITY)                                            AS quantity,
           SUM(LEAST(QUANTITY,20))                                  AS q_w20,
           SUM(SALES_VALUE)                                         AS sales,
           SUM(SALES_VALUE-RETAIL_DISC-COUPON_DISC-COUPON_MATCH_DISC) AS reg_value
    FROM tx GROUP BY 1,2,3,4
),
exp_any AS (
    SELECT DISTINCT p.COMMODITY_DESC, c.STORE_ID, c.WEEK_NO
    FROM causal_data c JOIN product p ON c.PRODUCT_ID=p.PRODUCT_ID
    WHERE c.mailer <> '0'
),
exp_feat AS (
    SELECT DISTINCT p.COMMODITY_DESC, c.STORE_ID, c.WEEK_NO
    FROM causal_data c JOIN product p ON c.PRODUCT_ID=p.PRODUCT_ID
    WHERE c.mailer IN {FEAT}
),
grid AS (
    SELECT t.household_key, t.STORE_ID, t.DAY, t.WEEK_NO, c.COMMODITY_DESC
    FROM trips t CROSS JOIN cats c
)
SELECT g.household_key, g.STORE_ID, g.DAY, g.WEEK_NO, g.COMMODITY_DESC,
       CASE WHEN b.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END      AS purchase,
       COALESCE(b.quantity, 0)                                    AS quantity,
       COALESCE(b.q_w20, 0)                                       AS q_w20,
       COALESCE(b.sales, 0)                                       AS sales,
       COALESCE(b.reg_value, 0)                                   AS reg_value,
       CASE WHEN ea.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END      AS exp_any,
       CASE WHEN ef.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END      AS exp_feat,
       CASE WHEN mp.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END      AS in_main_pair
FROM grid g
LEFT JOIN buy b       ON g.household_key=b.household_key AND g.STORE_ID=b.STORE_ID
                     AND g.DAY=b.DAY AND g.COMMODITY_DESC=b.COMMODITY_DESC
LEFT JOIN exp_any ea  ON g.COMMODITY_DESC=ea.COMMODITY_DESC
                     AND g.STORE_ID=ea.STORE_ID AND g.WEEK_NO=ea.WEEK_NO
LEFT JOIN exp_feat ef ON g.COMMODITY_DESC=ef.COMMODITY_DESC
                     AND g.STORE_ID=ef.STORE_ID AND g.WEEK_NO=ef.WEEK_NO
LEFT JOIN main_pair mp ON g.household_key=mp.household_key
                     AND g.COMMODITY_DESC=mp.COMMODITY_DESC
) TO '{OUT}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 1000000)
""")
print(f"생성 완료 -> {OUT}  ({os.path.getsize(OUT)/1e6:.0f}MB)")

print("\n" + "=" * 84)
print("shopping opportunity panel 요약")
print("=" * 84)
r = con.execute(f"""
SELECT COUNT(*)                                          AS n,
       COUNT(DISTINCT household_key)                     AS hh,
       COUNT(DISTINCT (household_key, STORE_ID, DAY))    AS trips,
       COUNT(DISTINCT COMMODITY_DESC)                    AS cats,
       AVG(purchase)                                     AS buy_rate,
       AVG(exp_any)                                      AS exp_rate,
       AVG(exp_feat)                                     AS expf_rate,
       SUM(quantity)                                     AS q,
       SUM(sales)                                        AS sv,
       AVG(in_main_pair)                                 AS mainshare
FROM '{OUT}'
""").fetchone()
print(f"  N (opportunity)        {r[0]:>14,}")
print(f"  가구                    {r[1]:>14,}")
print(f"  trip                   {r[2]:>14,}")
print(f"  카테고리                 {r[3]:>14,}")
print(f"  구매 발생률(purchase=1)  {100*r[4]:>13.3f}%   -> 0구매 비율 {100*(1-r[4]):.3f}%")
print(f"  노출률 exp_any          {100*r[5]:>13.3f}%")
print(f"  노출률 exp_feat         {100*r[6]:>13.3f}%")
print(f"  총수량 / 총매출          {r[7]:>14,.0f} / ${r[8]:,.0f}")
print(f"  Phase 3A 주 표본 pair 비중 {100*r[9]:>10.3f}%")

# active pair (해당 가구가 그 카테고리를 1회 이상 구매) 규모
r2 = con.execute(f"""
WITH p AS (SELECT household_key, COMMODITY_DESC, SUM(purchase) nb, COUNT(*) n
           FROM '{OUT}' GROUP BY 1,2)
SELECT COUNT(*), COUNT(*) FILTER (WHERE nb>0), SUM(n), SUM(n) FILTER (WHERE nb>0)
FROM p
""").fetchone()
print(f"\n  household-category pair 총 {r2[0]:,} 중 구매경험 있는 pair {r2[1]:,} "
      f"({100*r2[1]/r2[0]:.1f}%)")
print(f"  -> active 패널 행수 {r2[3]:,} ({100*r2[3]/r2[2]:.1f}%)")
con.close()
