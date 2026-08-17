"""Phase 3B-0-3 — shopping opportunity panel 추정
  §2 extensive margin (purchase)
  §3 total quantity (0 포함)
  §4 total spending (0 포함)
  + intensive/extensive 분해
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, sys, time
import numpy as np, pandas as pd

from common.fe_estimator import feols1, _codes

ROOT = str(PROJECT_ROOT)
PANEL = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 100
con = duckdb.connect()
con.execute("SET memory_limit='6GB'")

t0 = time.time()
print("패널 적재 중...")
# ⚠️ 반드시 단일 쿼리로 전 컬럼을 함께 가져올 것.
#    DuckDB의 병렬 parquet 스캔은 쿼리 간 행 순서를 보장하지 않으므로
#    컬럼을 따로 조회하면 배열 정렬이 어긋난다(실제로 이 버그를 겪었음).
base = con.execute(f"""
SELECT p.household_key::INTEGER   AS hh,
       p.STORE_ID::INTEGER        AS store,
       p.WEEK_NO::SMALLINT        AS week,
       p.DAY::INTEGER             AS day,
       c.cat_id::SMALLINT         AS cat,
       p.purchase::TINYINT        AS purchase,
       p.quantity::REAL           AS quantity,
       p.q_w20::REAL              AS q_w20,
       p.sales::REAL              AS sales,
       p.reg_value::REAL          AS reg_value,
       p.exp_any::TINYINT         AS d_any,
       p.exp_feat::TINYINT        AS d_feat
FROM '{PANEL}' p
JOIN (SELECT COMMODITY_DESC,
             row_number() OVER (ORDER BY COMMODITY_DESC) AS cat_id
      FROM (SELECT DISTINCT COMMODITY_DESC FROM '{PANEL}')) c
  ON p.COMMODITY_DESC = c.COMMODITY_DESC
