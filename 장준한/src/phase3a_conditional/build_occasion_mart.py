"""Phase 3A-2 — occasion 마트 구축

확정 규칙 (Phase 3A 진단 근거):
  * 분석단위 : household_key × COMMODITY_DESC × DAY
  * 표본     : causal 115점포 × WEEK 9-101, COUPON/MISC ITEMS 제외, SALES_VALUE>0
  * store 배정: 해당 카테고리 지출이 가장 큰 점포 (동점 시 STORE_ID 작은 쪽)
               근거 — 처치가 category×store×week 에서 정의되므로 그 카테고리를
               실제로 구매한 점포의 전단지가 해당 구매의 노출이다.
  * 처치 A  mailer_any     : mailer <> '0'
  * 처치 B  mailer_feature : mailer IN ('A','C','D','F','H','L')  (쿠폰 J,P / 무료 X,Z 제외)
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

con = duckdb.connect(DB)
con.execute("SET memory_limit='6GB'")
con.execute("SET preserve_insertion_order=false")

FEATURE_CODES = "('A','C','D','F','H','L')"

con.execute(f"""
COPY (
WITH tx AS (
    SELECT t.household_key, t.DAY, t.WEEK_NO, t.STORE_ID, t.PRODUCT_ID,
           p.COMMODITY_DESC, t.QUANTITY, t.SALES_VALUE, t.RETAIL_DISC,
           t.COUPON_DISC, t.COUPON_MATCH_DISC
    FROM transaction_data t JOIN product p ON t.PRODUCT_ID = p.PRODUCT_ID
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
),
-- 규칙B: occasion 내 카테고리 지출 최대 점포
store_pick AS (
    SELECT household_key, COMMODITY_DESC, DAY, STORE_ID,
           ROW_NUMBER() OVER (PARTITION BY household_key, COMMODITY_DESC, DAY
                              ORDER BY SUM(SALES_VALUE) DESC, STORE_ID) rn
    FROM tx GROUP BY 1,2,3,4
),
occ AS (
    SELECT t.household_key, t.COMMODITY_DESC, t.DAY,
           any_value(t.WEEK_NO)                            AS WEEK_NO,
           SUM(t.QUANTITY)                                 AS q_raw,
           SUM(LEAST(t.QUANTITY, 20))                      AS q_w20,
           SUM(t.SALES_VALUE)                              AS sales,
           SUM(t.SALES_VALUE - t.RETAIL_DISC
               - t.COUPON_DISC - t.COUPON_MATCH_DISC)      AS reg_value,
           SUM(-t.RETAIL_DISC)                             AS disc_amt,
           COUNT(DISTINCT t.PRODUCT_ID)                    AS n_prod,
           COUNT(DISTINCT t.STORE_ID)                      AS n_store
    FROM tx t GROUP BY 1,2,3
),
occ_s AS (
    SELECT o.*, sp.STORE_ID
    FROM occ o JOIN store_pick sp
      ON o.household_key=sp.household_key AND o.COMMODITY_DESC=sp.COMMODITY_DESC
     AND o.DAY=sp.DAY AND sp.rn=1
),
-- 노출 맵
exp_any AS (
    SELECT DISTINCT p.COMMODITY_DESC, c.STORE_ID, c.WEEK_NO
    FROM causal_data c JOIN product p ON c.PRODUCT_ID=p.PRODUCT_ID
    WHERE c.mailer <> '0'
),
exp_feat AS (
    SELECT DISTINCT p.COMMODITY_DESC, c.STORE_ID, c.WEEK_NO
    FROM causal_data c JOIN product p ON c.PRODUCT_ID=p.PRODUCT_ID
    WHERE c.mailer IN {FEATURE_CODES}
),
tagged AS (
    SELECT o.*,
           CASE WHEN ea.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END AS exp_any,
           CASE WHEN ef.COMMODITY_DESC IS NULL THEN 0 ELSE 1 END AS exp_feat
    FROM occ_s o
    LEFT JOIN exp_any  ea ON o.COMMODITY_DESC=ea.COMMODITY_DESC
                         AND o.STORE_ID=ea.STORE_ID AND o.WEEK_NO=ea.WEEK_NO
    LEFT JOIN exp_feat ef ON o.COMMODITY_DESC=ef.COMMODITY_DESC
                         AND o.STORE_ID=ef.STORE_ID AND o.WEEK_NO=ef.WEEK_NO
),
-- 가구별 방문 순번 (장보기 주기 통제용)
visits AS (
    SELECT household_key, DAY,
           DENSE_RANK() OVER (PARTITION BY household_key ORDER BY DAY) AS visit_no
    FROM (SELECT DISTINCT household_key, DAY FROM tx)
),
withv AS (
    SELECT t.*, v.visit_no FROM tagged t JOIN visits v
      ON t.household_key=v.household_key AND t.DAY=v.DAY
)
SELECT *,
       LEAD(DAY)      OVER w - DAY      AS gap_days,
       LEAD(visit_no) OVER w - visit_no AS gap_visits
FROM withv
WINDOW w AS (PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY)
) TO '{MART}' (FORMAT PARQUET, COMPRESSION ZSTD)
""")

n = con.execute(f"SELECT COUNT(*) FROM '{MART}'").fetchone()[0]
print(f"occasion 마트 생성: {n:,}행 -> {MART}")
print(f"  파일 크기 {os.path.getsize(MART)/1e6:.1f}MB")

r = con.execute(f"""
SELECT COUNT(*), SUM(exp_any), SUM(exp_feat),
       COUNT(*) FILTER (WHERE gap_days IS NULL),
       COUNT(DISTINCT household_key), COUNT(DISTINCT COMMODITY_DESC)
FROM '{MART}'
""").fetchone()
print(f"  노출(any) {r[1]:,} ({100*r[1]/r[0]:.2f}%) / 노출(feature) {r[2]:,} ({100*r[2]/r[0]:.2f}%)")
print(f"  우측중도절단(gap NULL) {r[3]:,} ({100*r[3]/r[0]:.2f}%)")
print(f"  가구 {r[4]:,} / 카테고리 {r[5]}")
con.close()
