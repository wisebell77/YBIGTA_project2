"""Phase 3B-0-4 — §5 mailer 정의 강건성 · §6 시간 교란 통제 진단

§5-A  mailer_feature (A,C,D,F,H,L)  — J,P,X,Z 셀이 대조군으로 섞이는 정의
§5-B  feature-only clean sample     — J,P,X,Z만 있는 셀을 표본에서 제거한 뒤
                                      A,C,D,F,H,L 노출 vs 진짜 mailer=0 비교
§6    시간 통제: WEEK FE / store×cat FE / category 선형추세 / cat×month FE
      처치 변동을 90% 이상 흡수하는 통제는 주 스펙 불가로 기록만 한다.
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

from common.fe_estimator import feols1, _codes, _demean, absorb_share

ROOT = str(PROJECT_ROOT)
PANEL = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 100
con = duckdb.connect()
con.execute("SET memory_limit='6GB'")

t0 = time.time()
b = con.execute(f"""
SELECT household_key::INTEGER AS hh, STORE_ID::INTEGER AS store,
       WEEK_NO::SMALLINT AS week, DAY::INTEGER AS day,
       dense_rank() OVER (ORDER BY COMMODITY_DESC)::SMALLINT AS cat,
       purchase::TINYINT AS purchase, quantity::REAL AS quantity,
       sales::REAL AS sales, exp_any::TINYINT AS d_any, exp_feat::TINYINT AS d_feat
