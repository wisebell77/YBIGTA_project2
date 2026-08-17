"""Phase 5A — category-level visit x spend matrix (PART B, observational)

Reuses the Phase 4B anchor+outcome dataset (data/marts/phase4b_anchor_future28.parquet) —
no recomputation from raw transactions. Per COMMODITY_DESC:
  X = 28-day future store VISIT difference (deep - full), household-clustered SE, household FE
  Y = 28-day future store SPEND difference (deep - full), household-clustered SE, household FE
  bubble size = N (hh x cat pairs in that category)

Rules:
  - only categories with >= 100 hh x cat pairs
  - 95% CI + N reported for every category
  - classification: strengthening (X CI>0 AND Y CI>0), weakening (X CI<0 AND Y CI<0),
    else indeterminate. A CI crossing zero on either axis => indeterminate (never SCALE/STOP
    from sign alone).
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import os, sys, time, warnings
import numpy as np, pandas as pd, pyfixest as pf

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
t0 = time.time()
ROOT = str(PROJECT_ROOT)
MARTS = os.path.join(ROOT, "data", "marts")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 94

def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)

marts_path = os.path.join(MARTS, "phase4b_anchor_future28.parquet")
log(f"loading anchor dataset from Phase 4B -> {marts_path}")
df = pd.read_parquet(marts_path)
log(f"loaded rows={len(df):,}  categories={df.COMMODITY_DESC.nunique()}  "
    f"households={df.household_key.nunique():,}")

MIN_PAIRS = 100
results = []
skipped_small = 0
skipped_novariation = 0

cats = df.COMMODITY_DESC.unique()
log(f"iterating over {len(cats)} categories (min {MIN_PAIRS} hh x cat pairs)...")

for i, cat in enumerate(cats):
    d = df[df.COMMODITY_DESC == cat]
    n_pairs = d.hh_cat.nunique()
    if n_pairs < MIN_PAIRS:
        skipped_small += 1
        continue
    if d.D.nunique() < 2:
        skipped_novariation += 1
        continue

    row = dict(category=cat, n=n_pairs, n_anchors=len(d),
               n_deep=int(d.D.sum()), n_full=int((1 - d.D).sum()),
               households=d.household_key.nunique())
    ok = True
    for outcome, prefix in [("post_visits", "x"), ("post_spend", "y")]:
        dd = d[d[outcome].notna()]
        try:
            m = pf.feols(f"{outcome} ~ D | household_key", data=dd,
                         vcov={"CRV1": "household_key"})
            b, se = m.coef()["D"], m.se()["D"]
        except Exception:
            ok = False
            break
        row[prefix] = b
        row[f"{prefix}_se"] = se
        row[f"{prefix}_ci_lo"] = b - 1.96 * se
        row[f"{prefix}_ci_hi"] = b + 1.96 * se
        row[f"{prefix}_p"] = m.pvalue()["D"]
    if not ok:
        skipped_novariation += 1
        continue
    results.append(row)
    if (i + 1) % 50 == 0:
        log(f"  processed {i+1}/{len(cats)} categories...")

log(f"done: {len(results)} categories kept, {skipped_small} skipped (<{MIN_PAIRS} pairs), "
    f"{skipped_novariation} skipped (no D variation / fit failure)")

res = pd.DataFrame(results)

def classify(r):
    x_pos = r["x_ci_lo"] > 0
    x_neg = r["x_ci_hi"] < 0
    y_pos = r["y_ci_lo"] > 0
    y_neg = r["y_ci_hi"] < 0
    if x_pos and y_pos:
        return "strengthening"
    if x_neg and y_neg:
        return "weakening"
    return "indeterminate"

res["classification"] = res.apply(classify, axis=1)

out_cols = ["category", "x", "x_ci_lo", "x_ci_hi", "y", "y_ci_lo", "y_ci_hi",
            "n", "n_deep", "n_full", "households", "classification"]
res_out = res[out_cols].sort_values("n", ascending=False)
out_path = os.path.join(OUT, "phase5a_category_matrix.csv")
res_out.to_csv(out_path, index=False, encoding="utf-8-sig")
log(f"saved -> {out_path}  rows={len(res_out)}")

print(BAR)
print("Phase 5A - category-level 28-day future visit x spend matrix (PART B, observational)")
print(BAR)
print(f"\n  categories evaluated (>= {MIN_PAIRS} hh x cat pairs): {len(res_out)}")
print(f"  skipped (< {MIN_PAIRS} pairs): {skipped_small}   skipped (no variation/fit fail): {skipped_novariation}")
print(f"\n  classification counts:")
print(res_out.classification.value_counts().to_string())

print(f"\n  top 10 by |x| among non-indeterminate:")
sig = res_out[res_out.classification != "indeterminate"].copy()
sig["absx"] = sig.x.abs()
print(sig.sort_values("absx", ascending=False)
      [["category", "x", "x_ci_lo", "x_ci_hi", "y", "y_ci_lo", "y_ci_hi", "n", "classification"]]
      .head(10).to_string(index=False))

print(f"\n{BAR}")
log("Phase 5A DONE")
