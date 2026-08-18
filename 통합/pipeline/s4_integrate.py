"""s4 — 통합 단계: 삼각측량 · 의사결정 매트릭스 · 고객 축 교차표

이전 버전(통합/build_integration.py)은 개인 폴더의 결과 CSV를 이어붙였다.
이 버전은 **이 파이프라인의 산출물만으로** 같은 표를 만든다 — 즉 표준 정의 하에서
전 단계가 자체 재현된 결과의 통합이다.

  입력: s2_category_verdict / s2_halo_category / s2_household_quintile
        s3_downstream28_category / s3_household_affinity
  출력: s4_triangulation.csv / s4_decision_matrix.csv / s4_household_axis.csv
"""
import os
import numpy as np, pandas as pd
from standards import OUT

log = []
say = lambda s: log.append(str(s))

ver = pd.read_csv(os.path.join(OUT, "s2_category_verdict.csv"), encoding="utf-8-sig")
halo = pd.read_csv(os.path.join(OUT, "s2_halo_category.csv"), encoding="utf-8-sig")
down = pd.read_csv(os.path.join(OUT, "s3_downstream28_category.csv"), encoding="utf-8-sig")

# ── 삼각측량: 당일 ITT(±halo) × 28일 하류 ─────────────────────────
tri = (ver[["category", "n_pairs", "verdict", "net_now", "t_net", "net_pct",
            "qty_pct", "elasticity", "significant_bh", "net_later", "t_cann"]]
       .merge(halo[["category", "halo_eff", "t_halo", "basket_total", "t_basket"]],
              on="category", how="left")
       .merge(down[["category", "visit28_diff", "t_visit", "spend28_diff",
                    "t_spend", "quadrant"]], on="category", how="left"))
tri.to_csv(os.path.join(OUT, "s4_triangulation.csv"), index=False, encoding="utf-8-sig")
say(f"[삼각측량] 카테고리 {len(tri)}개 / 하류 매칭 {tri.quadrant.notna().sum()}개")

# ── 의사결정 매트릭스 ─────────────────────────────────────────────
# 신뢰도 규칙 (엄격): 1축 = 당일 순수취(BH 유의), 2축 = 확증 축.
#   2축 후보 (a) 장바구니 합계(halo 포함, t_basket)  (b) 28일 하류 지출(t_spend)
#   '상' = 1축 유의 + 2축 중 하나 이상이 |t|>=1.96 으로 같은 방향
#   '중' = 1축 유의, 2축은 방향만 일치(비유의)
#   '하' = 1축 비유의
# 하류 28일 지출은 137개 중 7개만 유의할 만큼 노이즈가 크다. 부호(사분면)만으로
# '정합'을 선언하면 노이즈를 확증으로 포장하게 되므로 반드시 유의성을 요구한다.
def decide(r):
    v = r.verdict
    def sig(t, sign):
        return pd.notna(t) and (t >= 1.96 if sign > 0 else t <= -1.96)
    conf_up = sig(r.t_basket, +1) or sig(r.t_spend, +1)
    conf_dn = sig(r.t_basket, -1) or sig(r.t_spend, -1)
    dir_up = (pd.notna(r.basket_total) and r.basket_total > 0) or r.quadrant == "Q1 강화"
    dir_dn = (pd.notna(r.basket_total) and r.basket_total < 0) or r.quadrant == "Q4 약화"
    if v == "확대":
        if conf_up: return "확대 — 최우선", "상"
        if conf_dn: return "확대하되 온보딩 설계", "중"
        return ("확대", "중") if dir_up else ("확대 — 관찰 병행", "중")
    if v == "축소":
        if conf_dn: return "축소 — 최우선", "상"
        if conf_up: return "축소 보류 — 실험", "중"
        return ("할인 깊이 축소", "중") if dir_dn else ("할인 깊이 축소 — 관찰 병행", "중")
    if conf_up: return "소규모 확대 실험", "하"
    if conf_dn: return "현행 유지·관찰", "하"
    return "보류", "하"

acts = tri.apply(decide, axis=1, result_type="expand")
acts.columns = ["action", "confidence"]
mat = pd.concat([tri, acts], axis=1).sort_values(["confidence", "net_now"],
                                                 ascending=[True, False])
mat.to_csv(os.path.join(OUT, "s4_decision_matrix.csv"), index=False, encoding="utf-8-sig")
hi = mat[mat.confidence == "상"]
say(f"[매트릭스] 액션 {acts.action.value_counts().to_dict()}")
say(f"    2축 유의성: 장바구니 {int((tri.t_basket.abs()>=1.96).sum())}/{len(tri)} · "
    f"28일하류 {int((tri.t_spend.abs()>=1.96).sum())}/{int(tri.t_spend.notna().sum())}")
say(f"    신뢰도 '상' {len(hi)}개: " +
    ", ".join(f"{r.category}({r.action.split(' ')[0]})" for r in hi.itertuples()))

# ── 고객 축 교차표 ────────────────────────────────────────────────
dd = pd.read_csv(os.path.join(OUT, "s2_household_quintile.csv"), encoding="utf-8-sig")
af = pd.read_csv(os.path.join(OUT, "s3_household_affinity.csv"), encoding="utf-8-sig")
m = dd.merge(af, on="household_key")
m["affinity_q"] = pd.qcut(m.affinity, 5, labels=[1, 2, 3, 4, 5]).astype(int)
ct = pd.crosstab(m.quintile, m.affinity_q,
                 rownames=["할인의존도(배분단계)"], colnames=["할인친화도(하류단계)"])
rho = m[["quintile", "affinity_q"]].corr(method="spearman").iloc[0, 1]
same = (m.quintile == m.affinity_q).mean()
near = (abs(m.quintile - m.affinity_q) <= 1).mean()
ct.reset_index().to_csv(os.path.join(OUT, "s4_household_axis.csv"),
                        index=False, encoding="utf-8-sig")
say(f"[고객 축] Spearman {rho:.3f} / 동일 분위 {same:.1%} / ±1 이내 {near:.1%} "
    f"({len(m):,}가구) — 이전(개인 결과 결합) 0.838 / 58.7% / 93.8%")

with open(os.path.join(OUT, "s4_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s4 DONE")