FROM '{PANEL}'
""").fetchnumpy()
print(f"적재 {len(b['hh']):,}행 ({time.time()-t0:.0f}s)")

hh = b["hh"].astype(np.int64); cat = b["cat"].astype(np.int64)
store = b["store"].astype(np.int64); week = b["week"].astype(np.int64)
day = b["day"].astype(np.float64)
purchase = b["purchase"].astype(np.float64)
quantity = b["quantity"].astype(np.float64)
sales = b["sales"].astype(np.float64)
d_any = b["d_any"].astype(np.float64); d_feat = b["d_feat"].astype(np.float64)
del b

cl_hh = _codes(hh)
g_hhcat = _codes(hh * 1000 + cat)
g_storecat = _codes(store * 1000 + cat)
g_week = _codes(week)
month = (day // 30).astype(np.int64)
g_catmonth = _codes(cat * 1000 + month)
g_catquarter = _codes(cat * 1000 + (day // 91).astype(np.int64))
jpxz_only = (d_any == 1) & (d_feat == 0)
print(f"코드 생성 완료 ({time.time()-t0:.0f}s).  J,P,X,Z-only 관측치 {jpxz_only.sum():,} "
      f"({100*jpxz_only.mean():.3f}%)")

OUTS = [(purchase, "purchase"), (quantity, "quantity"), (sales, "SALES_VALUE")]
rows = []

# ══════════════════════════════════════════════════════════════════
print(f"\n{BAR}\n§5  mailer 정의 강건성 (M1 hh×cat, household cluster)\n{BAR}")
print(f"{'결과변수':12s} {'정의':34s} {'beta':>12s} {'SE':>10s} {'t':>8s} "
      f"{'대조평균':>10s} {'상대%':>8s} {'N':>12s}")

clean = ~jpxz_only
for y, ylab in OUTS:
    specs = [
        ("주  mailer_any",                      d_any, None),
        ("A   mailer_feature (JPXZ→대조군)",     d_feat, None),
        ("B   feature-only clean sample",       d_feat, clean),
    ]
    for dlab, D, msk in specs:
        if msk is None:
            yy, DD, gg, cc = y, D, g_hhcat, cl_hh
        else:
            yy, DD = y[msk], D[msk]
            gg, cc = _codes(g_hhcat[msk]), _codes(cl_hh[msk])
        r = feols1(yy, DD, [gg], cluster=cc)
        m0 = yy[DD == 0].mean()
        print(f"{ylab:12s} {dlab:34s} {r['beta']:12.6f} {r['se']:10.6f} "
              f"{r['t']:8.2f} {m0:10.5f} {100*r['beta']/m0:7.2f}% {r['n']:>12,}")
        rows.append(dict(section="§5", outcome=ylab, spec=dlab, beta=r["beta"],
                         se=r["se"], t=r["t"], p=r["p"], base=m0,
                         pct=100*r["beta"]/m0, n=r["n"]))

# ══════════════════════════════════════════════════════════════════
print(f"\n{BAR}\n§6  시간 교란 통제 — 처치 변동 흡수 진단\n{BAR}")
print("  (처치 변동을 90% 이상 흡수하면 주 스펙 채택 불가)")
CONTROLS = [
    ("① hh×cat (기준)",                [g_hhcat]),
    ("② + WEEK_NO",                    [g_hhcat, g_week]),
    ("③ + store×cat",                  [g_hhcat, g_storecat]),
    ("④ + store×cat + WEEK_NO",        [g_hhcat, g_storecat, g_week]),
    ("⑤ + cat×month(30일)",            [g_hhcat, g_catmonth]),
    ("⑥ + cat×quarter(91일)",          [g_hhcat, g_catquarter]),
]
print(f"\n  {'통제':30s} {'FE 그룹수':>12s} {'처치변동 흡수율':>14s} {'잔여 SD':>10s} {'판정':>10s}")
absorb = {}
for lab, fe in CONTROLS:
    t1 = time.time()
    sh, sd = absorb_share(d_any, fe)
    absorb[lab] = sh
    verdict = "식별불가" if sh >= 0.90 else "사용가능"
    ng = sum(int(g.max()) + 1 for g in fe)
    print(f"  {lab:30s} {ng:>12,} {100*sh:13.2f}% {sd:10.5f} {verdict:>10s}"
          f"  ({time.time()-t1:.0f}s)")
    rows.append(dict(section="§6-absorb", outcome="-", spec=lab, beta=np.nan,
                     se=np.nan, t=np.nan, p=np.nan, base=sh, pct=100*sh, n=0))

# category별 선형추세 진단 (별도 — FE가 아니라 추세 부분화)
def partial_trend(vec, catcodes, t):
    """카테고리별 선형추세(절편+기울기) 제거"""
    x = vec.astype(np.float64).copy()
    cnt = np.bincount(catcodes).astype(np.float64)
    tm = np.bincount(catcodes, weights=t) / cnt
    xm = np.bincount(catcodes, weights=x) / cnt
    td = t - tm[catcodes]
    xd = x - xm[catcodes]
    num = np.bincount(catcodes, weights=td * xd)
    den = np.bincount(catcodes, weights=td * td)
    slope = np.where(den > 0, num / np.maximum(den, 1e-12), 0.0)
    return xd - slope[catcodes] * td

d_tr = partial_trend(d_any, cat, day)
sh_tr = 1 - np.var(d_tr) / np.var(d_any)
print(f"  {'⑦ cat별 선형 time trend':30s} {'-':>12s} {100*sh_tr:13.2f}% "
      f"{d_tr.std():10.5f} {'사용가능' if sh_tr < 0.9 else '식별불가':>10s}")
rows.append(dict(section="§6-absorb", outcome="-", spec="⑦ cat별 선형 time trend",
                 beta=np.nan, se=np.nan, t=np.nan, p=np.nan, base=sh_tr,
                 pct=100*sh_tr, n=0))

print(f"\n  --- 흡수율 90% 미만 통제에서 beta 재추정 (purchase) ---")
print(f"  {'통제':30s} {'beta':>12s} {'SE':>10s} {'t':>8s} {'상대%':>9s} {'N':>12s}")
m0 = purchase[d_any == 0].mean()
for lab, fe in CONTROLS:
    if absorb[lab] >= 0.90:
        print(f"  {lab:30s}  (흡수율 {100*absorb[lab]:.1f}% — 추정 생략)")
        continue
    t1 = time.time()
    try:
        r = feols1(purchase, d_any, fe, cluster=cl_hh)
        print(f"  {lab:30s} {r['beta']:12.6f} {r['se']:10.6f} {r['t']:8.2f} "
              f"{100*r['beta']/m0:8.2f}% {r['n']:>12,}  ({time.time()-t1:.0f}s,{r['iters']}it)")
        rows.append(dict(section="§6-beta", outcome="purchase", spec=lab,
                         beta=r["beta"], se=r["se"], t=r["t"], p=r["p"], base=m0,
                         pct=100*r["beta"]/m0, n=r["n"]))
    except Exception as e:
        print(f"  {lab:30s}  ERROR {str(e)[:50]}")

pd.DataFrame(rows).to_csv(os.path.join(OUT, "phase3b0_robust.csv"),
                          index=False, encoding="utf-8-sig")
print(f"\n{BAR}\n저장: phase3b0_robust.csv   총 {time.time()-t0:.0f}s")