""").fetchnumpy()
n = len(base["hh"])
print(f"  {n:,}행 적재 ({time.time()-t0:.0f}s)")

hh = base["hh"].astype(np.int64)
cat = base["cat"].astype(np.int64)
store = base["store"].astype(np.int64)
week = base["week"].astype(np.int64)
day = base["day"].astype(np.int64)
purchase = base["purchase"].astype(np.float64)
d_any = base["d_any"].astype(np.float64)
d_feat = base["d_feat"].astype(np.float64)
COLS = {k: base[k] for k in ("quantity", "q_w20", "sales", "reg_value")}
del base

# 정합성 자가검증: 구매 없는 행은 quantity/sales 가 0이어야 한다
_bad = int(((purchase == 0) & (COLS["sales"] > 0)).sum())
_bad2 = int(((purchase == 1) & (COLS["sales"] <= 0)).sum())
_q0 = int(((purchase == 1) & (COLS["quantity"] <= 0)).sum())
print(f"  정합성 검사: purchase=0인데 매출>0 {_bad}건 / purchase=1인데 매출<=0 {_bad2}건")
print(f"    (참고) purchase=1인데 수량=0 {_q0}건 — 원자료에 QUANTITY=0 & SALES>0 라인 61건이"
      f" 실재하므로 정상")
assert _bad == 0 and _bad2 == 0, "행 정렬 불일치 — 중단"

print("FE 코드 생성 중...")
cl_hh = _codes(hh)
g_hhcat = _codes(hh * 1000 + cat)
g_storecat = _codes(store * 1000 + cat)
g_week = _codes(week)
print(f"  hh×cat {g_hhcat.max()+1:,} / store×cat {g_storecat.max()+1:,} "
      f"/ week {g_week.max()+1} / 가구 {cl_hh.max()+1:,} ({time.time()-t0:.0f}s)")

MODE = sys.argv[1] if len(sys.argv) > 1 else "m1"
ALL_SPECS = {"m1":    [("M1  hh×cat", [g_hhcat])],
             "multi": [("M2a +store×cat", [g_hhcat, g_storecat]),
                       ("M2b +store×cat +week", [g_hhcat, g_storecat, g_week])]}
SPECS = ALL_SPECS[MODE]
print(f"\n실행 모드: {MODE}  (스펙 {[s[0] for s in SPECS]})")


def getcol(name):
    """단일 적재분에서 꺼낸다 (별도 쿼리 금지 — 행 순서가 어긋남)"""
    return COLS[name].astype(np.float64)


def run(y, ylab, D, dlab, specs=SPECS, two_way=True):
    rows = []
    m0, m1 = y[D == 0].mean(), y[D == 1].mean()
    print(f"\n  ── {ylab}  (처치 {dlab}) ──")
    print(f"     원시 평균: 미노출 {m0:.6f} / 노출 {m1:.6f} "
          f"(차 {m1-m0:+.6f}, {100*(m1-m0)/m0:+.2f}%)")
    print(f"     {'스펙':22s} {'SE방식':14s} {'beta':>12s} {'SE':>10s} {'t':>8s} "
          f"{'p':>8s} {'%p':>9s} {'상대%':>8s} {'N':>12s}")
    for slab, fe in specs:
        for vlab, c2 in ([("hh 1-way", None), ("hh+store×cat", g_storecat)]
                         if two_way else [("hh 1-way", None)]):
            t1 = time.time()
            r = feols1(y, D, fe, cluster=cl_hh, cluster2=c2)
            print(f"     {slab:22s} {vlab:14s} {r['beta']:12.6f} {r['se']:10.6f} "
                  f"{r['t']:8.2f} {r['p']:8.4f} {100*r['beta']:8.4f}p "
                  f"{100*r['beta']/m0:7.2f}% {r['n']:>12,}  ({time.time()-t1:.0f}s,"
                  f"{r['iters']}it)")
            rows.append(dict(outcome=ylab, treat=dlab, spec=slab, vcov=vlab,
                             beta=r["beta"], se=r["se"], t=r["t"], p=r["p"],
                             base=m0, exposed_mean=m1, pct=100*r["beta"]/m0,
                             n=r["n"], iters=r["iters"]))
    return rows


results = []
print(f"\n{BAR}\n§2  EXTENSIVE MARGIN — 카테고리 구매 발생 여부 (LPM)\n{BAR}")
results += run(purchase, "purchase (0/1)", d_any, "mailer_any")

print(f"\n{BAR}\n§3  TOTAL QUANTITY — 0구매 포함\n{BAR}")
q = getcol("quantity")
results += run(q, "quantity (0 포함)", d_any, "mailer_any")
qw = getcol("q_w20")
results += run(qw, "q_w20 (0 포함)", d_any, "mailer_any",
               specs=SPECS[:1], two_way=False)
del qw

print(f"\n{BAR}\n§4  TOTAL SPENDING — 0구매 포함\n{BAR}")
sv = getcol("sales")
results += run(sv, "SALES_VALUE (0 포함)", d_any, "mailer_any")
rv = getcol("reg_value")
results += run(rv, "정가환산 (0 포함)", d_any, "mailer_any")

print(f"\n{BAR}\n§3-b  조건부 효과 (동일 패널, purchase=1 만) — 분해용\n{BAR}")
m = purchase == 1
print(f"  구매 발생 관측치 {m.sum():,}")
for y_, lab in [(q[m], "quantity | 구매"), (sv[m], "SALES_VALUE | 구매"),
                (rv[m], "정가환산 | 구매")]:
    r = feols1(y_, d_any[m], [_codes(g_hhcat[m])], cluster=_codes(cl_hh[m]))
    b0 = y_[d_any[m] == 0].mean()
    print(f"  {lab:22s} M1  beta={r['beta']:9.5f}  t={r['t']:7.2f}  "
          f"대조군평균={b0:8.4f}  {100*r['beta']/b0:+6.2f}%  N={r['n']:,}")
    results.append(dict(outcome=lab, treat="mailer_any", spec="M1 (조건부)",
                        vcov="hh 1-way", beta=r["beta"], se=r["se"], t=r["t"],
                        p=r["p"], base=b0, exposed_mean=np.nan,
                        pct=100*r["beta"]/b0, n=r["n"], iters=r["iters"]))

pd.DataFrame(results).to_csv(
    os.path.join(OUT, f"phase3b0_main_{MODE}.csv"),
    index=False, encoding="utf-8-sig")
print(f"\n{BAR}\n저장: phase3b0_main_{MODE}.csv   총 {time.time()-t0:.0f}s")
