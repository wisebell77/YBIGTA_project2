"""Phase 5B — CRM 세그먼트 다중검정 BH-FDR 보정 (후처리 전용)

결과변수별로 segment-level 검정만 하나의 family 로 본다.
사전지정 주 추정치(ALL)는 보정 대상에서 제외한다.

⚠️ 새 회귀를 실행하지 않는다. 저장된 결과 CSV 만 읽어 BH q-value 를 계산한다.
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT, TABLES_DIR, TABLEAU_DIR, ensure_dirs  # noqa: E402

import os, sys
import numpy as np, pandas as pd
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")

ensure_dirs()
T = str(TABLES_DIR)
TAB = str(TABLEAU_DIR)
Z = 1.96                      # 원 스크립트가 쓴 상수 (정확히 일치시켜야 함)
Q = 0.05
BAR = "=" * 100


def bh(p):
    """Benjamini-Hochberg q-value (step-up, 단조성 강제)"""
    p = np.asarray(p, dtype=float)
    m = len(p)
    order = np.argsort(p)
    q = np.empty(m, dtype=float)
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        val = p[i] * m / (rank + 1)
        prev = min(prev, val)
        q[i] = min(prev, 1.0)
    return q


# Phase 5B — CRM segments
# ══════════════════════════════════════════════════════════════════════
b = pd.read_csv(os.path.join(T, "phase5b_segment_results.csv")).copy()
b["is_overall"] = b.segmentation == "ALL"

# family = outcome별 segment-level 검정만 (ALL은 사전지정 주 추정치이므로 제외)
b["p"] = b["p_fe"]
b["q"] = np.nan
for oc in b.outcome.unique():
    m = (b.outcome == oc) & (~b.is_overall)
    b.loc[m, "q"] = bh(b.loc[m, "p"].values)

b["nominal_sig"] = b["p"] < 0.05
b["fdr_sig"] = b["q"] < Q

b["part"] = "B (observational)"
OUT5B = ["part", "segmentation", "level", "outcome", "n_hh", "n_occ",
         "n_pairs", "eff_n", "mean_full", "mean_deep",
         "diff_naive", "se_naive", "t_naive",
         "diff_fe", "se_fe", "ci_lo_fe", "ci_hi_fe", "t_fe",
         "p", "q", "nominal_sig", "fdr_sig", "is_overall"]
out5b = b[OUT5B]
out5b.to_csv(os.path.join(T, "phase5b_rfm_segments.csv"),
             index=False, encoding="utf-8-sig")
out5b.to_csv(os.path.join(TAB, "customer_segments.csv"),
             index=False, encoding="utf-8-sig")

print(f"\n{BAR}\n■ Phase 5B — segment-level FDR (ALL 제외, outcome별 family)\n{BAR}")
rows5b = []
for oc in b.outcome.unique():
    seg = b[(b.outcome == oc) & (~b.is_overall)]
    allr = b[(b.outcome == oc) & (b.is_overall)].iloc[0]
    print(f"\n  {oc}   [주 추정치(ALL): {allr.diff_fe:+.4f}, t={allr.t_fe:.2f}, "
          f"p={allr.p_fe:.4g}]")
    print(f"    {'segment':28s} {'diff_FE':>9s} {'t':>7s} {'p':>9s} {'q':>9s} "
          f"{'nominal':>8s} {'FDR':>5s}")
    for _, r in seg.sort_values("p").iterrows():
        print(f"    {r.segmentation+'/'+str(r.level):28s} {r.diff_fe:+9.4f} "
              f"{r.t_fe:7.2f} {r.p:9.4g} {r.q:9.4g} "
              f"{str(r.nominal_sig):>8s} {str(r.fdr_sig):>5s}")
    rows5b.append(dict(family=f"{oc} (segments)", n_tests=len(seg),
                       n_nominal=int(seg.nominal_sig.sum()),
                       n_fdr=int(seg.fdr_sig.sum()),
                       min_p=float(seg.p.min()), min_q=float(seg.q.min()),
                       overall_diff_fe=float(allr.diff_fe),
                       overall_p=float(allr.p_fe)))

fdr5b = pd.DataFrame(rows5b)
fdr5b.to_csv(os.path.join(T, "phase5b_fdr_summary.csv"),
             index=False, encoding="utf-8-sig")
print(f"\n{fdr5b.to_string(index=False)}")

print(f"\n{BAR}\n저장 완료\n{BAR}")

print(BAR)
print("Phase 5B FDR 저장 완료")
print(BAR)
