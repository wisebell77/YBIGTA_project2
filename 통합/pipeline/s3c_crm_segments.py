"""s3c — 가구 세그먼트(S1~S5) x 카테고리 역할(R1~R4) CRM 전략 매트릭스.

전영찬 12_customer_relationship_strategy.sql의 세그먼트/역할 설계를 표준
마트(occ/fct, standards.py 처치정의) 위에서 재구축한다. s3_crm.py(고할인
당일/사후 분석)과 달리, 여기서는 "노출 자체가 매장 관계에 어떤 가구·카테고리
조합에서 통하는가"를 가구 단위로 세그먼트화하고, s2의 인과판정(category_action)과
결합해 실행 우선순위를 만든다.

판정 로직 (두 축을 분리해서 결합 — 세그먼트가 판정을 뒤집지 않고 우선순위만 바꾼다):
  category_action = s2_category_verdict.verdict의 role별 다수결 (인과추정, "무엇을")
  segment_priority = 세그먼트별 관계지표(halo·매장전체지출·반복구매) 기반 (관찰적, "누구부터")

출력: ../outputs/s3c_segment_summary.csv, s3c_category_role.csv,
      s3c_segment_role_crosstab.csv
"""
import os
import numpy as np, pandas as pd
from standards import connect, find_data, OUT, WEEK_MIN, WEEK_MAX, POST_MAX_DAY

DATA = find_data()
con = connect()

# ── 가구인구통계 ─────────────────────────────────────────────────
con.execute(f"""
CREATE OR REPLACE TABLE dim_household AS
SELECT household_key, income_desc, age_desc, hh_comp_desc
FROM read_csv_auto('{DATA}/hh_demographic.csv')
""")

# ── 스코프: s2에서 유의 판정(확대/축소)난 카테고리만 ────────────────
verdict = pd.read_csv(os.path.join(OUT, "s2_category_verdict.csv"))
scope_df = verdict.loc[verdict.verdict != "불확실", ["category", "verdict"]].reset_index(drop=True)
con.register("scope_verdict", scope_df)
print(f"스코프 카테고리(s2 확대/축소 판정): {len(scope_df)}개")

# ── 매장 전체 컨텍스트(halo 분모) — causal 표본 전체 카테고리 기준 ──
con.execute(f"""
CREATE OR REPLACE TEMP VIEW cstore AS SELECT DISTINCT store_id FROM causal_flag;
CREATE OR REPLACE TEMP VIEW store_ctx AS
  SELECT f.household_key, f.day,
    SUM(f.net_sales) AS store_spend,
    COUNT(DISTINCT f.basket_id) AS baskets,
    COUNT(DISTINCT f.commodity_desc) AS categories
  FROM fct f JOIN cstore USING (store_id)
  WHERE f.week_no BETWEEN {WEEK_MIN} AND {WEEK_MAX}
  GROUP BY 1, 2;
""")

