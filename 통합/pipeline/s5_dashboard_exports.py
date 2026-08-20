"""s5 — 대시보드 export 단계. 새 통계분석 없음 — s1~s4가 이미 계산한 결과를
Tableau가 바로 읽을 수 있는 형태로 정리만 한다 (컬럼명·라벨 정리, t→95% CI 역산,
크로스탭 long-format 변환).

  입력: s1_itt / s1_payback56 / s2_quintile_heterogeneity / s3_sameday /
        s3_trial_conversion / s3_downstream28_category / s3c_segment_summary /
        s3c_segment_role_crosstab / s4_decision_matrix / s4_household_axis
  출력: ../outputs/dashboard_*.csv (총 9개)
"""
import os
import numpy as np, pandas as pd
from standards import OUT

log = []
say = lambda s: log.append(str(s))


def ci(est, t, z=1.96):
    """t = est/SE 이므로 SE = est/t 로 역산해 95% CI를 만든다."""
    se = est / t.replace(0, np.nan)
    return est - z * se, est + z * se


def read(name):
    return pd.read_csv(os.path.join(OUT, f"{name}.csv"), encoding="utf-8-sig")


def write(df, name):
    df.to_csv(os.path.join(OUT, f"dashboard_{name}.csv"), index=False, encoding="utf-8-sig")
    say(f"[{name}] {len(df)}행 → dashboard_{name}.csv")


# ── 1. 헤드라인 KPI (2절) ──────────────────────────────────────────
itt = read("s1_itt")
itt = itt[itt["mode"] == "standard"].copy()
OUTCOME_KR = {"purchase": "구매확률", "qty": "총수량(0구매 포함)",
              "net": "실제 매출", "gross": "정가환산"}
SORT = {"purchase": 1, "qty": 2, "net": 3, "gross": 4}
itt["outcome_kr"] = itt["outcome"].map(OUTCOME_KR)
itt["sort_order"] = itt["outcome"].map(SORT)
itt["ci_low"], itt["ci_high"] = ci(itt["pct"], itt["t"])
write(itt.sort_values("sort_order")[["outcome_kr", "pct", "t", "ci_low", "ci_high",
                                     "sort_order"]], "kpi_summary")

# ── 2. 56일 미래수요 잠식 (2.1절) ──────────────────────────────────
pay = read("s1_payback56")
SPEC_KR = {"legacy(검증)": "pair FE만 (naive)", "standard": "+ WEEK, cat×월 FE"}
pay["spec_kr"] = pay["mode"].map(SPEC_KR)
write(pay[["spec_kr", "beta", "t"]], "payback56")

# ── 3. 카테고리 포트폴리오 (3.1·3.3·5절) ───────────────────────────
dm = read("s4_decision_matrix")
CONF_RANK = {"상": 1, "중": 2, "하": 3}
dm["confidence_rank"] = dm["confidence"].map(CONF_RANK)
dm["net_now_ci_low"], dm["net_now_ci_high"] = ci(dm["net_now"], dm["t_net"])
dm["basket_total_ci_low"], dm["basket_total_ci_high"] = ci(dm["basket_total"], dm["t_basket"])
dm["spend28_ci_low"], dm["spend28_ci_high"] = ci(dm["spend28_diff"], dm["t_spend"])
write(dm, "category_portfolio")

# ── 4. 고객 이질성 — 할인의존도 5분위 (3.2절) ──────────────────────
q = read("s2_quintile_heterogeneity")
Q_KR = {1: "Q1 비의존", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 최다의존"}
q["quintile_kr"] = q["quintile"].map(Q_KR)
q["ci_low"], q["ci_high"] = ci(q["net_pct"], q["t_net"])
q["net_usd_ci_low"], q["net_usd_ci_high"] = ci(q["net_usd"], q["t_net"])
write(q, "customer_quintile")

# ── 5. 고객 축 교차표 — 할인의존도 × 할인친화도 (5.3절) ────────────
ax = read("s4_household_axis")
ax_long = ax.melt(id_vars="할인의존도(배분단계)", var_name="할인친화도(하류단계)",
                  value_name="households")
write(ax_long, "household_axis")

# ── 6. CRM 세그먼트 요약 (3.4절) ───────────────────────────────────
seg = read("s3c_segment_summary")
PRIORITY = {"S2 관계강화형": 1, "S1 재고비축형": 2, "S5 반응불분명형": 3,
            "S3 장바구니재편형": 4, "S4 전단지의존형": 5}
seg["priority_rank"] = seg["segment"].map(PRIORITY).fillna(9).astype(int)
write(seg, "segment_summary")

# ── 7. 세그먼트 × 카테고리 역할 교차표 (3.4절) ─────────────────────
write(read("s3c_segment_role_crosstab"), "segment_role_crosstab")

# ── 8. 당일 고할인 vs 정가, 체험 전환 (4.1·4.3절) ──────────────────
sd = read("s3_sameday")
sd = sd[sd["mode"] == "standard"].copy()
write(sd[["qty", "t_qty", "spend", "t_spend", "reg", "t_reg", "gap", "t_gap"]], "sameday")

tc = read("s3_trial_conversion")
tc["first_kr"] = tc["deep_first"].map({1: "고할인", 0: "비고할인"})
write(tc[["first_kr", "n", "any_rep_pct", "reg_rep_pct"]], "trial_conversion")

# ── 9. 카테고리별 28일 하류 (4절 관련, 3.1 확장) ───────────────────
d28 = read("s3_downstream28_category")
d28["visit28_ci_low"], d28["visit28_ci_high"] = ci(d28["visit28_diff"], d28["t_visit"])
d28["spend28_ci_low"], d28["spend28_ci_high"] = ci(d28["spend28_diff"], d28["t_spend"])
write(d28, "category_downstream28")

with open(os.path.join(OUT, "s5_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s5 DONE")
