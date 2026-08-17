"""Phase 8 — 최종 핵심수치표 + Decision Matrix 생성 및 교차검증 (후처리 전용)

⚠️ 새 회귀·스캔 없음. 저장된 CSV만 읽는다.
산출:
  outputs/tables/FINAL_key_results.csv
  outputs/tableau/07_final_decision_matrix.csv
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
BAR = "=" * 104


def rd(n, d=T):
    return pd.read_csv(os.path.join(d, n))


m1 = rd("phase3b0_main_m1.csv")
tc = rd("phase3b0_timecontrol.csv")
cur = rd("phase3b1_incrementality_curve.csv")
rb = rd("FINAL_phase4a_robustness.csv")
f4 = rd("phase4b_future28_results.csv")
s5b = rd("phase5b_rfm_segments.csv")
mg = rd("phase5c_margin_sensitivity.csv")
t3 = rd("phase5c_step3_trial_conversion.csv").iloc[0]
bd = rd("phase5c_step4_discount_bands_summary.csv")
p5a = rd("phase5a_category_portfolio.csv")
fdr5a = rd("phase5a_fdr_summary.csv")
fdr5b = rd("phase5b_fdr_summary.csv")


def one(df, **kw):
    q = df
    for k, v in kw.items():
        q = q[q[k] == v]
    return q.iloc[0]


DSAL = one(m1, outcome="SALES_VALUE (0 포함)", vcov="hh 1-way").beta
DREG = one(m1, outcome="정가환산 (0 포함)", vcov="hh 1-way").beta
bem = 100 * (1 - DSAL / DREG)

m3_56 = cur[(cur.metric == "total quantity [M3 ⑧]") & (cur.horizon == 56)].iloc[0]
q56 = rb[(rb.phase == "3B-1 H=56") & (rb.outcome == "q56")
         & (rb.spec.str.contains("M3"))].iloc[0]
d0m3 = rb[(rb.phase == "3B-1 H=56") & (rb.outcome == "quantity")
          & (rb.spec.str.contains("M3"))].iloc[0]
bound = 100 * (-q56.ci_lo) / d0m3.beta

allspend = one(s5b, segmentation="ALL", outcome="future 28d store spend")

K = []


def add(no, name, value, unit, part, source, note="", onepage=False):
    K.append(dict(no=no, metric=name, value=value, unit=unit, part=part,
                  source=source, note=note, on_onepage=onepage))


r = one(m1, outcome="purchase (0/1)", vcov="hh 1-way")
add(1, "구매확률 증가", round(r.pct, 2), "%", "A (causal ITT)",
    "phase3b0_main_m1.csv", "hh×cat FE, hh cluster SE", True)
r = one(m1, outcome="quantity (0 포함)", vcov="hh 1-way")
add(2, "총수량 증가 (0구매 포함)", round(r.pct, 2), "%", "A (causal ITT)",
    "phase3b0_main_m1.csv", "주 스펙 M1", True)
r8 = one(tc, spec="⑧ + cat×month + WEEK", outcome="quantity")
add(3, "강한 시간통제 수량효과", round(r8.pct, 2), "%", "A (causal ITT)",
    "phase3b0_timecontrol.csv", "⑧ cat×month+WEEK — 하한", True)
r = one(m1, outcome="SALES_VALUE (0 포함)", vcov="hh 1-way")
add(4, "실제 매출 증가", round(r.pct, 2), "%", "A (causal ITT)",
    "phase3b0_main_m1.csv", "", True)
r = one(m1, outcome="정가환산 (0 포함)", vcov="hh 1-way")
add(5, "정가환산 증가", round(r.pct, 2), "%", "A (causal ITT)",
    "phase3b0_main_m1.csv", "", True)
gap = one(m1, outcome="정가환산 (0 포함)", vcov="hh 1-way").pct - \
      one(m1, outcome="SALES_VALUE (0 포함)", vcov="hh 1-way").pct
add(6, "value-to-revenue gap", round(gap, 2), "%p", "A (causal ITT)",
    "phase3b0_main_m1.csv",
    "정가환산 증가율 − 실제 매출 증가율. margin loss가 아님", True)
add(7, "총수량 증가 중 extensive-margin 근사 기여", 70.6, "%", "A (causal ITT)",
    "01_phase3b0_report.md §4", "근사 분해 — 잔차 9.8% 존재", False)
add(8, "56일 future quantity (M3)", round(float(m3_56.post), 6), "units/기회",
    "A (causal ITT)", "phase3b1_incrementality_curve.csv",
    f"t={float(m3_56.post_t):.2f} — significant payback 없음", True)
add(9, "점추정 기준 cumulative ratio", round(100 * float(m3_56.incrementality), 1),
    "% (point-estimate only)", "A (causal ITT)",
    "phase3b1_incrementality_curve.csv",
    "⚠️ 헤드라인 사용 금지 — 점추정 기준 참고값", False)
add(10, "Approx. CI-implied payback bound", round(bound, 1), "%",
    "A (causal ITT)", "FINAL_phase4a_robustness.csv",
    "ΔQ0 고정 근사 환산. formal equivalence test 아님", True)
add(11, "gross-margin scenario break-even", round(bem, 2), "%",
    "A 량 + 마진 가정", "phase5c_margin_sensitivity.csv",
    "원가·vendor funding·운영비 미반영 단순 scenario", True)
add(12, "회수율 ΔSALES/ΔREG", round(100 * DSAL / DREG, 2), "%",
    "A (causal ITT)", "phase3b0_main_m1.csv", "", False)
r = f4[f4.outcome_var == "post_spend"].iloc[0]
add(13, "4B 28일 whole-store spend association", round(r.beta, 2), "$",
    "B (observational)", "phase4b_future28_results.csv",
    f"{r.pct_diff:.2f}% — 관측적, 인과 아님", True)
add(14, "5B naive → FE 축소", 93, "% 축소", "B (observational)",
    "phase5b_rfm_segments.csv",
    f"naive {allspend.diff_naive:.2f} → FE {allspend.diff_fe:.2f}", True)
add(15, "5B 전체 future spend (FE)", round(allspend.diff_fe, 2), "$",
    "B (observational)", "phase5b_rfm_segments.csv",
    f"t={allspend.t_fe:.2f}", False)
add(16, "첫 딥할인 후 28일 재구매율", float(t3.repeat_rate_28_pct), "%",
    "B (descriptive)", "phase5c_step3_trial_conversion.csv", "", False)
add(17, "첫 딥할인 후 56일 재구매율", float(t3.repeat_rate_56_pct), "%",
    "B (descriptive)", "phase5c_step3_trial_conversion.csv", "", True)
add(18, "재구매 중 정가 전환율 (56일)", float(t3.conversion_rate_56_pct), "%",
    "B (descriptive)", "phase5c_step3_trial_conversion.csv", "", True)
lo, hi = bd.iloc[0], bd.iloc[-1]
add(19, "정가 전환율: 얕은(<20%) → 깊은(40%+) 할인",
    f"{lo.conversion_to_regular_pct} → {hi.conversion_to_regular_pct}", "%",
    "B (descriptive)", "phase5c_step4_discount_bands_summary.csv",
    "밴드는 자기선택 — 인과 아님", True)
add(20, "5A FDR 후 robust category", 0, "개 (83개 중)", "B (observational)",
    "phase5a_fdr_summary.csv", "BH q<0.05, 최소 q=0.065", True)
add(21, "5B FDR 후 robust segment (지표별)", 6, "개 (17개 중)",
    "B (observational)", "phase5b_fdr_summary.csv",
    "visits·spend 양쪽 모두 6개 — 전부 High 세그먼트", True)

kdf = pd.DataFrame(K)
kdf.to_csv(os.path.join(T, "FINAL_key_results.csv"),
           index=False, encoding="utf-8-sig")

# ── Decision Matrix ──────────────────────────────────────────────────────
n_rob5a = int((p5a.classification_fdr.isin(
    ["robust strengthening", "robust weakening"])).sum())
n_rob5b = int(fdr5b.n_fdr.min())

DEC = [
    dict(no=1, topic="56일 payback 우려",
         conclusion="큰 미래수요 잠식 근거 없음",
         evidence=f"M3 ΔQ56={float(m3_56.post):+.6f}, t={float(m3_56.post_t):.2f}; "
                  f"CI 단순환산 payback bound ≈{bound:.1f}%",
         part="A (causal ITT)", confidence="높음",
         action="잠식을 판촉 축소 사유로 쓰지 않는다"),
    dict(no=2, topic="전체 판촉 수요효과",
         conclusion="purchase / quantity 증가",
         evidence="구매확률 +24.31%, 총수량 +34.41% (강한 시간통제 시 +26.97%)",
         part="A (causal ITT)", confidence="높음",
         action="증분수요 자체는 유지 대상"),
    dict(no=3, topic="gross-margin < 40.3% scenario",
         conclusion="경제성 재검토 / 할인 깊이 축소 후보",
         evidence=f"단순 scenario break-even ≈{bem:.2f}%",
         part="A 량 + 마진 가정", confidence="중",
         action="실제 원가·vendor funding 확보 후 재평가"),
    dict(no=4, topic="gross-margin 40.3~45%",
         conclusion="경제성 민감구간 / 실제 원가정보 필요",
         evidence="scenario 상 손익 부호가 가정에 민감",
         part="A 량 + 마진 가정", confidence="중",
         action="원가정보 확보 우선"),
    dict(no=5, topic="gross-margin >= 45%",
         conclusion="단순 scenario상 상대적으로 경제성 우호적",
         evidence="m=45% +$72,933 / m=50% +$151,192 (패널 전체)",
         part="A 량 + 마진 가정", confidence="중",
         action="유지 후보 — 단, 운영비·vendor funding 미반영"),
    dict(no=6, topic="category SCALE/STOP",
         conclusion="현재 데이터만으로 세밀한 category SCALE/STOP 보류",
         evidence=f"83개 중 FDR 후 robust category {n_rob5a}개 (최소 q=0.065). "
                  f"명목 유의 10개는 다중검정 후 전부 소멸",
         part="B (observational)", confidence="높음",
         action="카테고리 단위 차별화 보류, 필요시 실험 설계"),
    dict(no=7, topic="고객 segment targeting",
         conclusion="제한적 targeting 후보 — 단 exploratory",
         evidence=f"FDR 후에도 High 세그먼트 {n_rob5b}개가 visits·spend 양쪽에서 q<0.05 유지",
         part="B (observational)", confidence="낮음~중",
         action="자기선택 가능성 있음 — 실험으로 검증 후 적용"),
    dict(no=8, topic="discount depth",
         conclusion="깊은 할인은 더 많은 물량과 함께 낮은 realized revenue 및 "
                    "낮은 정상가 전환과 연관",
         evidence=f"수량 {lo.avg_quantity}→{hi.avg_quantity}, "
                  f"SALES ${lo.avg_sales}→${hi.avg_sales}, "
                  f"정가전환 {lo.conversion_to_regular_pct}%→{hi.conversion_to_regular_pct}%",
         part="B (descriptive)", confidence="낮음~중 (자기선택)",
         action="할인 깊이 축소가 1순위 실험 대상"),
]
ddf = pd.DataFrame(DEC)
ddf.to_csv(os.path.join(TAB, "07_final_decision_matrix.csv"),
           index=False, encoding="utf-8-sig")

print(f"{BAR}\n최종 핵심수치 {len(kdf)}개 / Decision Matrix {len(ddf)}행 저장\n{BAR}")
print(kdf[["no", "metric", "value", "unit", "part"]].to_string(index=False))

# ══ 교차검증 ═════════════════════════════════════════════════════════════
print(f"\n{BAR}\n교차검증 — 최종 문서 인용 수치 vs source CSV\n{BAR}")
ok = []


def chk(lab, got, exp, tol=5e-3):
    good = abs(float(got) - exp) <= tol
    ok.append(good)
    print(f"  {'OK ' if good else 'FAIL'} {lab:44s} 문서 {exp:>12.5f} / CSV {float(got):>12.5f}")


chk("purchase 24.31", one(m1, outcome="purchase (0/1)", vcov="hh 1-way").pct, 24.31)
chk("quantity 34.41", one(m1, outcome="quantity (0 포함)", vcov="hh 1-way").pct, 34.41)
chk("time-controlled quantity 26.97", r8.pct, 26.97)
chk("SALES 26.12", one(m1, outcome="SALES_VALUE (0 포함)", vcov="hh 1-way").pct, 26.12)
chk("REG 39.52", one(m1, outcome="정가환산 (0 포함)", vcov="hh 1-way").pct, 39.52)
chk("value-to-revenue gap 13.40", gap, 13.40)
chk("56d M3 +0.000158", m3_56.post, 0.000158, 1e-6)
chk("approx payback bound 17.1", bound, 17.13, 0.05)
chk("scenario break-even 40.34", bem, 40.34, 0.01)
chk("4B -4.56", f4[f4.outcome_var == "post_spend"].iloc[0].beta, -4.5627, 1e-3)
chk("5B FE -1.35", allspend.diff_fe, -1.3519, 1e-3)
chk("28d repeat 33.55", t3.repeat_rate_28_pct, 33.55)
chk("56d repeat 49.73", t3.repeat_rate_56_pct, 49.73)
chk("regular-price conversion 57.15", t3.conversion_rate_56_pct, 57.15)
chk("5A FDR robust = 0", n_rob5a, 0, 0)
chk("5A nominal visits = 10", fdr5a.iloc[0].n_nominal, 10, 0)
chk("5A FDR visits = 0", fdr5a.iloc[0].n_fdr, 0, 0)
chk("5B FDR visits = 6", fdr5b.iloc[0].n_fdr, 6, 0)
chk("5B FDR spend = 6", fdr5b.iloc[1].n_fdr, 6, 0)

print(f"\n  {'전부 통과' if all(ok) else '⚠️ 불일치'} ({sum(ok)}/{len(ok)})")

# ── 교차검증 게이트 ────────────────────────────────────────────────────
# 위 기대값은 원 full run 의 확정 수치다. smoke 는 소표본이라 일치할 수 없으므로
# 비교 자체가 무의미하다(PART 20: smoke 를 full estimate 와 비교하지 않는다).
# full run 에서는 불일치 시 non-zero 로 종료해 파이프라인을 중단시킨다.
import os as _os

if _os.environ.get("DUNNHUMBY_SMOKE") == "1":
    print("  (SMOKE — 기대값은 full run 기준이므로 비교 결과를 무시하고 계속 진행합니다)")
elif not all(ok):
    print("  ✗ full run 교차검증 실패 — 산출물이 확정 수치와 다릅니다.")
    sys.exit(1)
