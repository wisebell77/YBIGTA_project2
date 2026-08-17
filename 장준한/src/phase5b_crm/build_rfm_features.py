"""Phase 5B-1 — period-split RFM 프로필 + 평가기간 anchor + future 28일 store outcome 빌드

설계 (leakage 방지, period split):
  pre-period  DAY 55-138   (84일, sample DAY 최솟값=55부터 시작 — 더 당길 수 없음)
  eval period DAY 139-677  (anchor: occasion 단위 household_key x COMMODITY_DESC x DAY)
  future window (DAY_anchor, DAY_anchor+28]  — anchor DAY<=677 이므로 max(DAY)=705 censoring 자동 충족

households: pre-period에 최소 1일 구매기록이 있어야 RFM 프로필 생성 가능(없으면 제외, 카운트 기록).
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, time
import numpy as np, pandas as pd

t_start = time.time()
ROOT = str(PROJECT_ROOT)
DB = os.path.join(ROOT, "data", "interim", "dunn.duckdb")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 90

PRE_START, PRE_END = 55, 138     # 84 days: 138-55+1=84
EVAL_START, EVAL_END = 139, 677  # anchor DAY<=677 -> +28 <= 705 (max DAY, no leakage past data end)

print(BAR)
print("Phase 5B-1: period-split RFM build")
print(f"pre-period DAY [{PRE_START},{PRE_END}] ({PRE_END-PRE_START+1}d)  |  "
      f"eval anchors DAY [{EVAL_START},{EVAL_END}]  |  future window (anchor, anchor+28]")
print(BAR)

con = duckdb.connect(DB, read_only=True)
con.execute("SET memory_limit='4GB'")

TX_CTE = """
tx AS (
    SELECT t.household_key, t.DAY, t.STORE_ID, t.PRODUCT_ID,
           p.COMMODITY_DESC, t.SALES_VALUE, t.RETAIL_DISC,
           t.COUPON_DISC, t.COUPON_MATCH_DISC
    FROM transaction_data t JOIN product p ON t.PRODUCT_ID = p.PRODUCT_ID
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
)
"""

# ---------------------------------------------------------------- 1. pre-period profile
print("\n[1/4] pre-period RFM + behavior profile ...")
t0 = time.time()
profile = con.execute(f"""
WITH {TX_CTE},
pretx AS (SELECT * FROM tx WHERE DAY BETWEEN {PRE_START} AND {PRE_END}),
occ AS (
    SELECT household_key, COMMODITY_DESC, DAY,
           SUM(SALES_VALUE) sales,
           SUM(-RETAIL_DISC) / NULLIF(SUM(SALES_VALUE-RETAIL_DISC),0) AS rate
    FROM pretx GROUP BY 1,2,3
),
occ_cls AS (
    SELECT *, CASE WHEN rate>=0.30 THEN 1 WHEN rate<=0.02 THEN 0 END D
    FROM occ
),
day_agg AS (
    SELECT household_key, DAY, SUM(SALES_VALUE) day_sales
    FROM pretx GROUP BY 1,2
),
rfm AS (
    SELECT household_key,
           {PRE_END} - MAX(DAY) AS R,
           COUNT(DISTINCT DAY) AS F,
           SUM(day_sales) AS M
    FROM day_agg GROUP BY 1
),
gaps AS (
    SELECT household_key, DAY - LAG(DAY) OVER (PARTITION BY household_key ORDER BY DAY) AS gap
    FROM day_agg
),
typical_gap AS (
    SELECT household_key, AVG(gap) AS typical_gap, COUNT(gap) AS n_gaps
    FROM gaps WHERE gap IS NOT NULL GROUP BY 1
),
disc AS (
    SELECT household_key,
           SUM(sales) FILTER (WHERE D=1) / NULLIF(SUM(sales),0) AS deep_spend_share,
           SUM(sales*rate) / NULLIF(SUM(sales),0) AS spend_wtd_rate,
           AVG(rate) AS mean_occ_rate
    FROM occ_cls GROUP BY 1
),
cat AS (
    SELECT household_key,
           COUNT(DISTINCT COMMODITY_DESC) AS n_cat,
           SUM(POWER(cat_sales/tot_sales, 2)) AS hhi
    FROM (
        SELECT household_key, COMMODITY_DESC, SUM(SALES_VALUE) cat_sales,
               SUM(SUM(SALES_VALUE)) OVER (PARTITION BY household_key) tot_sales
        FROM pretx GROUP BY 1,2
    ) GROUP BY 1
)
SELECT r.household_key, r.R, r.F, r.M,
       COALESCE(d.deep_spend_share,0) deep_spend_share,
       d.spend_wtd_rate, d.mean_occ_rate,
       c.n_cat, c.hhi,
       tg.typical_gap, tg.n_gaps,
       CASE WHEN tg.typical_gap IS NOT NULL THEN (r.R > tg.typical_gap)::INT END AS churn_flag
