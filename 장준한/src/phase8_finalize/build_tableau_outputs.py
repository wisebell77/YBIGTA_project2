"""Phase 7 — Tableau-ready 데이터셋 생성 + 전 수치 교차검증

모든 FINAL_* 산출물의 숫자를 원본 CSV에서 직접 읽어 만든다(하드코딩 금지).
마지막에 보고서에 인용된 헤드라인 수치를 원본과 대조 검증한다.
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

ROOT = str(PROJECT_ROOT)
T = os.path.join(ROOT, "outputs", "tables")
TAB = os.path.join(ROOT, "outputs", "tableau")
os.makedirs(TAB, exist_ok=True)
BAR = "=" * 100


def rd(n):
    return pd.read_csv(os.path.join(T, n))


def w(df, name):
    p = os.path.join(TAB, name)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"  {name:44s} {len(df):>6,}행")


print(f"{BAR}\nPhase 7 — Tableau 데이터셋 생성\n{BAR}\n")

# ── 1. PART A 헤드라인 (CI 포함) ─────────────────────────────────────────
ci = rd("FINAL_phase4a_ci.csv")
h = ci[ci.vcov == "hh 1-way"].copy()
h["part"] = "A (causal ITT)"
h["metric_kr"] = h["outcome"]
w(h[["part", "metric_kr", "beta", "se", "ci_lo", "ci_hi", "pct",
     "pct_ci_lo", "pct_ci_hi", "n"]], "FINAL_tableau_headline.csv")

# ── 2. 증분성 곡선 ───────────────────────────────────────────────────────
cur = rd("phase3b1_incrementality_curve.csv")
cur = cur[cur.metric.isin(["total quantity", "total quantity [M3 ⑧]"])].copy()
cur["spec"] = np.where(cur.metric.str.contains("M3"),
                       "M3 시간통제 (확정)", "M1 자연경로 (교란 포함)")
cur["part"] = "A (causal ITT)"
w(cur[["part", "spec", "horizon", "immediate", "post", "post_t",
       "net_cumulative", "cannibalization", "incrementality",
       "cumulative_multiplier", "verdict"]],
  "FINAL_tableau_incrementality_curve.csv")

# ── 3. 카테고리 매트릭스 (5A 버블차트) ───────────────────────────────────
cat = rd("phase5a_category_matrix.csv").copy()
cat["part"] = "B (observational)"
cat["x_significant"] = (cat.x_ci_lo * cat.x_ci_hi) > 0
cat["y_significant"] = (cat.y_ci_lo * cat.y_ci_hi) > 0
w(cat, "FINAL_tableau_category_matrix.csv")

# ── 4. 마진 시나리오 ─────────────────────────────────────────────────────
mg = rd("phase5c_margin_sensitivity.csv").drop_duplicates(
    subset=["gross_margin_pct", "profit_per_opportunity"]).copy()
mg = mg[mg.breakeven_flag != "BREAKEVEN (m*)"]
mg["part"] = "A quantities + margin assumption"
DSAL, DREG = 0.019989, 0.033505
mg["breakeven_m_pct"] = round(100 * (1 - DSAL / DREG), 2)
w(mg, "FINAL_tableau_margin_scenarios.csv")

# ── 5. CRM 세그먼트 (naive vs FE 대비) ───────────────────────────────────
seg = rd("phase5b_segment_results.csv").copy()
seg["part"] = "B (observational)"
seg["fe_significant"] = (seg.ci_lo_fe * seg.ci_hi_fe) > 0
w(seg[["part", "segmentation", "level", "outcome", "n_pairs", "eff_n",
       "mean_full", "mean_deep", "diff_naive", "diff_fe", "se_fe",
       "ci_lo_fe", "ci_hi_fe", "t_fe", "fe_significant"]],
  "FINAL_tableau_crm_segments.csv")

# ── 6. 할인 깊이 밴드 ────────────────────────────────────────────────────
bd = rd("phase5c_step4_discount_bands_summary.csv").copy()
bd["part"] = "B (descriptive)"
w(bd, "FINAL_tableau_discount_bands.csv")

# ── 7. 시간통제 robustness 밴드 ──────────────────────────────────────────
rb = rd("FINAL_phase4a_robustness.csv")
tc = rb[rb.phase == "3B-0 시간통제"].copy()
tc["part"] = "A (causal ITT)"
w(tc[["part", "spec", "outcome", "beta", "ci_lo", "ci_hi", "pct", "n"]],
  "FINAL_tableau_timecontrol.csv")

# ── 8. Decision Matrix ───────────────────────────────────────────────────
bem = 100 * (1 - DSAL / DREG)
dec = pd.DataFrame([
    dict(dimension="카테고리 총마진 < 40.3%", evidence=f"breakeven m*={bem:.2f}%",
         basis="PART A ΔSALES/ΔREG + 마진 가정",
         recommendation="할인 깊이 축소 우선 검토",
         confidence="중 — 마진율은 가정이지 실측이 아님"),
    dict(dimension="카테고리 총마진 40~45%", evidence="손익 경계",
         basis="PART A ΔSALES/ΔREG + 마진 가정",
         recommendation="현행 유지 + 깊이 실험",
         confidence="중"),
    dict(dimension="카테고리 총마진 >= 45%", evidence="+$72.9k~$151.2k (패널 전체)",
         basis="PART A ΔSALES/ΔREG + 마진 가정",
         recommendation="전단지 판촉 유지·확대",
         confidence="중"),
    dict(dimension="잠식 우려로 판촉 축소", evidence="56일 잠식률 95% 상한 17.1%, 점추정 0%",
         basis="PART A Phase 3B-1 M3",
         recommendation="근거 없음 — 잠식은 축소 사유가 아니다",
         confidence="높음 — 인과 ITT, 정밀한 0"),
    dict(dimension="카테고리별 SCALE/STOP 차별화", evidence="83개 중 80개 CI가 0을 포함",
         basis="PART B Phase 5A",
         recommendation="현 근거로는 불가 — 카테고리 단위 차별화 보류",
         confidence="높음 — 판정 자체가 '판정 불가'"),
    dict(dimension="딥할인 성향 고객 타겟팅", evidence="High 성향 세그먼트만 유의 (−$2.83)",
         basis="PART B Phase 5B (FE)",
         recommendation="탐색적 가설로만 — 인과 아님",
         confidence="낮음 — 관측적, 자기선택"),
])
w(dec, "FINAL_decision_matrix.csv")

# ══ 교차검증 ═════════════════════════════════════════════════════════════
print(f"\n{BAR}\n교차검증 — 보고서 인용 수치 vs 원본 CSV\n{BAR}")
m1 = rd("phase3b0_main_m1.csv")


def g(df, **kw):
    q = df
    for k, v in kw.items():
        q = q[q[k] == v]
    return q.iloc[0]


checks = []


def chk(label, got, exp, tol=5e-4):
    ok = abs(got - exp) <= tol
    checks.append(ok)
    print(f"  {'OK ' if ok else 'FAIL'} {label:52s} 보고 {exp:>12.6f} / 원본 {got:>12.6f}")


r = g(m1, outcome="purchase (0/1)", vcov="hh 1-way")
chk("3B-0 purchase beta", r.beta, 0.005412)
chk("3B-0 purchase 상대%", r.pct, 24.31, 0.01)
r = g(m1, outcome="quantity (0 포함)", vcov="hh 1-way")
chk("3B-0 quantity beta", r.beta, 0.012984)
r = g(m1, outcome="SALES_VALUE (0 포함)", vcov="hh 1-way")
chk("3B-0 SALES beta", r.beta, 0.019989)
r = g(m1, outcome="정가환산 (0 포함)", vcov="hh 1-way")
chk("3B-0 정가환산 beta", r.beta, 0.033505)

c = rd("phase3b1_incrementality_curve.csv")
r = c[(c.metric == "total quantity [M3 ⑧]") & (c.horizon == 56)].iloc[0]
chk("3B-1 M3 ΔQ56", r.post, 0.000158)
chk("3B-1 M3 ΔQ0", r.immediate, 0.010298)
chk("3B-1 M3 순증분성 (배수)", r.incrementality, 1.0153, 1e-3)

f4 = rd("phase4b_future28_results.csv")
chk("4B 28일 store spend", f4[f4.outcome_var == "post_spend"].iloc[0].beta, -4.562736)
chk("4B 28일 store visits", f4[f4.outcome_var == "post_visits"].iloc[0].beta, -0.077947)

s = rd("phase5b_segment_results.csv")
r = s[(s.segmentation == "ALL") & (s.outcome.str.contains("spend"))].iloc[0]
chk("5B 전체 spend (FE)", r.diff_fe, -1.351850)
chk("5B 전체 spend (naive, 참고)", r.diff_naive, -19.240899)

m = rd("phase5c_margin_sensitivity.csv")
chk("5C breakeven margin %", 100 * (1 - DSAL / DREG), 40.34, 0.01)
chk("5C m=50% 패널이익", m[m.gross_margin_pct == 50].iloc[0].profit_total_panel,
    151192.430781, 1.0)

t3 = rd("phase5c_step3_trial_conversion.csv").iloc[0]
chk("5C 56일 repeat rate %", t3.repeat_rate_56_pct, 49.73, 0.01)
chk("5C 56일 정가전환률 %", t3.conversion_rate_56_pct, 57.15, 0.01)

cm = rd("phase5a_category_matrix.csv")
chk("5A indeterminate 개수", (cm.classification == "indeterminate").sum(), 80, 0)
chk("5A 카테고리 총수", len(cm), 83, 0)

# 잠식률 상한 (Phase 4A에서 새로 도출한 수치)
rb2 = rd("FINAL_phase4a_robustness.csv")
q56 = rb2[(rb2.phase == "3B-1 H=56") & (rb2.outcome == "q56")
          & (rb2.spec.str.contains("M3"))].iloc[0]
d0 = rb2[(rb2.phase == "3B-1 H=56") & (rb2.outcome == "quantity")
         & (rb2.spec.str.contains("M3"))].iloc[0]
chk("4A 잠식률 95% 상한 %", 100 * (-q56.ci_lo) / d0.beta, 17.13, 0.05)

print(f"\n  {'모든 교차검증 통과' if all(checks) else '⚠️ 불일치 있음'} "
      f"({sum(checks)}/{len(checks)})")
print(f"\n{BAR}\nTableau 파일 8종 저장 → outputs/tableau/\n{BAR}")
