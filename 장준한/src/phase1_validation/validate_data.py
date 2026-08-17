"""Phase 1 (GATE) — PDF 보고 숫자 재현 검증

목표 숫자 (DA 아이디어.pdf p.8 '할인 밀도'):
    전체 거래 라인            2,595,732
    RETAIL_DISC != 0         1,303,062 (50.20%)
    COUPON_DISC != 0            36,422 (1.40%)
    할인 라인 중위 할인율          24.6%
    딥할인(>=30%) 라인         507,539 (19.70%), 매출 비중 14.90%

정의 (PDF p.10 SQL 파이프라인):
    정가   = SALES_VALUE - RETAIL_DISC - COUPON_DISC - COUPON_MATCH_DISC
    할인율 = -RETAIL_DISC / (SALES_VALUE - RETAIL_DISC)
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT, DUCKDB_PATH, ensure_dirs  # noqa: E402
ensure_dirs()
# ──────────────────────────────────────────────────────────────────────

import duckdb, os

DB = str(DUCKDB_PATH)
con = duckdb.connect(DB, read_only=True)

BASE = """
    SELECT *,
           SALES_VALUE - RETAIL_DISC                                  AS reg_price,
           SALES_VALUE - RETAIL_DISC - COUPON_DISC - COUPON_MATCH_DISC AS full_price,
           CASE WHEN SALES_VALUE - RETAIL_DISC > 0
                THEN -RETAIL_DISC / (SALES_VALUE - RETAIL_DISC) END   AS disc_rate
    FROM transaction_data
"""

def q(sql):
    return con.execute(f"WITH t AS ({BASE}) {sql}").fetchall()


def chk(label, got, target, unit="", tol=None):
    if target is None:
        print(f"  {label:32s} {got:>14,.2f}{unit}")
        return
    ok = abs(got - target) <= (tol if tol is not None else abs(target) * 0.001)
    mark = "PASS" if ok else "FAIL"
    diff = got - target
    print(f"  [{mark}] {label:28s} {got:>14,.2f}{unit}  (목표 {target:,.2f}{unit}, 차이 {diff:+,.2f})")
    return ok


print("=" * 78)
print("PHASE 1 — 사실 재현 게이트")
print("=" * 78)

# ---- 1. 행 수 ----
n_total = q("SELECT COUNT(*) FROM t")[0][0]
print("\n[1] 거래 라인 수")
chk("전체 라인", n_total, 2_595_732, tol=0)

# ---- 2. 할인 라인 밀도 ----
r = q("""
    SELECT COUNT(*) FILTER (WHERE RETAIL_DISC <> 0),
           COUNT(*) FILTER (WHERE COUPON_DISC <> 0),
           COUNT(*) FILTER (WHERE COUPON_MATCH_DISC <> 0),
           COUNT(*) FILTER (WHERE reg_price <= 0),
           COUNT(*) FILTER (WHERE SALES_VALUE <= 0)
    FROM t
""")[0]
n_rd, n_cd, n_cmd, n_badprice, n_badsales = r
print("\n[2] 할인 라인 밀도")
chk("RETAIL_DISC != 0 (건)", n_rd, 1_303_062, tol=0)
chk("RETAIL_DISC != 0 (%)", 100 * n_rd / n_total, 50.20, "%", tol=0.01)
chk("COUPON_DISC != 0 (건)", n_cd, 36_422, tol=0)
chk("COUPON_DISC != 0 (%)", 100 * n_cd / n_total, 1.40, "%", tol=0.01)
chk("COUPON_MATCH_DISC != 0 (건)", n_cmd, None)
chk("정가<=0 인 라인 (건)", n_badprice, None)
chk("SALES_VALUE<=0 인 라인 (건)", n_badsales, None)

# ---- 3. 중위 할인율 ----
r = q("""
    SELECT median(disc_rate), COUNT(*)
    FROM t WHERE RETAIL_DISC <> 0 AND disc_rate IS NOT NULL
