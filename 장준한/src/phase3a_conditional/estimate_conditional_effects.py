"""Phase 3A-3 — 처치 정의 비교 · Model 0/1/2 추정 · cluster SE 비교"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, time, warnings
import numpy as np
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

ROOT = str(PROJECT_ROOT)
MART = os.path.join(ROOT, "data", "marts", "occasion.parquet").replace("\\", "/")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 88
def h(t): print(f"\n{BAR}\n{t}\n{BAR}")

con = duckdb.connect()

# ══════════════════════════════════════════════════════════════════════════
h("§2  처치 정의 비교 — mailer_any vs mailer_feature")
# ══════════════════════════════════════════════════════════════════════════
rows = []
for tag, col in [("A mailer_any", "exp_any"), ("B mailer_feature", "exp_feat")]:
    r = con.execute(f"""
    WITH o AS (SELECT * FROM '{MART}'),
    pair AS (
        SELECT household_key, COMMODITY_DESC, COUNT(*) n,
               SUM({col}) ne, COUNT(*)-SUM({col}) nu
        FROM o GROUP BY 1,2
    ),
    keep AS (SELECT * FROM pair WHERE n>=5 AND ne>=2 AND nu>=2),
    cat AS (
        SELECT COMMODITY_DESC, COUNT(*) n, AVG({col}) rate
        FROM o GROUP BY 1 HAVING COUNT(*)>=1000
    )
    SELECT (SELECT COUNT(*) FROM o),
           (SELECT SUM({col}) FROM o),
           (SELECT COUNT(*) FROM keep),
           (SELECT COUNT(DISTINCT household_key) FROM keep),
           (SELECT COUNT(DISTINCT COMMODITY_DESC) FROM keep),
           (SELECT SUM(n) FROM keep),
           (SELECT COUNT(*) FROM cat WHERE rate BETWEEN 0.05 AND 0.95),
           (SELECT COUNT(*) FROM cat),
           (SELECT median(rate) FROM cat),
           (SELECT AVG(disc_amt/NULLIF(reg_value,0)) FROM o WHERE {col}=1),
           (SELECT AVG(disc_amt/NULLIF(reg_value,0)) FROM o WHERE {col}=0)
    """).fetchone()
    rows.append((tag, *r))

print(f"\n{'정의':18s} {'노출 occ':>12s} {'노출률':>7s} {'usable pair':>12s} "
      f"{'가구':>6s} {'카테':>5s} {'표본 occ':>10s}")
for t, n_all, n_exp, npair, nhh, ncat, nocc, usable, ncat_all, medrate, dr1, dr0 in rows:
    print(f"{t:18s} {n_exp:>12,} {100*n_exp/n_all:6.2f}% {npair:>12,} "
          f"{nhh:>6,} {ncat:>5} {nocc:>10,}")

print(f"\n{'정의':18s} {'가용 카테고리(5~95%)':>22s} {'중위 노출률':>11s} "
      f"{'노출 할인율':>11s} {'미노출 할인율':>13s} {'배수':>6s}")
for t, n_all, n_exp, npair, nhh, ncat, nocc, usable, ncat_all, medrate, dr1, dr0 in rows:
    print(f"{t:18s} {usable:>13,}/{ncat_all:<8,} {100*medrate:10.1f}% "
          f"{100*dr1:10.2f}% {100*dr0:12.2f}% {dr1/dr0:6.2f}x")

# 두 정의의 불일치
r = con.execute(f"""
SELECT COUNT(*) FILTER (WHERE exp_any=1 AND exp_feat=0),
       COUNT(*) FILTER (WHERE exp_any=0 AND exp_feat=1),
       COUNT(*) FROM '{MART}'
