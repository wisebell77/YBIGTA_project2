"""Phase 4A — 저장된 결과만으로 robustness 정리 + 95% CI 산출

⚠️ 새 대규모 회귀를 실행하지 않는다. 이미 저장된 CSV만 읽는다.
   (Cox/AFT, 28일 M3, store×cat+WEEK 87분 스펙은 오늘 실행 대상이 아니다)

산출:
  outputs/tables/FINAL_phase4a_robustness.csv   — 스펙별 beta/SE/t/95%CI 통합표
  outputs/tables/FINAL_phase4a_ci.csv           — 주 결과 95% CI (상대% 기준 포함)
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
Z = 1.959964            # 가구 클러스터 2,485개 → t(2484) ≈ 정규분포
BAR = "=" * 104


def rd(name):
    return pd.read_csv(os.path.join(T, name))


def ci(beta, se):
    return beta - Z * se, beta + Z * se


rows = []


def add(part, phase, outcome, spec, vcov, beta, se, t, base, n, note=""):
    lo, hi = ci(beta, se)
    rows.append(dict(
        part=part, phase=phase, outcome=outcome, spec=spec, vcov=vcov,
        beta=beta, se=se, t=t, ci_lo=lo, ci_hi=hi,
        base_unexposed=base,
        pct=100 * beta / base if base else np.nan,
        pct_ci_lo=100 * lo / base if base else np.nan,
        pct_ci_hi=100 * hi / base if base else np.nan,
        n=n, sig="yes" if lo * hi > 0 else "no", note=note))


# ── 1. Phase 3B-0 주 결과 (M1, 1-way / 2-way) ────────────────────────────
m1 = rd("phase3b0_main_m1.csv")
for _, r in m1.iterrows():
    cond = "조건부" in str(r["spec"])
    add("A", "3B-0", r["outcome"], r["spec"], r["vcov"],
        r["beta"], r["se"], r["t"], r["base"], r["n"],
        "구매기회 단위" if not cond else "구매 발생 occasion만(조건부)")

# ── 2. Phase 3B-0 시간통제 (①②③⑤⑥⑧) ──────────────────────────────────
tc = rd("phase3b0_timecontrol.csv")
BASE = {"purchase": 0.022263635935351946,
        "quantity": 0.03772875623327554,
        "SALES_VALUE": 0.07652074843093352}
for _, r in tc.iterrows():
    add("A", "3B-0 시간통제", r["outcome"], r["spec"], "hh 1-way",
        r["beta"], r["se"], r["t"], BASE[r["outcome"]], r["n"],
        f"흡수율 {r['absorb']}%" if pd.notna(r.get("absorb")) else "")

# ── 3. Phase 3B-1 미래효과 ───────────────────────────────────────────────
fut = rd("phase3b1_future.csv")
for _, r in fut.iterrows():
    add("A", f"3B-1 H={r['horizon']}", r["outcome"], r["spec"], r["vcov"],
        r["beta"], r["se"], r["t"], r["base_unexposed"], r["n"], r["sample"])

# ── 4. Phase 3A (occasion 패널, 조건부) ──────────────────────────────────
try:
    cs = rd("phase3a_clusterse.csv")
    for _, r in cs.iterrows():
        if pd.notna(r["beta"]) and pd.notna(r["se"]):
            add("A", "3A occasion", r["outcome"], r["spec"], r["vcov"],
                r["beta"], r["se"], r["t"], r["base"], r["n"], "조건부 효과")
except Exception as e:
    print(f"  (phase3a_clusterse 건너뜀: {e})")

# ── 5. PDF 딥할인 보조설계 (PART B 성격 — 관측적) ────────────────────────
try:
    dd = rd("phase3a_pdf_deepdisc.csv")
    for _, r in dd.iterrows():
        add("B", "3A 딥할인(참고)", r["outcome"], r["model"], "hh 1-way",
            r["beta"], r["se"], r["t"], r["base"], r["n"],
            "⚠️ 관측적 — 인과 아님")
except Exception as e:
    print(f"  (phase3a_pdf_deepdisc 건너뜀: {e})")

out = pd.DataFrame(rows)
out.to_csv(os.path.join(T, "FINAL_phase4a_robustness.csv"),
           index=False, encoding="utf-8-sig")

# ── 출력 ─────────────────────────────────────────────────────────────────
print(f"{BAR}\nPhase 4A — robustness 통합 ({len(out)}행) · 95% CI = beta ± 1.96·SE\n{BAR}")

print(f"\n■ PART A 주 결과 (Phase 3B-0 M1 hh×cat, 구매기회 단위)\n")
print(f"{'결과변수':22s} {'SE방식':14s} {'beta':>11s} {'95% CI':>24s} "
      f"{'상대%':>8s} {'상대% CI':>18s}")
main = out[(out.phase == "3B-0") & (out.note == "구매기회 단위")]
for _, r in main.iterrows():
    print(f"{r.outcome:22s} {r.vcov:14s} {r.beta:+11.6f} "
          f"[{r.ci_lo:+9.6f},{r.ci_hi:+9.6f}] {r.pct:+7.2f}% "
          f"[{r.pct_ci_lo:+7.2f},{r.pct_ci_hi:+7.2f}]")

print(f"\n■ 시간통제 robustness (purchase / quantity)\n")
print(f"{'통제':26s} {'결과변수':12s} {'beta':>11s} {'95% CI':>24s} {'상대%':>8s}")
for oc in ("purchase", "quantity"):
    sub = out[(out.phase == "3B-0 시간통제") & (out.outcome == oc)]
    for _, r in sub.iterrows():
        print(f"{r.spec:26s} {r.outcome:12s} {r.beta:+11.6f} "
              f"[{r.ci_lo:+9.6f},{r.ci_hi:+9.6f}] {r.pct:+7.2f}%")
    print()

print(f"■ 1-way vs 2-way cluster SE 비교 (Phase 3B-0 M1)\n")
print(f"{'결과변수':22s} {'1-way SE':>10s} {'2-way SE':>10s} {'배수':>7s} "
      f"{'1-way t':>9s} {'2-way t':>9s}")
for oc in main.outcome.unique():
    a = main[(main.outcome == oc) & (main.vcov == "hh 1-way")]
    b = main[(main.outcome == oc) & (main.vcov == "hh+store×cat")]
    if len(a) and len(b):
        a, b = a.iloc[0], b.iloc[0]
        print(f"{oc:22s} {a.se:10.6f} {b.se:10.6f} {b.se/a.se:7.3f} "
              f"{a.t:9.2f} {b.t:9.2f}")

print(f"\n■ Phase 3B-1 핵심 (56일)\n")
key = out[(out.phase == "3B-1 H=56") & (out.outcome.isin(["q56", "quantity"]))
          & (out["sample" if "sample" in out else "note"] == "full")]
print(f"{'결과':12s} {'스펙':24s} {'beta':>11s} {'95% CI':>24s} {'유의':>5s}")
for _, r in key.iterrows():
    print(f"{r.outcome:12s} {r.spec:24s} {r.beta:+11.6f} "
          f"[{r.ci_lo:+9.6f},{r.ci_hi:+9.6f}] {r.sig:>5s}")

# 주 결과 CI 요약 파일
main[["outcome", "vcov", "beta", "se", "ci_lo", "ci_hi", "pct",
      "pct_ci_lo", "pct_ci_hi", "n"]].to_csv(
    os.path.join(T, "FINAL_phase4a_ci.csv"), index=False, encoding="utf-8-sig")
print(f"\n저장: FINAL_phase4a_robustness.csv ({len(out)}행) / FINAL_phase4a_ci.csv")