con.execute(f"""
CREATE OR REPLACE TABLE stage3c_pair AS
WITH occasions0 AS (
  SELECT * FROM occ
  WHERE category IN (SELECT category FROM scope_verdict)
    AND has_coupon = 0 AND has_free = 0 AND has_display = 0
),
occasions AS (
  SELECT o.*,
    LEAD(o.day) OVER (PARTITION BY o.household_key, o.category ORDER BY o.day) - o.day AS next_days,
    ROW_NUMBER() OVER (PARTITION BY o.household_key, o.category ORDER BY o.day) AS cat_order
  FROM occasions0 o
),
occasion_context AS (
  SELECT o.*, sc.store_spend, sc.categories,
    sc.store_spend - o.net AS other_cat_spend,
    (SELECT COUNT(DISTINCT s2.day) FROM store_ctx s2
      WHERE s2.household_key = o.household_key AND s2.day BETWEEN o.day + 1 AND o.day + 28) AS post28_visits,
    (SELECT COALESCE(SUM(s2.store_spend), 0) FROM store_ctx s2
      WHERE s2.household_key = o.household_key AND s2.day BETWEEN o.day + 1 AND o.day + 28) AS post28_store_spend,
    (SELECT COALESCE(SUM(o2.qty), 0) FROM occasions0 o2
      WHERE o2.household_key = o.household_key AND o2.category = o.category
        AND o2.day BETWEEN o.day + 1 AND o.day + 56) AS post56_cat_qty
  FROM occasions o JOIN store_ctx sc USING (household_key, day)
  WHERE o.day <= {POST_MAX_DAY}
),
eligible AS (
  SELECT household_key, category FROM occasion_context GROUP BY 1, 2
  HAVING COUNT(*) >= 5 AND SUM(exposed) >= 2 AND SUM(1 - exposed) >= 2
)
SELECT o.household_key, o.category,
  AVG(o.qty) FILTER (WHERE o.exposed=1) - AVG(o.qty) FILTER (WHERE o.exposed=0) AS qty_diff,
  AVG(o.net) FILTER (WHERE o.exposed=1) - AVG(o.net) FILTER (WHERE o.exposed=0) AS net_diff,
  AVG(o.other_cat_spend) FILTER (WHERE o.exposed=1) - AVG(o.other_cat_spend) FILTER (WHERE o.exposed=0) AS halo_diff,
  AVG(o.post28_visits) FILTER (WHERE o.exposed=1) - AVG(o.post28_visits) FILTER (WHERE o.exposed=0) AS post28_visit_diff,
  AVG(o.post28_store_spend) FILTER (WHERE o.exposed=1) - AVG(o.post28_store_spend) FILTER (WHERE o.exposed=0) AS post28_store_spend_diff,
  AVG(o.post56_cat_qty) FILTER (WHERE o.exposed=1) - AVG(o.post56_cat_qty) FILTER (WHERE o.exposed=0) AS post56_cat_qty_diff,
  AVG(o.next_days) FILTER (WHERE o.exposed=1) - AVG(o.next_days) FILTER (WHERE o.exposed=0) AS next_days_diff
FROM occasion_context o JOIN eligible USING (household_key, category)
GROUP BY 1, 2
""")
print("stage3c_pair:", con.execute("SELECT COUNT(*) FROM stage3c_pair").fetchone()[0], "행")

con.execute(f"""
CREATE OR REPLACE TABLE stage3c_hh_segment AS
WITH occasions0 AS (
  SELECT * FROM occ
  WHERE category IN (SELECT category FROM scope_verdict)
    AND has_coupon = 0 AND has_free = 0 AND has_display = 0
),
hh_effect AS (
  SELECT household_key, COUNT(*) AS eligible_categories,
    AVG(qty_diff) AS qty_diff, AVG(net_diff) AS net_diff,
    AVG(halo_diff) AS halo_diff, AVG(post28_visit_diff) AS post28_visit_diff,
    AVG(post28_store_spend_diff) AS post28_store_spend_diff,
    AVG(post56_cat_qty_diff) AS post56_cat_qty_diff, AVG(next_days_diff) AS next_days_diff
  FROM stage3c_pair GROUP BY 1
),
hh_affinity AS (
  SELECT household_key, AVG(disc_rate) AS avg_discount, AVG(exposed) AS exposed_share
  FROM occasions0 GROUP BY 1
),
hh_scored AS (
  SELECT e.*, a.exposed_share, a.avg_discount,
    PERCENT_RANK() OVER (ORDER BY post28_store_spend_diff) AS spend_pr,
    PERCENT_RANK() OVER (ORDER BY halo_diff) AS halo_pr,
    PERCENT_RANK() OVER (ORDER BY exposed_share) AS affinity_pr
  FROM hh_effect e JOIN hh_affinity a USING (household_key)
)
SELECT *, CASE
    WHEN post56_cat_qty_diff < 0 AND next_days_diff > 0 THEN 'S1 재고비축형'
    WHEN spend_pr >= .60 AND post28_visit_diff > 0 THEN 'S2 관계강화형'
    WHEN halo_pr >= .60 AND post28_store_spend_diff <= 0 THEN 'S3 장바구니재편형'
    WHEN affinity_pr >= .80 AND net_diff <= 0 THEN 'S4 전단지의존형'
    ELSE 'S5 반응불분명형' END AS segment
FROM hh_scored
""")
n_seg = con.execute("SELECT COUNT(*) FROM stage3c_hh_segment").fetchone()[0]
print("stage3c_hh_segment:", n_seg, "행")

# ── 카테고리 역할 4종 ────────────────────────────────────────────
n_hh_universe = con.execute(f"""
  SELECT COUNT(DISTINCT f.household_key) FROM fct f JOIN cstore USING (store_id)
  WHERE f.week_no BETWEEN {WEEK_MIN} AND {WEEK_MAX}
""").fetchone()[0]

