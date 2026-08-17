"""Phase 4B — deep-discount anchor -> 28-day future store-wide behavior (PART B, observational)

Reuses the validated anchor SQL from src/phase3a_07_pdfcompare.py (lines 19-70) verbatim
(tx -> occ -> vis -> cls -> gaps -> pair CTE chain), then:
  1. builds the anchor pool (same filters: n>=5, n_deep>=2, n_full>=2, D in {0,1})
  2. drops anchors with another deep-discount (D=1) occasion in the SAME household_key x
     COMMODITY_DESC within +/-28 days (contamination), excluding the anchor occasion itself
  3. right-censors: keep only DAY+28 <= 705 (never fill post-period with 0 for censored anchors)
  4. computes, over the next 28 days (anchor day excluded), household-wide (all stores, all
     categories, using the same base sample filter as tx):
       - total store visits (distinct DAY)
       - total store spend (SUM SALES_VALUE)
       - basket count (distinct BASKET_ID)
       - other-category spend (total spend - anchor category spend)
  5. saves the anchor+outcome dataset to parquet for Phase 5A reuse
  6. estimates deep vs full-price differences with hh x cat FE and household-clustered SE

Resumable: if the parquet + composition CSV already exist, skips the heavy DuckDB build and
just reloads them for the reporting/regression step (safe to re-run after a crash downstream).
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, sys, time, warnings
import numpy as np, pandas as pd, pyfixest as pf

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
t0 = time.time()
ROOT = str(PROJECT_ROOT)
DB = os.path.join(ROOT, "data", "interim", "dunn.duckdb")
OUT = os.path.join(ROOT, "outputs", "tables")
MARTS = os.path.join(ROOT, "data", "marts")
BAR = "=" * 94

def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)

marts_path = os.path.join(MARTS, "phase4b_anchor_future28.parquet")
comp_path = os.path.join(OUT, "phase4b_sample_composition.csv")

if os.path.exists(marts_path) and os.path.exists(comp_path):
    log(f"RESUME: found existing {marts_path} and composition csv -> skipping heavy DuckDB build")
    df = pd.read_parquet(marts_path)
    comp0 = pd.read_csv(comp_path)
    n_anchor0 = int(comp0["anchor_pool_prefilter"].iloc[0])
    n_after_contam_censor = int(comp0["anchor_pool_postfilter"].iloc[0])
else:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET memory_limit='4GB'")

    log("building anchor pool (reused tx/occ/vis/cls/gaps/pair CTEs)...")
    anchor_sql = """
