"""Phase 5B-2 — RFM/behavior 세그먼트별 딥할인 vs 정가 future 28일 store outcome 비교

관측적(observational) 분석: 딥할인 구매는 가구가 스스로 선택한 것이며 선택편의가 제거되지
않았다. 세그먼트 차이를 인과효과로 해석해서는 안 된다.

식별: TEAM_HANDOFF §4-1 "가구가 스스로의 대조군" — FE = hh×cat (household_key x COMMODITY_DESC).
FE 없는 naive 추정(raw between-household 평균차)은 구성효과(composition confounding)가 섞여
있어 대표값으로 쓰지 않는다 — 참고용으로만 같이 남긴다(naive-vs-FE 대비 자체가 발견).

최소 cell 크기: household>=30 AND occasion>=100 (naive 후보군 기준, 둘 다 충족해야 시도).
미달 시 인접 tertile을 병합하고 그 규칙을 기록한다. (본 데이터는 모든 cell이 이 기준을 크게
상회 — 병합 불필요.) FE 모형은 hh×cat 쌍 중 D=0/D=1 둘 다 있는 쌍에서만 식별되므로, 이 쌍 수
(n_pairs)와 유효 occasion 수(eff_n)를 별도로 보고한다 — 표본이 줄어드는 것은 예상된 결과다.
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import os, sys, warnings
import numpy as np, pandas as pd, pyfixest as pf

sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")
ROOT = str(PROJECT_ROOT)
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 94
MIN_HH, MIN_OCC = 30, 100

df = pd.read_parquet(os.path.join(ROOT, "data", "marts", "phase5b_anchors.parquet"))
df["hh_cat"] = pd.factorize(df.household_key.astype(str) + "_" + df.COMMODITY_DESC.astype(str))[0]

print(BAR)
print("Phase 5B-2: segment x (deep vs full-price) future-28d comparison -- hh x cat FE")
print(f"anchors {len(df):,}  households {df.household_key.nunique():,}  hh_cat pairs {df.hh_cat.nunique():,}  "
      f"min cell rule (naive pool): household>={MIN_HH} occasion>={MIN_OCC}")
print(BAR)

OUTCOMES = [("future_visits", "future 28d store visits"), ("future_spend", "future 28d store spend")]
SEGS = ["R_tert", "F_tert", "M_tert", "disc_tert", "rfm_seg", "churn_flag"]

rows = []


def run_cell(sub, seg_name, seg_level, y, ylab):
    n_occ = len(sub)
    n_hh = sub.household_key.nunique()
    n1, n0 = int((sub.D == 1).sum()), int((sub.D == 0).sum())
    hh1, hh0 = sub.loc[sub.D == 1, "household_key"].nunique(), sub.loc[sub.D == 0, "household_key"].nunique()
    if min(n1, n0) < MIN_OCC or min(hh1, hh0) < MIN_HH:
        print(f"  [SKIP too small] {seg_name}={seg_level} {ylab}: n1={n1} n0={n0} hh1={hh1} hh0={hh0}")
        return None

    base = sub.loc[sub.D == 0, y].mean()
    mean1 = sub.loc[sub.D == 1, y].mean()

    # naive (no FE) -- kept for reference only, composition-confounded
    m0 = pf.feols(f"{y} ~ D", data=sub, vcov={"CRV1": "household_key"})
    b0, se0, t0 = m0.coef()["D"], m0.se()["D"], m0.tstat()["D"]

    # hh x cat FE -- primary estimate, household is its own control within category
    grp = sub.groupby("hh_cat")["D"].agg(["nunique", "count"])
    both = grp[grp["nunique"] == 2]
    n_pairs, eff_n = len(both), int(both["count"].sum())

    b, se, t, p, ci_lo, ci_hi = (np.nan,) * 6
    if n_pairs >= 5:
        try:
            m = pf.feols(f"{y} ~ D | hh_cat", data=sub, vcov={"CRV1": "household_key"})
            b, se, t, p = m.coef()["D"], m.se()["D"], m.tstat()["D"], m.pvalue()["D"]
            ci_lo, ci_hi = b - 1.96 * se, b + 1.96 * se
        except Exception as e:
            print(f"  [FE FAILED] {seg_name}={seg_level} {ylab}: {e}")
    else:
        print(f"  [FE SKIPPED too few pairs] {seg_name}={seg_level} {ylab}: n_pairs={n_pairs}")

    return dict(segmentation=seg_name, level=str(seg_level), outcome=ylab,
                n_occ=n_occ, n_hh=n_hh, n_deep=n1, n_full=n0, hh_deep=hh1, hh_full=hh0,
                mean_full=base, mean_deep=mean1,
                diff_naive=b0, se_naive=se0, t_naive=t0,
                n_pairs=n_pairs, eff_n=eff_n,
                diff_fe=b, se_fe=se, ci_lo_fe=ci_lo, ci_hi_fe=ci_hi, t_fe=t, p_fe=p,
                pct_fe=100 * b / base if base and not np.isnan(b) else np.nan)


def fmt(v, w=8, d=4):
    return f"{v:{w}.{d}f}" if pd.notna(v) else " " * (w - 2) + "NA"


# ---- overall (no segmentation) baseline ----
print("\n-- overall (all households pooled) --")
for y, ylab in OUTCOMES:
    r = run_cell(df, "ALL", "ALL", y, ylab)
    if r:
        rows.append(r)
        print(f"  {ylab:26s} full-mean={r['mean_full']:.3f} deep-mean={r['mean_deep']:.3f}  "
              f"naive_diff={r['diff_naive']:+.4f} (t={r['t_naive']:.2f})  |  "
              f"FE_diff={fmt(r['diff_fe'])} SE={fmt(r['se_fe'])} "
              f"95%CI=[{fmt(r['ci_lo_fe'])},{fmt(r['ci_hi_fe'])}] t={fmt(r['t_fe'],6,2)} "
              f"n_pairs={r['n_pairs']:,} eff_n={r['eff_n']:,}")

# ---- per segmentation ----
for seg in SEGS:
    print(f"\n-- segmentation: {seg} --")
    levels = [lv for lv in df[seg].cat.categories] if hasattr(df[seg], "cat") else sorted(df[seg].dropna().unique())
    for lv in levels:
        sub = df[df[seg] == lv]
        for y, ylab in OUTCOMES:
            r = run_cell(sub, seg, lv, y, ylab)
            if r:
                rows.append(r)
                print(f"  {str(lv):18s} {ylab:26s} naive={r['diff_naive']:+8.4f}(t={r['t_naive']:6.2f})  |  "
                      f"FE={fmt(r['diff_fe'])} SE={fmt(r['se_fe'],7,4)} "
                      f"95%CI=[{fmt(r['ci_lo_fe'])},{fmt(r['ci_hi_fe'])}] t={fmt(r['t_fe'],6,2)} "
                      f"n_pairs={r['n_pairs']:,} eff_n={r['eff_n']:,}")
    sub_na = df[df[seg].isna()]
    if len(sub_na) > 0:
        print(f"  [excluded, undefined] {seg}=NA: {len(sub_na):,} occasions / "
              f"{sub_na.household_key.nunique():,} households (churn proxy undefined, F=1 in pre-period)")

res = pd.DataFrame(rows)
res.to_csv(os.path.join(OUT, "phase5b_segment_results.csv"), index=False, encoding="utf-8-sig")
print(f"\nsaved: outputs/tables/phase5b_segment_results.csv  ({len(res)} rows)")
print(BAR)