con.execute(f"""
CREATE OR REPLACE TABLE stage3c_category_role AS
WITH occasions0 AS (
  SELECT * FROM occ
  WHERE category IN (SELECT category FROM scope_verdict)
    AND has_coupon = 0 AND has_free = 0 AND has_display = 0
),
occasions AS (
  SELECT o.*,
    LEAD(o.day) OVER (PARTITION BY o.household_key, o.category ORDER BY o.day) - o.day AS next_days
  FROM occasions0 o
),
category_basic AS (
  SELECT category,
    COUNT(DISTINCT household_key) AS buyer_hh,
    COUNT(DISTINCT household_key)::DOUBLE / {n_hh_universe} AS penetration,
    COUNT(*)::DOUBLE / COUNT(DISTINCT household_key) AS occasions_per_buyer,
    AVG(next_days) AS mean_gap
  FROM occasions GROUP BY 1 HAVING COUNT(DISTINCT household_key) >= 100
),
category_coshop AS (
  SELECT o.category,
    AVG(CASE WHEN sc.categories > 1 THEN 1 ELSE 0 END) AS coshop_rate,
    AVG(o.net / NULLIF(sc.store_spend, 0)) AS basket_value_share
  FROM occasions0 o JOIN store_ctx sc USING (household_key, day)
  GROUP BY 1
),
category_week AS (
  SELECT commodity_desc AS category, week_no, SUM(net_sales) AS spend
  FROM fct JOIN cstore USING (store_id)
  WHERE commodity_desc IN (SELECT category FROM scope_verdict)
    AND week_no BETWEEN {WEEK_MIN} AND {WEEK_MAX}
  GROUP BY 1, 2
),
category_season AS (
  SELECT category,
    SUM(spend) FILTER (WHERE week_rank <= 13) / NULLIF(SUM(spend), 0) AS top13_week_share
  FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY category ORDER BY spend DESC) AS week_rank
        FROM category_week) GROUP BY 1
),
category_metric AS (
  SELECT b.*, c.coshop_rate, c.basket_value_share, s.top13_week_share,
    PERCENT_RANK() OVER (ORDER BY penetration) AS pen_pr,
    PERCENT_RANK() OVER (ORDER BY occasions_per_buyer) AS freq_pr,
    PERCENT_RANK() OVER (ORDER BY top13_week_share) AS season_pr,
    PERCENT_RANK() OVER (ORDER BY basket_value_share) AS share_pr
  FROM category_basic b JOIN category_coshop c USING (category)
  JOIN category_season s USING (category)
)
SELECT *, CASE
    WHEN season_pr >= .85 THEN 'R3 계절형'
    WHEN pen_pr >= .70 AND share_pr >= .60 THEN 'R1 집객형'
    WHEN freq_pr >= .65 AND mean_gap <= 45 THEN 'R2 일상구매형'
    ELSE 'R4 편의보완형' END AS role_label
FROM category_metric
""")
n_role = con.execute("SELECT COUNT(*) FROM stage3c_category_role").fetchone()[0]
print("stage3c_category_role:", n_role, "행")

# ── 세그먼트 요약 (인구통계 포함) ───────────────────────────────────
seg_summary = con.execute("""
  SELECT s.segment, COUNT(*) AS households,
    ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER (), 1) AS pct,
    ROUND(AVG(s.exposed_share), 4) AS exposed_share,
    ROUND(AVG(s.post28_visit_diff), 4) AS visit_28d_diff,
    ROUND(AVG(s.post28_store_spend_diff), 3) AS store_spend_28d_diff,
    ROUND(AVG(s.halo_diff), 3) AS other_category_spend_diff,
    ROUND(AVG(s.post56_cat_qty_diff), 3) AS same_category_56d_qty_diff,
    ROUND(AVG(s.next_days_diff), 3) AS purchase_gap_diff,
    mode(d.income_desc) AS top_income, mode(d.age_desc) AS top_age, mode(d.hh_comp_desc) AS top_hh_comp
  FROM stage3c_hh_segment s LEFT JOIN dim_household d USING (household_key)
  GROUP BY 1 ORDER BY 1
""").df()
seg_summary.to_csv(os.path.join(OUT, "s3c_segment_summary.csv"), index=False, encoding="utf-8-sig")
print("\n[세그먼트 요약]")
print(seg_summary.to_string(index=False))

