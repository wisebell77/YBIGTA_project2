"""Phase 2 (GATE) — 전단지 ITT 설계의 대조군 존재 확인

핵심 질문: COMMODITY_DESC 307개는 넓다. "그 주 그 점포에 이 카테고리 전단지
상품이 하나도 없는" 경우가 충분히 존재하는가? 없으면 대조군이 소멸하고
(b) ITT 설계는 불가능하며 (c) 연속처치 또는 SUB_COMMODITY 수준으로 내려가야 한다.

처치 정의 (ITT):
    exposed(카테고리, 점포, 주차) = 1  <=>  그 점포-주차에 그 카테고리 소속 상품 중
                                          mailer <> '0' 인 것이 하나라도 있음
표본 한정: causal 115개 점포 x WEEK 9-101, COUPON/MISC ITEMS 제외
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT, DUCKDB_PATH, ensure_dirs  # noqa: E402
ensure_dirs()
# ──────────────────────────────────────────────────────────────────────

import duckdb

DB = str(DUCKDB_PATH)
con = duckdb.connect(DB, read_only=True)
con.execute("SET memory_limit='6GB'")

con.execute("""
CREATE OR REPLACE TEMP VIEW exposure AS
SELECT DISTINCT p.COMMODITY_DESC, c.STORE_ID, c.WEEK_NO
FROM causal_data c JOIN product p USING (PRODUCT_ID)
WHERE c.mailer <> '0'
""")

con.execute("""
CREATE OR REPLACE TEMP VIEW occasion AS
WITH tx AS (
    SELECT t.household_key, p.COMMODITY_DESC, t.DAY, t.WEEK_NO, t.STORE_ID,
           t.SALES_VALUE
    FROM transaction_data t JOIN product p USING (PRODUCT_ID)
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
), occ AS (
    SELECT household_key, COMMODITY_DESC, DAY,
           any_value(WEEK_NO)  AS WEEK_NO,
           max(STORE_ID)       AS STORE_ID,
           sum(SALES_VALUE)    AS sales
    FROM tx GROUP BY household_key, COMMODITY_DESC, DAY
)
SELECT o.*, CASE WHEN e.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END AS exposed
FROM occ o
LEFT JOIN exposure e
  ON o.COMMODITY_DESC = e.COMMODITY_DESC
 AND o.STORE_ID = e.STORE_ID
 AND o.WEEK_NO  = e.WEEK_NO
""")

print("=" * 78)
print("PHASE 2 — 대조군 존재 확인 (전단지 ITT)")
print("=" * 78)

# ---- A. 셀 수준 변동 ----
r = con.execute("""
    SELECT COUNT(*), SUM(exposed), COUNT(DISTINCT COMMODITY_DESC),
           COUNT(DISTINCT household_key), SUM(sales),
           SUM(sales) FILTER (WHERE exposed = 1)
    FROM occasion
""").fetchone()
n_occ, n_exp, n_cat, n_hh, sv, sv_exp = r
print(f"\n[A] 구매기회(occasion) 수준")
print(f"  총 구매기회        {n_occ:>12,}")
print(f"  가구 수            {n_hh:>12,}")
print(f"  카테고리 수        {n_cat:>12,}")
print(f"  노출 구매기회      {n_exp:>12,}  ({100*n_exp/n_occ:5.2f}%)")
print(f"  미노출 구매기회    {n_occ-n_exp:>12,}  ({100*(n_occ-n_exp)/n_occ:5.2f}%)")
print(f"  노출 매출 비중                    {100*sv_exp/sv:5.2f}%")
print(f"\n  >>> 판정: 미노출 비중이 20% 이상이면 ITT 설계 가능")

# ---- B. 카테고리별 노출률 분포 ----
print(f"\n[B] 카테고리별 노출률 분포 (구매기회 >= 1000인 카테고리)")
rows = con.execute("""
    WITH c AS (
      SELECT COMMODITY_DESC, COUNT(*) n, AVG(exposed) rate
      FROM occasion GROUP BY 1 HAVING COUNT(*) >= 1000
    )
    SELECT
      COUNT(*) AS n_cat,
      COUNT(*) FILTER (WHERE rate < 0.05) AS almost_never,
      COUNT(*) FILTER (WHERE rate BETWEEN 0.05 AND 0.95) AS usable,
      COUNT(*) FILTER (WHERE rate > 0.95) AS almost_always,
      median(rate)
    FROM c