WITH tx AS (
    SELECT t.household_key, t.DAY, t.WEEK_NO, t.STORE_ID, t.PRODUCT_ID,
           p.COMMODITY_DESC, t.QUANTITY, t.SALES_VALUE, t.RETAIL_DISC,
           t.COUPON_DISC, t.COUPON_MATCH_DISC, t.BASKET_ID
    FROM transaction_data t JOIN product p ON t.PRODUCT_ID=p.PRODUCT_ID
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
),
occ AS (
    SELECT household_key, COMMODITY_DESC, DAY, any_value(WEEK_NO) WEEK_NO,
           max(STORE_ID) STORE_ID,
           SUM(QUANTITY) q_raw, SUM(SALES_VALUE) sales,
           SUM(SALES_VALUE-RETAIL_DISC-COUPON_DISC-COUPON_MATCH_DISC) reg_value,
           SUM(-RETAIL_DISC) / NULLIF(SUM(SALES_VALUE-RETAIL_DISC),0) AS rate
    FROM tx GROUP BY 1,2,3
),
vis AS (
    SELECT household_key, DAY,
           DENSE_RANK() OVER (PARTITION BY household_key ORDER BY DAY) visit_no
    FROM (SELECT DISTINCT household_key, DAY FROM tx)
),
cls AS (
    SELECT o.*, v.visit_no,
           CASE WHEN o.rate>=0.30 THEN 1 WHEN o.rate<=0.02 THEN 0 END AS D
    FROM occ o JOIN vis v USING (household_key, DAY)
),
gaps AS (
    SELECT *,
           LEAD(DAY)      OVER w - DAY      AS gap_days,
           LEAD(visit_no) OVER w - visit_no AS gap_visits
    FROM cls
    WINDOW w AS (PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY)
),
pair AS (
    SELECT household_key, COMMODITY_DESC, COUNT(*) n,
           COUNT(*) FILTER (WHERE D=1) nd, COUNT(*) FILTER (WHERE D=0) nf
    FROM gaps WHERE D IS NOT NULL GROUP BY 1,2
),
anchor0 AS (
    SELECT g.household_key, g.COMMODITY_DESC, g.STORE_ID, g.WEEK_NO, g.DAY, g.D,
           g.q_raw, g.sales, g.reg_value, g.gap_days, g.gap_visits, g.rate,
           ROW_NUMBER() OVER () AS anchor_id
    FROM gaps g JOIN pair p USING (household_key, COMMODITY_DESC)
    WHERE g.D IS NOT NULL AND p.n>=5 AND p.nd>=2 AND p.nf>=2
),
deep_events AS (
    SELECT DISTINCT household_key, COMMODITY_DESC, DAY FROM cls WHERE D=1
),
contaminated AS (
    SELECT DISTINCT a.anchor_id
    FROM anchor0 a
    JOIN deep_events e
      ON a.household_key = e.household_key AND a.COMMODITY_DESC = e.COMMODITY_DESC
     AND e.DAY <> a.DAY AND ABS(e.DAY - a.DAY) <= 28
)
SELECT a.*,
       CASE WHEN c.anchor_id IS NOT NULL THEN 1 ELSE 0 END AS contaminated,
       CASE WHEN a.DAY + 28 <= 705 THEN 1 ELSE 0 END AS not_censored
FROM anchor0 a
LEFT JOIN contaminated c USING (anchor_id)
"""
    anchor_all = con.execute(anchor_sql).df()
    n_anchor0 = len(anchor_all)
    anchor_raw = anchor_all[(anchor_all.contaminated == 0) & (anchor_all.not_censored == 1)].copy()
    anchor_raw.drop(columns=["contaminated", "not_censored"], inplace=True)
    n_after_contam_censor = len(anchor_raw)
    log(f"anchor pool (pre-filter, same as phase3a) = {n_anchor0:,}")
    log(f"anchor pool (after contamination-drop + right-censor DAY+28<=705) = {n_after_contam_censor:,}  "
        f"(dropped {n_anchor0 - n_after_contam_censor:,})")

    # register anchor_raw for the post-window join
    con.register("anchor_tbl", anchor_raw)

    log("computing 28-day post-window store-wide outcomes (visits/spend/baskets/other-cat spend)...")
    post_sql = """
WITH tx AS (
    SELECT t.household_key, t.DAY, t.WEEK_NO, t.STORE_ID, t.PRODUCT_ID,
           p.COMMODITY_DESC, t.SALES_VALUE, t.BASKET_ID
    FROM transaction_data t JOIN product p ON t.PRODUCT_ID=p.PRODUCT_ID
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
)
SELECT a.anchor_id,
       COALESCE(COUNT(DISTINCT t.DAY), 0)                                   AS post_visits,
       COALESCE(SUM(t.SALES_VALUE), 0.0)                                    AS post_spend,
       COALESCE(COUNT(DISTINCT t.BASKET_ID), 0)                             AS post_baskets,
       COALESCE(SUM(CASE WHEN t.COMMODITY_DESC = a.COMMODITY_DESC
                          THEN t.SALES_VALUE ELSE 0 END), 0.0)              AS post_anchorcat_spend
FROM anchor_tbl a
LEFT JOIN tx t
  ON t.household_key = a.household_key
 AND t.DAY BETWEEN a.DAY + 1 AND a.DAY + 28
