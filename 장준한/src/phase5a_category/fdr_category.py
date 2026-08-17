"""Phase 5A — 카테고리 다중검정 BH-FDR 보정 (후처리 전용)

p-value 는 원 CSV 에 저장돼 있지 않아, 공표된 CI(beta ± 1.96·SE)에서 SE 를 정확히
역산하고 같은 정규근사로 양측 p 를 계산한다. 원 회귀 p-value 와 완전히 동일하지 않다.

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


# Phase 5A — category portfolio
# ══════════════════════════════════════════════════════════════════════
a = pd.read_csv(os.path.join(T, "phase5a_category_matrix.csv")).copy()

for ax, pre in [("visit", "x"), ("spend", "y")]:
    se = (a[f"{pre}_ci_hi"] - a[f"{pre}_ci_lo"]) / (2 * Z)
    a[f"{ax}_beta"] = a[pre]
    a[f"{ax}_se"] = se
    a[f"{ax}_t"] = a[pre] / se
    a[f"{ax}_p"] = 2 * stats.norm.sf(np.abs(a[f"{ax}_t"]))

a["visit_q"] = bh(a["visit_p"])
a["spend_q"] = bh(a["spend_p"])
# sensitivity: 166개를 하나의 family로
joint = bh(pd.concat([a["visit_p"], a["spend_p"]]).values)
a["visit_q_joint"] = joint[:len(a)]
a["spend_q_joint"] = joint[len(a):]

a["nominal_visit_sig"] = a["visit_p"] < 0.05
a["nominal_spend_sig"] = a["spend_p"] < 0.05
a["fdr_visit_sig"] = a["visit_q"] < Q
a["fdr_spend_sig"] = a["spend_q"] < Q
a["fdr_visit_sig_joint"] = a["visit_q_joint"] < Q
a["fdr_spend_sig_joint"] = a["spend_q_joint"] < Q


def classify(r):
    both_fdr = r.fdr_visit_sig and r.fdr_spend_sig
    same_dir_pos = r.visit_beta > 0 and r.spend_beta > 0
    same_dir_neg = r.visit_beta < 0 and r.spend_beta < 0
    if both_fdr and same_dir_pos:
        return "robust strengthening"
    if both_fdr and same_dir_neg:
        return "robust weakening"
    if same_dir_pos or same_dir_neg:
        return "suggestive"
    return "indeterminate"


a["classification_fdr"] = a.apply(classify, axis=1)
a = a.rename(columns={"classification": "classification_prefdr"})

COLS = ["category", "n", "n_deep", "n_full", "households",
        "visit_beta", "visit_se", "visit_ci_lo", "visit_ci_hi", "visit_t",
        "visit_p", "visit_q", "visit_q_joint",
        "spend_beta", "spend_se", "spend_ci_lo", "spend_ci_hi", "spend_t",
        "spend_p", "spend_q", "spend_q_joint",
        "nominal_visit_sig", "nominal_spend_sig",
        "fdr_visit_sig", "fdr_spend_sig",
        "fdr_visit_sig_joint", "fdr_spend_sig_joint",
        "classification_prefdr", "classification_fdr"]
a = a.rename(columns={"x_ci_lo": "visit_ci_lo", "x_ci_hi": "visit_ci_hi",
                      "y_ci_lo": "spend_ci_lo", "y_ci_hi": "spend_ci_hi"})
a["part"] = "B (observational)"
out5a = a[["part"] + COLS]
out5a.to_csv(os.path.join(T, "phase5a_category_portfolio.csv"),
             index=False, encoding="utf-8-sig")
out5a.to_csv(os.path.join(TAB, "category_portfolio.csv"),
             index=False, encoding="utf-8-sig")

print(f"\n■ Phase 5A — 83개 카테고리\n")
print(f"{'':34s} {'visits':>10s} {'spend':>10s}")
print(f"{'nominal p<0.05':34s} {int(a.nominal_visit_sig.sum()):>10d} "
      f"{int(a.nominal_spend_sig.sum()):>10d}")
print(f"{'BH FDR q<0.05 (family=83)':34s} {int(a.fdr_visit_sig.sum()):>10d} "
      f"{int(a.fdr_spend_sig.sum()):>10d}")
print(f"{'BH FDR q<0.05 (joint family=166)':34s} "
      f"{int(a.fdr_visit_sig_joint.sum()):>10d} "
      f"{int(a.fdr_spend_sig_joint.sum()):>10d}")

print(f"\n  분류 변화 (FDR 이전 → 이후)")
pre = a.classification_prefdr.value_counts()
post = a.classification_fdr.value_counts()
for k in ["robust strengthening", "robust weakening", "suggestive",
          "strengthening", "weakening", "indeterminate"]:
    if k in pre.index or k in post.index:
        print(f"    {k:24s} 이전 {pre.get(k,0):>3d}  →  이후 {post.get(k,0):>3d}")

fdr5a = pd.DataFrame([
    dict(family="visits (83)", n_tests=len(a),
         n_nominal=int(a.nominal_visit_sig.sum()),
         n_fdr=int(a.fdr_visit_sig.sum()),
         min_p=float(a.visit_p.min()), min_q=float(a.visit_q.min())),
    dict(family="spend (83)", n_tests=len(a),
         n_nominal=int(a.nominal_spend_sig.sum()),
         n_fdr=int(a.fdr_spend_sig.sum()),
         min_p=float(a.spend_p.min()), min_q=float(a.spend_q.min())),
    dict(family="joint visits+spend (166)", n_tests=2 * len(a),
         n_nominal=int(a.nominal_visit_sig.sum() + a.nominal_spend_sig.sum()),
         n_fdr=int(a.fdr_visit_sig_joint.sum() + a.fdr_spend_sig_joint.sum()),
         min_p=float(min(a.visit_p.min(), a.spend_p.min())),
         min_q=float(min(a.visit_q_joint.min(), a.spend_q_joint.min()))),
])
fdr5a.to_csv(os.path.join(T, "phase5a_fdr_summary.csv"),
             index=False, encoding="utf-8-sig")
print(f"\n{fdr5a.to_string(index=False)}")

surv = a[a.classification_fdr.isin(["robust strengthening", "robust weakening"])]
print(f"\n  FDR 후 robust 카테고리: {len(surv)}개")
if len(surv):
    print(surv[["category", "visit_beta", "visit_q", "spend_beta",
                "spend_q", "n", "classification_fdr"]].to_string(index=False))

# ══════════════════════════════════════════════════════════════════════

print(BAR)
print("Phase 5A FDR 저장 완료")
print(BAR)