""")[0]
print("\n[3] 할인 라인의 중위 할인율")
chk("중위 할인율", 100 * r[0], 24.6, "%", tol=0.05)
chk("  (대상 라인 수)", r[1], None)

# ---- 4. 딥할인 ----
r = q("""
    SELECT COUNT(*) FILTER (WHERE disc_rate >= 0.30),
           SUM(SALES_VALUE) FILTER (WHERE disc_rate >= 0.30),
           SUM(SALES_VALUE),
           COUNT(*) FILTER (WHERE disc_rate IS NOT NULL),
           AVG(disc_rate) FILTER (WHERE disc_rate >= 0.30)
    FROM t
""")[0]
n_deep, sv_deep, sv_all, n_valid, avg_deep = r
print("\n[4] 딥할인 (할인율 >= 30%)")
chk("딥할인 라인 (건)", n_deep, 507_539, tol=0)
print("\n    -- 분모 후보별 비율 (PDF 목표 19.70%) --")
chk("  / 전체 라인", 100 * n_deep / n_total, 19.70, "%", tol=0.02)
chk("  / 정가>0 라인", 100 * n_deep / n_valid, 19.70, "%", tol=0.02)
chk("딥할인 매출 비중", 100 * sv_deep / sv_all, 14.90, "%", tol=0.02)
chk("딥할인 평균 할인율", 100 * avg_deep, 41.2, "%", tol=0.15)

# ---- 5. 정가(<=2%) 그룹 ----
r = q("""
    SELECT COUNT(*) FILTER (WHERE disc_rate <= 0.02),
           COUNT(*) FILTER (WHERE RETAIL_DISC = 0)
    FROM t WHERE disc_rate IS NOT NULL
""")[0]
print("\n[5] 정가 그룹 (보조 설계용)")
chk("할인율 <= 2% 라인", r[0], None)
chk("RETAIL_DISC = 0 라인", r[1], None)

# ---- 6. causal_data 커버리지 ----
r = con.execute("""
    SELECT COUNT(*), COUNT(DISTINCT PRODUCT_ID), COUNT(DISTINCT STORE_ID),
           MIN(WEEK_NO), MAX(WEEK_NO),
           COUNT(*) FILTER (WHERE display = '0' AND mailer = '0')
    FROM causal_data
""").fetchone()
print("\n[6] causal_data 커버리지")
chk("총 행수", r[0], 36_786_524, tol=0)
chk("고유 상품", r[1], 68_377, tol=0)
chk("고유 점포", r[2], 115, tol=0)
chk("display=0 & mailer=0 행", r[5], 0, tol=0)
print(f"     WEEK 범위: {r[3]} ~ {r[4]}")

# 115개 점포의 매출 비중
r = con.execute("""
    SELECT 100.0 * SUM(SALES_VALUE) FILTER (
             WHERE STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data))
           / SUM(SALES_VALUE)
    FROM transaction_data
""").fetchone()[0]
chk("115개 점포 매출 비중", r, 98.49, "%", tol=0.02)

# ---- 7. mailer / display 코드 분포 ----
print("\n[7] mailer 코드 분포 (공식 코드북 대조)")
CODEBOOK = {
    '0': '미노출', 'A': '내지 피처', 'C': '내지 라인아이템', 'D': '1면 피처',
    'F': '뒷면 피처', 'H': '랩 앞면 피처', 'J': '랩 내지 쿠폰',
    'L': '랩 뒷면 피처', 'P': '내지 쿠폰', 'X': '내지 무료', 'Z': '1면/뒷면/랩 무료',
}
rows = con.execute("""
    SELECT mailer, COUNT(*) FROM causal_data GROUP BY 1 ORDER BY 2 DESC
""").fetchall()
tot = sum(c for _, c in rows)
for code, cnt in rows:
    print(f"  {code:2s} {CODEBOOK.get(code,'??? 미정의'):16s} {cnt:>12,}  {100*cnt/tot:5.2f}%")

con.close()
print("\n" + "=" * 78)