GROUP BY a.anchor_id
"""
    post = con.execute(post_sql).df()
    log(f"post-window outcomes computed for {len(post):,} anchors")

    df = anchor_raw.merge(post, on="anchor_id", how="left")
    df["post_othercat_spend"] = df["post_spend"] - df["post_anchorcat_spend"]

    df["cat"] = pd.factorize(df.COMMODITY_DESC)[0]
    df["hh_cat"] = pd.factorize(df.household_key.astype(str) + "_" + df.cat.astype(str))[0]

    df.to_parquet(marts_path, index=False)
    log(f"saved anchor+outcome dataset -> {marts_path}  rows={len(df):,}")

    con.close()

print(BAR)
print("Phase 4B - deep-discount anchor -> next-28-day store-wide behavior (PART B, observational)")
print(BAR)
print(f"\n  anchor pool (post pair-filter, reused from phase3a) = {n_anchor0:,}")
print(f"  after contamination-drop (+/-28d another deep-discount) + right-censor(DAY+28<=705) = "
      f"{n_after_contam_censor:,}  (dropped {n_anchor0-n_after_contam_censor:,})")
print(f"  households {df.household_key.nunique():,} / categories {df.cat.nunique()} / "
      f"hh x cat pairs {df.hh_cat.nunique():,}")
print(f"  deep-discount anchors {int(df.D.sum()):,} / full-price anchors {int((1-df.D).sum()):,}")

OUTCOMES = [("post_visits", "28d future store visits (all stores)"),
            ("post_spend", "28d future total spend (all stores)"),
            ("post_baskets", "28d future basket count (all stores)"),
            ("post_othercat_spend", "28d future other-category spend")]

rows = []
print(f"\n  === hh x cat FE, household-clustered SE ===")
print(f"  {'outcome':38s} {'beta':>10s} {'SE':>8s} {'t':>8s} {'p':>8s} "
      f"{'full-price avg':>15s} {'%diff':>9s} {'N':>9s}")
for y, ylab in OUTCOMES:
    d = df[df[y].notna()]
    fml = f"{y} ~ D | hh_cat"
    m = pf.feols(fml, data=d, vcov={"CRV1": "household_key"})
    b, se, t, p = m.coef()["D"], m.se()["D"], m.tstat()["D"], m.pvalue()["D"]
    base = d.loc[d.D == 0, y].mean()
    ci_lo, ci_hi = b - 1.96 * se, b + 1.96 * se
    print(f"  {ylab:38s} {b:10.4f} {se:8.4f} {t:8.2f} {p:8.4f} {base:15.3f} "
          f"{100*b/base:8.2f}%  {len(d):9,}")
    rows.append(dict(outcome=ylab, outcome_var=y, beta=b, se=se, t=t, p=p,
                      ci_lo=ci_lo, ci_hi=ci_hi, base_fullprice_mean=base,
                      pct_diff=100*b/base, n=len(d),
                      households=d.household_key.nunique(), categories=d.cat.nunique(),
                      hh_cat_pairs=d.hh_cat.nunique()))

res = pd.DataFrame(rows)
res_path = os.path.join(OUT, "phase4b_future28_results.csv")
res.to_csv(res_path, index=False, encoding="utf-8-sig")
log(f"saved regression results -> {res_path}")

# sample composition summary for the report (also lets a re-run resume)
pd.DataFrame([dict(
    anchor_pool_prefilter=n_anchor0,
    anchor_pool_postfilter=n_after_contam_censor,
    dropped_contam_or_censor=n_anchor0 - n_after_contam_censor,
    households=df.household_key.nunique(),
    categories=df.cat.nunique(),
    hh_cat_pairs=df.hh_cat.nunique(),
    deep_anchors=int(df.D.sum()),
    fullprice_anchors=int((1-df.D).sum()),
)]).to_csv(comp_path, index=False, encoding="utf-8-sig")
log(f"saved sample composition -> {comp_path}")

print(f"\n{BAR}")
log("Phase 4B DONE")