FROM rfm r
LEFT JOIN disc d USING (household_key)
LEFT JOIN cat c USING (household_key)
LEFT JOIN typical_gap tg USING (household_key)
""").df()
print(f"  households with pre-period profile: {len(profile):,}  ({time.time()-t0:.1f}s)")
print(f"  R range [{profile.R.min()},{profile.R.max()}]  F range [{profile.F.min()},{profile.F.max()}]  "
      f"M range [{profile.M.min():.1f},{profile.M.max():.1f}]")
print(f"  churn_flag undefined (F=1, no gap) for {profile.churn_flag.isna().sum():,} households")

# ---------------------------------------------------------------- 2. tertiles / segments
print("\n[2/4] quantile cuts (tertiles) ...")

def tertile(s, labels=("Low", "Mid", "High")):
    return pd.qcut(s.rank(method="first"), 3, labels=labels)

profile["R_tert"] = tertile(-profile.R, labels=("Low(오래됨)", "Mid", "High(최근)"))  # High = recent = good
profile["F_tert"] = tertile(profile.F, labels=("Low", "Mid", "High"))
profile["M_tert"] = tertile(profile.M, labels=("Low", "Mid", "High"))
profile["disc_tert"] = tertile(profile.deep_spend_share, labels=("Low(정가선호)", "Mid", "High(딥할인선호)"))

score_map = {"Low(오래됨)": 1, "Mid": 2, "High(최근)": 3}
score_map2 = {"Low": 1, "Mid": 2, "High": 3}
profile["rfm_score"] = (profile.R_tert.map(score_map).astype(float)
                         + profile.F_tert.map(score_map2).astype(float)
                         + profile.M_tert.map(score_map2).astype(float))
profile["rfm_seg"] = pd.qcut(profile.rfm_score.rank(method="first"), 3,
                              labels=("Low value", "Mid value", "High value"))

print("  R tertile cut points (days since last trip, pre-window end=DAY138):")
print("   ", profile.groupby("R_tert", observed=True).R.agg(["min", "max", "count"]))
print("  F tertile cut points (distinct shopping days / 84d):")
print("   ", profile.groupby("F_tert", observed=True).F.agg(["min", "max", "count"]))
print("  M tertile cut points (pre-period SALES_VALUE):")
print("   ", profile.groupby("M_tert", observed=True).M.agg(["min", "max", "count"]))
print("  discount-share tertile cut points (deep-discount spend share, pre-period):")
print("   ", profile.groupby("disc_tert", observed=True).deep_spend_share.agg(["min", "max", "count"]))
print("  rfm_score composite -> rfm_seg tertile:")
print("   ", profile.groupby("rfm_seg", observed=True).rfm_score.agg(["min", "max", "count"]))

profile.to_csv(os.path.join(OUT, "phase5b_household_profile.csv"), index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 3. eval-period occasions -> anchors
print("\n[3/4] eval-period occasions (anchors, deep vs full-price) ...")
t0 = time.time()
pre_hh = set(profile.household_key.tolist())
con.execute("CREATE OR REPLACE TEMP TABLE pre_hh AS SELECT UNNEST(?) AS household_key", [list(pre_hh)])

anchors = con.execute(f"""
WITH {TX_CTE},
evtx AS (SELECT * FROM tx WHERE DAY BETWEEN {EVAL_START} AND {EVAL_END}),
occ AS (
    SELECT household_key, COMMODITY_DESC, DAY,
           SUM(SALES_VALUE) sales,
           SUM(-RETAIL_DISC) / NULLIF(SUM(SALES_VALUE-RETAIL_DISC),0) AS rate
    FROM evtx GROUP BY 1,2,3
),
cls AS (
    SELECT o.*, CASE WHEN rate>=0.30 THEN 1 WHEN rate<=0.02 THEN 0 END D
    FROM occ o JOIN pre_hh USING (household_key)
)
SELECT household_key, COMMODITY_DESC, DAY, sales, rate, D
FROM cls WHERE D IS NOT NULL
""").df()
print(f"  anchor occasions: {len(anchors):,}  deep(D=1) {int((anchors.D==1).sum()):,}  "
      f"full(D=0) {int((anchors.D==0).sum()):,}  households {anchors.household_key.nunique():,}  "
      f"({time.time()-t0:.1f}s)")

# ---------------------------------------------------------------- 4. future 28-day store outcome per (hh, DAY)
print("\n[4/4] future 28-day store visits / spend per anchor (hh, DAY) via range join ...")
t0 = time.time()
hh_days = anchors[["household_key", "DAY"]].drop_duplicates()
con.execute("CREATE OR REPLACE TEMP TABLE hh_days AS SELECT * FROM hh_days")

future = con.execute(f"""
WITH {TX_CTE},
day_agg AS (SELECT household_key, DAY, SUM(SALES_VALUE) day_sales FROM tx GROUP BY 1,2)
SELECT a.household_key, a.DAY,
       COUNT(h.DAY) AS future_visits,
       COALESCE(SUM(h.day_sales), 0) AS future_spend
FROM hh_days a
LEFT JOIN day_agg h
  ON h.household_key = a.household_key AND h.DAY > a.DAY AND h.DAY <= a.DAY + 28
GROUP BY 1, 2
""").df()
print(f"  distinct (hh,DAY) anchor keys: {len(hh_days):,}  future table rows: {len(future):,}  "
      f"({time.time()-t0:.1f}s)")

anchors_full = anchors.merge(future, on=["household_key", "DAY"], how="left")
anchors_full = anchors_full.merge(
    profile[["household_key", "R", "F", "M", "R_tert", "F_tert", "M_tert",
             "disc_tert", "rfm_score", "rfm_seg", "churn_flag", "deep_spend_share"]],
    on="household_key", how="left")

MART_DIR = os.path.join(ROOT, "data", "marts")
os.makedirs(MART_DIR, exist_ok=True)
anchors_full.to_parquet(os.path.join(MART_DIR, "phase5b_anchors.parquet"), index=False)
anchors_full.sample(min(2000, len(anchors_full)), random_state=0).to_csv(
    os.path.join(OUT, "phase5b_anchors_sample.csv"), index=False, encoding="utf-8-sig")

print(f"\nsaved: outputs/tables/phase5b_household_profile.csv  ({len(profile):,} rows)")
print(f"saved: data/marts/phase5b_anchors.parquet  ({len(anchors_full):,} rows, full anchor table)")
print(f"saved: outputs/tables/phase5b_anchors_sample.csv  (2,000-row sample for inspection)")
print(f"\ntotal elapsed {time.time()-t_start:.1f}s")
print(BAR)