""").fetchone()
print(f"  대상 카테고리          {rows[0]:>6,}")
print(f"  노출률 <5%  (변동없음) {rows[1]:>6,}")
print(f"  노출률 5~95% (사용가능){rows[2]:>6,}   <<< 식별 변동의 원천")
print(f"  노출률 >95% (변동없음) {rows[3]:>6,}")
print(f"  중위 노출률            "
      f"{100*rows[4]:>6.1f}%" if rows[4] is not None else "  중위 노출률            (해당 셀 없음)")

# ---- C. 가구-카테고리 쌍 (진짜 식별 변동) ----
print(f"\n[C] 가구-카테고리 쌍 — 표본 필터 통과 여부  (PDF 목표: 45,050쌍)")
rows = con.execute("""
    WITH pair AS (
      SELECT household_key, COMMODITY_DESC,
             COUNT(*) AS n_occ,
             SUM(exposed) AS n_exp,
             COUNT(*) - SUM(exposed) AS n_unexp
      FROM occasion GROUP BY 1, 2
    )
    SELECT
      COUNT(*)                                                     AS all_pairs,
      COUNT(*) FILTER (WHERE n_occ >= 5)                           AS occ5,
      COUNT(*) FILTER (WHERE n_occ >= 5 AND n_exp >= 1 AND n_unexp >= 1) AS f11,
      COUNT(*) FILTER (WHERE n_occ >= 5 AND n_exp >= 2 AND n_unexp >= 2) AS f22,
      SUM(n_occ) FILTER (WHERE n_occ >= 5 AND n_exp >= 2 AND n_unexp >= 2) AS occ_in_f22,
      COUNT(DISTINCT household_key) FILTER (WHERE n_occ >= 5 AND n_exp >= 2 AND n_unexp >= 2) AS hh_f22,
      COUNT(DISTINCT COMMODITY_DESC) FILTER (WHERE n_occ >= 5 AND n_exp >= 2 AND n_unexp >= 2) AS cat_f22
    FROM pair
""").fetchone()
print(f"  전체 쌍                        {rows[0]:>10,}")
print(f"  구매기회 >=5                   {rows[1]:>10,}")
print(f"  >=5 & 노출>=1 & 미노출>=1      {rows[2]:>10,}")
print(f"  >=5 & 노출>=2 & 미노출>=2 (주) {rows[3]:>10,}   <<< 주 설계 표본")
print(f"     그 안의 구매기회             {rows[4]:>10,}   (PDF 목표 872,829)")
print(f"     가구 수 / 카테고리 수        {rows[5]:>10,} / {rows[6]}")

# ---- D. 1단계 강도 검정 (노출 -> 실제 할인율) ----
print(f"\n[D] 1단계 강도 — 노출되면 실제로 할인율이 오르는가 (PDF: 0.117 -> 0.290)")
r = con.execute("""
    WITH tx AS (
        SELECT t.household_key, p.COMMODITY_DESC, t.DAY, t.WEEK_NO, t.STORE_ID,
               t.SALES_VALUE, t.RETAIL_DISC
        FROM transaction_data t JOIN product p USING (PRODUCT_ID)
        WHERE t.WEEK_NO BETWEEN 9 AND 101
          AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
          AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
          AND t.SALES_VALUE > 0
    ), occ AS (
        SELECT household_key, COMMODITY_DESC, DAY,
               any_value(WEEK_NO) WEEK_NO, max(STORE_ID) STORE_ID,
               sum(SALES_VALUE) sv, sum(-RETAIL_DISC) rd
        FROM tx GROUP BY 1,2,3
    )
    SELECT CASE WHEN e.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END AS exposed,
           COUNT(*), AVG(rd / NULLIF(sv + rd, 0))
    FROM occ o LEFT JOIN exposure e
      ON o.COMMODITY_DESC=e.COMMODITY_DESC AND o.STORE_ID=e.STORE_ID AND o.WEEK_NO=e.WEEK_NO
    GROUP BY 1 ORDER BY 1
""").fetchall()
for exposed, n, rate in r:
    lab = "노출" if exposed else "미노출"
    print(f"  {lab:6s} n={n:>10,}   평균 실현 할인율 {100*rate:6.3f}%")

con.close()
print("\n" + "=" * 78)
