"""팀 통합 산출물 생성기.

세 사람의 분석을 잇는 브리지 테이블 3종을 만든다. 각자의 코드는 그대로 두고
(설계가 다른 것이 삼각측량이라는 강점이므로), 이미 커밋된 결과 CSV와 원본
데이터만으로 통합 표를 생성한다.

  01_category_triangulation.csv  카테고리 삼각측량 (남궁현종 ITT × 전영찬 하류 관계)
  02_decision_matrix.csv         최종 의사결정 매트릭스 (액션 + 신뢰도)
  03_household_axis_crosstab.csv 고객 축 교차표 (할인의존도 × 할인친화도)

실행: python 통합/build_integration.py   (저장소 루트 또는 통합/ 에서)
03은 data/ 의 원본 CSV가 필요하다. 없으면 01·02만 생성하고 건너뛴다.
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P_OURS = os.path.join(ROOT, "남궁현종", "산출물", "tableau")
P_JYC = os.path.join(ROOT, "전영찬", "tableau_data")
DATA = os.path.join(ROOT, "data")

log = []


def say(s):
    log.append(s)


# ══════════════════════════════════════════════════════════════════
# 01. 카테고리 삼각측량
#   남궁현종: 전단지 ITT 당일 순수취액 + halo(장바구니 합계)  — "단기 수익" 축
#   전영찬  : 딥할인 후 28일 매장 방문·전체 지출 변화        — "장기 관계" 축
#   장준한  : 카테고리 개별 판정은 FDR 후 0/83 (관측 설계) → 표에는 각주로만.
# ══════════════════════════════════════════════════════════════════
ours = pd.read_csv(os.path.join(P_OURS, "tableau_category_decision.csv"), encoding="utf-8-sig")
jyc = pd.read_csv(os.path.join(P_JYC, "tableau_category_kpi.csv"), encoding="utf-8-sig")

jyc = jyc.rename(columns={
    "COMMODITY_DESC": "category",
    "visit_diff": "jyc_visit28_diff", "visit_se": "jyc_visit28_se",
    "spend_diff": "jyc_spend28_diff", "spend_se": "jyc_spend28_se",
    "performance_quadrant": "jyc_quadrant",
    "households": "jyc_households",
})
jyc["jyc_spend28_sig"] = (jyc.jyc_spend28_diff.abs() > 1.96 * jyc.jyc_spend28_se)
jyc["jyc_visit28_sig"] = (jyc.jyc_visit28_diff.abs() > 1.96 * jyc.jyc_visit28_se)

tri = ours.merge(
    jyc[["category", "jyc_households", "jyc_visit28_diff", "jyc_visit28_sig",
         "jyc_spend28_diff", "jyc_spend28_sig", "jyc_quadrant"]],
    on="category", how="left")

say(f"[01] 우리 72개 카테고리 중 전영찬 표와 매칭 {tri.jyc_quadrant.notna().sum()}개 "
    f"(전영찬 전체 {len(jyc)}개)")

tri.to_csv(os.path.join(HERE, "01_category_triangulation.csv"),
           index=False, encoding="utf-8-sig")


# ══════════════════════════════════════════════════════════════════
# 02. 최종 의사결정 매트릭스
#   규칙(투명하게 코드로 고정):
#     단기 축 = 우리 verdict (확대/축소/불확실)
#     장기 축 = 전영찬 quadrant (Q1 강화 / Q4 약화 / 그 외 혼합)
# ══════════════════════════════════════════════════════════════════
def decide(r):
    v = r["verdict"]
    q = r["jyc_quadrant"] if isinstance(r["jyc_quadrant"], str) else None
    sig = bool(r["jyc_spend28_sig"]) if r["jyc_spend28_sig"] == r["jyc_spend28_sig"] else False
    sp = r["jyc_spend28_diff"]
    # 하류 신호: 사분면 라벨 또는 개별 유의한 28일 지출 변화 (유의 시 우선)
    up = (sig and sp > 0) or q == "Q1 Relationship strengthened"
    dn = (sig and sp < 0) or q == "Q4 Relationship weakened"
    if v == "확대":
        if up:
            return ("확대 — 최우선", "상", "당일 순수취 + 28일 관계 모두 양호 (2설계 정합)")
        if dn:
            return ("확대하되 온보딩 설계", "중", "당일 수익은 나지만 28일 관계 약화 — 깊이·빈도 조정 실험")
        return ("확대", "중", "당일 순수취 양호. 하류 지표는 혼합/미매칭")
    if v == "축소":
        if dn:
            return ("축소 — 최우선", "상", "당일 손실 + 28일 관계 약화 (2설계 정합)")
        if up:
            return ("축소 보류 — 실험", "중", "당일 손실이나 28일 관계 양호 — 상충. 홀드아웃 실험 후보")
        return ("할인 깊이 축소", "중", "당일 손실. 하류 지표는 혼합/미매칭")
    # 판정불가
    if up:
        return ("소규모 확대 실험", "하", "당일 효과 판정불가, 28일 관계 양호")
    if dn:
        return ("현행 유지·관찰", "하", "당일 효과 판정불가, 28일 관계 약화")
    return ("보류", "하", "두 설계 모두 뚜렷한 신호 없음")


acts = tri.apply(decide, axis=1, result_type="expand")
acts.columns = ["action", "confidence", "rationale"]
mat = pd.concat([
    tri[["category", "department", "verdict", "net_effect_usd", "t_stat",
         "basket_total_usd", "t_basket", "jyc_visit28_diff", "jyc_spend28_diff",
         "jyc_spend28_sig", "jyc_quadrant"]],
    acts], axis=1).sort_values(
        ["confidence", "net_effect_usd"], ascending=[True, False])
mat.to_csv(os.path.join(HERE, "02_decision_matrix.csv"),
           index=False, encoding="utf-8-sig")

say(f"[02] 액션 분포: {acts.action.value_counts().to_dict()}")
say(f"     신뢰도 '상' = {int((acts.confidence == '상').sum())}개 (2설계 정합)")
hi = mat[mat.confidence == "상"][["category", "verdict", "action"]]
say(hi.to_string(index=False))


# ══════════════════════════════════════════════════════════════════
# 03. 고객 축 교차표 — 할인의존도(남궁현종) × 할인친화도(전영찬 방식)
#   의존도: 로열티 할인액 ÷ 정가 구매액, DAY 1~547 (기존 5분위 그대로 사용)
#   친화도: 딥할인(구매기회 할인율 ≥30%) 구매기회 비중 — 전영찬 정의를 재계산
# ══════════════════════════════════════════════════════════════════
tx = os.path.join(DATA, "transaction_data.csv")
if not os.path.isfile(tx):
    say("[03] data/ 원본이 없어 건너뜀 (dunnhumby CSV를 data/ 에 두면 생성됨)")
else:
    import duckdb
    con = duckdb.connect()
    aff = con.execute(f"""
        WITH occ AS (
          SELECT t.household_key, p.COMMODITY_DESC, t.DAY,
                 SUM(-t.RETAIL_DISC - t.COUPON_MATCH_DISC) AS disc,
                 SUM(t.SALES_VALUE - t.RETAIL_DISC - t.COUPON_MATCH_DISC) AS gross
          FROM read_csv_auto('{tx}') t
          JOIN read_csv_auto('{os.path.join(DATA, "product.csv")}') p USING (PRODUCT_ID)
          WHERE p.COMMODITY_DESC IS NOT NULL
            AND p.COMMODITY_DESC NOT IN ('COUPON','MISC ITEMS','NO COMMODITY DESCRIPTION',' ')
          GROUP BY 1,2,3)
        SELECT household_key,
               COUNT(*) AS occasions,
               COUNT(*) FILTER (WHERE gross > 0 AND disc/gross >= 0.30) AS deep_occ,
               COUNT(*) FILTER (WHERE gross > 0 AND disc/gross >= 0.30) * 1.0
                 / NULLIF(COUNT(*) FILTER (WHERE gross > 0), 0) AS affinity
        FROM occ GROUP BY 1
    """).df()
    say(f"[03] 구매기회 {int(aff.occasions.sum()):,}건 / 가구 {len(aff):,} "
        f"(전영찬 보고서 1,855,343건과 대조용)")

    dd = pd.read_csv(os.path.join(P_OURS, "tableau_household_dd.csv"),
                     encoding="utf-8-sig")[["household_key", "dd_value", "quintile_value"]]
    m = dd.merge(aff[["household_key", "affinity"]], on="household_key", how="inner")
    m["affinity_q"] = pd.qcut(m.affinity, 5, labels=[1, 2, 3, 4, 5]).astype(int)

    ct = pd.crosstab(m.quintile_value, m.affinity_q,
                     rownames=["할인의존도(남궁현종)"], colnames=["할인친화도(전영찬 방식)"])
    rho = m[["quintile_value", "affinity_q"]].corr(method="spearman").iloc[0, 1]
    same = (m.quintile_value == m.affinity_q).mean()
    near = (abs(m.quintile_value - m.affinity_q) <= 1).mean()

    out = ct.reset_index()
    out.to_csv(os.path.join(HERE, "03_household_axis_crosstab.csv"),
               index=False, encoding="utf-8-sig")
    say(f"     Spearman rho = {rho:.3f} / 동일 분위 {same:.1%} / ±1 분위 이내 {near:.1%}")
    say(ct.to_string())

with open(os.path.join(HERE, "_build_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("DONE")