role_summary = con.execute("""
  SELECT role_label, COUNT(*) AS n_categories,
    ROUND(AVG(penetration), 4) AS penetration, ROUND(AVG(occasions_per_buyer), 2) AS occasions_per_buyer,
    ROUND(AVG(mean_gap), 2) AS mean_gap, ROUND(AVG(coshop_rate), 4) AS coshop_rate,
    ROUND(AVG(basket_value_share), 4) AS basket_value_share, ROUND(AVG(top13_week_share), 4) AS top13_week_share
  FROM stage3c_category_role GROUP BY 1 ORDER BY 1
""").df()
role_summary.to_csv(os.path.join(OUT, "s3c_category_role.csv"), index=False, encoding="utf-8-sig")
print("\n[카테고리 역할 요약]")
print(role_summary.to_string(index=False))

# ── 세그먼트 x 역할 교차표 + 결합 판정 규칙 ─────────────────────────
joined = con.execute("""
  SELECT s.segment, r.role_label, p.household_key, p.category, p.qty_diff, p.net_diff, v.verdict
  FROM stage3c_pair p
  JOIN stage3c_hh_segment s USING (household_key)
  JOIN stage3c_category_role r USING (category)
  LEFT JOIN scope_verdict v USING (category)
""").df()

agg = joined.groupby(["segment", "role_label"]).agg(
    n_pairs=("household_key", "size"),
    n_households=("household_key", "nunique"),
    n_categories=("category", "nunique"),
    avg_net_diff=("net_diff", "mean"),
    avg_qty_diff=("qty_diff", "mean"),
).reset_index()
verdict_counts = joined.groupby(["segment", "role_label", "verdict"]).size().unstack(fill_value=0)
agg["n_expand_pairs"] = agg.apply(lambda r: verdict_counts.loc[(r.segment, r.role_label)].get("확대", 0)
                                  if (r.segment, r.role_label) in verdict_counts.index else 0, axis=1)
agg["n_shrink_pairs"] = agg.apply(lambda r: verdict_counts.loc[(r.segment, r.role_label)].get("축소", 0)
                                  if (r.segment, r.role_label) in verdict_counts.index else 0, axis=1)
agg["category_action"] = np.where(agg.n_expand_pairs > agg.n_shrink_pairs, "확대",
                           np.where(agg.n_shrink_pairs > agg.n_expand_pairs, "축소", "판단보류"))


def strategy(row):
    seg, role, action = row.segment, row.role_label, row.category_action
    if seg == "S4 전단지의존형":
        return "보류 — 모니터링만 (표본 작음, role 무관 신규확대 금지)"
    if seg == "S2 관계강화형":
        if action == "확대":
            return "확대 — 최우선 (매장 전체 지출까지 함께 증가하는 유일한 세그먼트)"
        if action == "축소":
            return "축소 — 표준 집행"
        return "판단보류 — 최우선 세그먼트, 소규모 확대 테스트 우선 검토"
    if seg == "S1 재고비축형":
        if role in ("R1 집객형", "R3 계절형") and action == "확대":
            return "확대 — 2순위 (집객·계절 role만 선별)"
        if role in ("R2 일상구매형", "R4 편의보완형"):
            return "축소 — 반복노출 자제 (재구매 시점만 당길 위험)"
        if action == "축소":
            return "축소 — 표준 집행"
        return "유지 — 2순위 세그먼트지만 role 근거 약함"
    if seg == "S3 장바구니재편형":
        if role == "R3 계절형" and action == "확대":
            return "확대 — 3순위 (halo만으로 확실한 유일한 role)"
        if role == "R1 집객형":
            return "유지 — 경계사례, 소규모 테스트 후 판단 (halo 양수·매장지출 음수 상충)"
        if action == "축소":
            return "축소 — 표준 집행"
        return "유지 — 3순위 세그먼트, role 근거 약함"
    if seg == "S5 반응불분명형":
        if action == "확대":
            return "확대 — 카테고리 판정대로 (세그먼트 가중 없음)"
        if action == "축소":
            return "축소 — 카테고리 판정대로 (세그먼트 가중 없음)"
    return "유지 — 근거 약함, 추가검증 필요"


agg["suggested_strategy"] = agg.apply(strategy, axis=1)
agg = agg.sort_values(["segment", "role_label"])
agg.to_csv(os.path.join(OUT, "s3c_segment_role_crosstab.csv"), index=False, encoding="utf-8-sig")
print(f"\n저장: s3c_segment_summary.csv / s3c_category_role.csv / s3c_segment_role_crosstab.csv ({len(agg)}행)")
print(agg[["segment", "role_label", "n_households", "n_categories", "category_action", "suggested_strategy"]]
      .to_string(index=False))

con.close()
print("s3c DONE")