""").fetchone()
print(f"\n  any=1 & feature=0 : {r[0]:,} ({100*r[0]/r[2]:.2f}%)  <- 쿠폰(J,P)/무료(X,Z) 전용 셀")
print(f"  any=0 & feature=1 : {r[1]:,}  (정의상 0이어야 정상)")

# ══════════════════════════════════════════════════════════════════════════
h("§4-5  분석 표본 구축 및 추정")
# ══════════════════════════════════════════════════════════════════════════

def build(col):
    df = con.execute(f"""
    WITH o AS (SELECT * FROM '{MART}'),
    pair AS (
        SELECT household_key, COMMODITY_DESC, COUNT(*) n,
               SUM({col}) ne, COUNT(*)-SUM({col}) nu
        FROM o GROUP BY 1,2
    )
    SELECT o.household_key, o.COMMODITY_DESC, o.STORE_ID, o.WEEK_NO, o.DAY,
           o.{col} AS D, o.q_raw, o.q_w20, o.sales, o.reg_value,
           o.gap_days, o.gap_visits
    FROM o JOIN pair p USING (household_key, COMMODITY_DESC)
    WHERE p.n>=5 AND p.ne>=2 AND p.nu>=2
    """).df()
    df["cat"] = pd.factorize(df["COMMODITY_DESC"])[0]
    df["hh_cat"] = pd.factorize(
        df["household_key"].astype(str) + "_" + df["cat"].astype(str))[0]
    df["store_cat"] = pd.factorize(
        df["STORE_ID"].astype(str) + "_" + df["cat"].astype(str))[0]
    df["cat_week"] = pd.factorize(
        df["cat"].astype(str) + "_" + df["WEEK_NO"].astype(str))[0]
    return df

SAMPLES = {"A mailer_any": build("exp_any"), "B mailer_feature": build("exp_feat")}
for tag, df in SAMPLES.items():
    print(f"\n  [{tag}] N={len(df):,}  가구={df.household_key.nunique():,}  "
          f"카테고리={df.cat.nunique()}  쌍={df.hh_cat.nunique():,}")
    print(f"        FE 규모: hh×cat {df.hh_cat.nunique():,} / "
          f"store×cat {df.store_cat.nunique():,} / cat×week {df.cat_week.nunique():,}")
    print(f"        gap 관측 {df.gap_days.notna().sum():,} "
          f"(중도절단 {df.gap_days.isna().sum():,} = {100*df.gap_days.isna().mean():.2f}%)")

OUTCOMES = [
    ("gap_days",   "다음 구매까지 일수",   True),
    ("gap_visits", "다음 구매까지 방문수", True),
    ("q_raw",      "occasion당 수량",      False),
    ("sales",      "occasion당 지출액",    False),
    ("reg_value",  "occasion당 정가환산",  False),
]
MODELS = [
    ("M0 naive",   None),
    ("M1 hh×cat",  "hh_cat"),
    ("M2 +store×cat +cat×week", "hh_cat + store_cat + cat_week"),
]

def fit(df, y, fe, vcov):
    d = df[df[y].notna()]
    fml = f"{y} ~ D" + (f" | {fe}" if fe else "")
    m = pf.feols(fml, data=d, vcov=vcov)
    b = m.coef().iloc[0]; se = m.se().iloc[0]
    t = m.tstat().iloc[0]; p = m.pvalue().iloc[0]
    base = d.loc[d.D == 0, y].mean()
    return dict(beta=b, se=se, t=t, p=p, n=len(d), base=base,
                pct=100 * b / base if base else np.nan,
                nfe=int(m._k_fe.sum()) if hasattr(m, "_k_fe") and m._k_fe is not None else 0)

results = []
for tag, df in SAMPLES.items():
    for y, ylab, is_gap in OUTCOMES:
        for mlab, fe in MODELS:
            t0 = time.time()
            try:
                r = fit(df, y, fe, {"CRV1": "household_key"})
                r.update(treat=tag, outcome=ylab, ycol=y, model=mlab,
                         sec=time.time() - t0, err="")
            except Exception as e:
                r = dict(treat=tag, outcome=ylab, ycol=y, model=mlab,
                         beta=np.nan, se=np.nan, t=np.nan, p=np.nan, n=0,
                         base=np.nan, pct=np.nan, nfe=0,
                         sec=time.time() - t0, err=str(e)[:60])
            results.append(r)
            print(f"  {tag[:1]} {mlab:26s} {ylab:20s} "
                  f"b={r['beta']:9.4f} t={r['t']:7.2f} n={r['n']:>8,} "
                  f"({r['sec']:.1f}s) {r['err']}")

res = pd.DataFrame(results)
res.to_csv(os.path.join(OUT, "phase3a_models.csv"), index=False, encoding="utf-8-sig")

# ══════════════════════════════════════════════════════════════════════════
h("§5  cluster SE 방식 비교 (Model 1 · Model 2, 처치 A)")
# ══════════════════════════════════════════════════════════════════════════
df = SAMPLES["A mailer_any"]
df["store_cat_s"] = df["store_cat"].astype(str)
VC = [
    ("A hh 1-way",              {"CRV1": "household_key"}),
    ("B hh + store 2-way",      {"CRV1": "household_key + STORE_ID"}),
    ("C hh + store×cat 2-way",  {"CRV1": "household_key + store_cat_s"}),
]
se_rows = []
for mlab, fe in MODELS[1:]:
    for y, ylab, _ in OUTCOMES:
        for vlab, vc in VC:
            try:
                r = fit(df, y, fe, vc)
                se_rows.append(dict(model=mlab, outcome=ylab, vcov=vlab, **r))
            except Exception as e:
                se_rows.append(dict(model=mlab, outcome=ylab, vcov=vlab,
                                    beta=np.nan, se=np.nan, t=np.nan, p=np.nan,
                                    n=0, base=np.nan, pct=np.nan, nfe=0,
                                    err=str(e)[:70]))
se = pd.DataFrame(se_rows)
se.to_csv(os.path.join(OUT, "phase3a_clusterse.csv"), index=False, encoding="utf-8-sig")

for mlab, _ in MODELS[1:]:
    print(f"\n  --- {mlab} ---")
    print(f"  {'결과변수':20s} {'SE 방식':24s} {'beta':>10s} {'SE':>9s} {'t':>8s} {'p':>8s}")
    for _, r in se[se.model == mlab].iterrows():
        if pd.isna(r["se"]):
            print(f"  {r['outcome']:20s} {r['vcov']:24s}  ERROR: {r.get('err','')}")
        else:
            print(f"  {r['outcome']:20s} {r['vcov']:24s} {r['beta']:10.4f} "
                  f"{r['se']:9.4f} {r['t']:8.2f} {r['p']:8.4f}")

print(f"\n결과 저장: {OUT}\\phase3a_models.csv, phase3a_clusterse.csv")
