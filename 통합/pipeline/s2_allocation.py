"""s2 — 배분 단계 (남궁현종 설계 표준 재현)

  A. 카테고리 판정: 전단지 ITT 당일 순수취액 + BH-FDR + 유의 잠식 → 확대/축소/불확실
  B. 고객 이질성: 할인의존도 5분위별 전단지 효과
  C. halo: 노출 구매기회의 당일 나머지-장바구니 지출 (카테고리/전체)
  D. 지면 위치 용량반응: 내지 vs 1면

원 분석 대비 달라지는 것은 정크 필터 확대('COUPON/MISC ITEMS' 추가)뿐이며,
72개 판정 카테고리에는 영향이 없음을 스크립트가 원 결과와 대조해 확인한다.
출력: ../outputs/s2_*.csv
"""
import os
import numpy as np, pandas as pd
from scipy import stats as st
from standards import connect, OUT

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
con = connect()
log = []
say = lambda s: log.append(str(s))

# ── 표본: clean 구매기회 + 적격 쌍 ────────────────────────────────
con.execute("""
CREATE OR REPLACE TEMP VIEW s AS
WITH clean AS (SELECT * FROM occ WHERE has_coupon=0 AND has_free=0 AND has_display=0),
p AS (SELECT household_key, category FROM clean
      GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exposed)>=2 AND SUM(1-exposed)>=2)
SELECT clean.* FROM clean JOIN p USING (household_key, category)
""")

# ── A. 카테고리 효과 + 잠식 + 판정 ────────────────────────────────
eff = con.execute("""
WITH e AS (SELECT household_key,category,AVG(qty) q,AVG(net) n,AVG(disc_rate) dr
           FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(qty) q,AVG(net) n,AVG(disc_rate) dr
      FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.q-u.q dq, e.n-u.n dn, u.q uq, u.n un, u.dr udr, e.dr edr
      FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) n_pairs,
  AVG(dq)/AVG(uq)*100 AS qty_pct,
  AVG(dn) AS net_now, AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))) AS t_net,
  AVG(dn)/AVG(un)*100 AS net_pct,
  (AVG(edr)-AVG(udr))*100 AS d_disc
FROM d GROUP BY category HAVING COUNT(*)>=100
""").df()
eff["elasticity"] = eff.qty_pct / eff.d_disc

cann = con.execute("""
WITH post AS (
  SELECT a.household_key, a.category, a.day, a.exposed,
    COALESCE(SUM(CASE WHEN b.day>a.day AND b.day<=a.day+56 THEN b.net END),0) n56
  FROM s a LEFT JOIN s b
    ON a.household_key=b.household_key AND a.category=b.category
   AND b.day>a.day AND b.day<=a.day+56
  WHERE a.day <= 655 GROUP BY 1,2,3,4),
e AS (SELECT household_key,category,AVG(n56) n FROM post WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(n56) n FROM post WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.n-u.n dn FROM e JOIN u USING (household_key,category))
SELECT category, AVG(dn) net_later, AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))) t_cann
FROM d GROUP BY category
""").df()

cat = eff.merge(cann, on="category", how="left")
# BH-FDR 5% (양측) 후, 순효과(당일 + 유의 잠식만) 부호로 판정
cat["p"] = 2 * st.norm.sf(cat.t_net.abs())
ps = cat.p.sort_values().values
thresh_mask = ps <= np.arange(1, len(ps) + 1) / len(ps) * 0.05
cutoff = ps[thresh_mask].max() if thresh_mask.any() else -1.0
cat["significant_bh"] = cat.p <= cutoff
cat["net_total"] = cat.net_now + np.where(cat.t_cann <= -1.96, cat.net_later.fillna(0), 0)
cat["verdict"] = np.where(~cat.significant_bh, "불확실",
                          np.where(cat.net_total > 0, "확대", "축소"))
cat.to_csv(os.path.join(OUT, "s2_category_verdict.csv"), index=False, encoding="utf-8-sig")
say(f"[A] 카테고리 {len(cat)}개 / BH 유의 {int(cat.significant_bh.sum())}개 / "
    f"판정 {cat.verdict.value_counts().to_dict()}")

ref = pd.read_csv(os.path.join(ROOT, "남궁현종", "산출물", "tableau",
                               "tableau_category_decision.csv"), encoding="utf-8-sig")
j = cat.merge(ref[["category", "verdict", "net_effect_usd", "t_stat"]],
              on="category", suffixes=("", "_ref"))
mismatch = j[j.verdict != j.verdict_ref]
say(f"    원 판정 대조: {len(j)}개 매칭 / 판정 불일치 {len(mismatch)}건 / "
    f"당일효과 최대차 ${(j.net_now - j.net_effect_usd).abs().max():.4f}")
if len(mismatch):
    say(mismatch[["category", "verdict", "verdict_ref", "net_now",
                  "net_effect_usd", "t_net", "t_stat"]].to_string(index=False))

# ── B. 할인의존도 5분위 이질성 ────────────────────────────────────
con.execute("""
CREATE OR REPLACE TEMP VIEW hh_q AS
WITH dd AS (SELECT household_key,
              SUM(retailer_disc)/NULLIF(SUM(gross_sales),0) AS dd
            FROM fct WHERE day <= 547 GROUP BY 1)
SELECT household_key, dd, NTILE(5) OVER (ORDER BY dd) AS quintile FROM dd
""")
# 검증: 공식 자체는 대시보드 CSV의 전기간 dd_value 와 완전 일치해야 한다.
# (분석용 분위는 누출 차단을 위해 DAY<=547 로 계산 — 대시보드 표시용 전기간 값과 다른 변수)
qref = pd.read_csv(os.path.join(ROOT, "남궁현종", "산출물", "tableau",
                                "tableau_household_dd.csv"), encoding="utf-8-sig")
ddfull = con.execute("""SELECT household_key,
    SUM(retailer_disc)/NULLIF(SUM(gross_sales),0) AS dd FROM fct GROUP BY 1""").df()
jq = qref.merge(ddfull, on="household_key")
say(f"[B] dd 공식 검증(전기간, 대시보드 dd_value 대비): 최대절대차 "
    f"{(jq.dd - jq.dd_value).abs().max():.6f} — 분석 분위는 DAY<=547 (누출 차단)")

het = con.execute("""
WITH e AS (SELECT household_key,category,AVG(net) n FROM s WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(net) n FROM s WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.household_key, e.n-u.n dn, u.n un FROM e JOIN u USING (household_key,category))
SELECT q.quintile, COUNT(*) n_pairs,
  AVG(dn)/AVG(un)*100 AS net_pct,
  AVG(dn)/(STDDEV(dn)/SQRT(COUNT(*))) AS t_net
FROM d JOIN hh_q q USING (household_key)
GROUP BY 1 ORDER BY 1
""").df()
het.to_csv(os.path.join(OUT, "s2_quintile_heterogeneity.csv"), index=False, encoding="utf-8-sig")
con.execute("SELECT household_key, dd, quintile FROM hh_q").df().to_csv(
    os.path.join(OUT, "s2_household_quintile.csv"), index=False, encoding="utf-8-sig")
say("    분위별 순수취액 효과: " +
    " / ".join(f"Q{int(r.quintile)} {r.net_pct:+.1f}%(t={r.t_net:.1f})" for r in het.itertuples()))

# ── C. halo ───────────────────────────────────────────────────────
halo = con.execute("""
WITH hhday AS (SELECT household_key, day, SUM(net_sales) total FROM fct GROUP BY 1,2),
x AS (SELECT s.household_key, s.category, s.exposed, h.total - s.net AS rest, s.net AS focal
      FROM s JOIN hhday h USING (household_key, day)),
e AS (SELECT household_key,category,AVG(rest) r,AVG(focal) f FROM x WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(rest) r,AVG(focal) f FROM x WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.category, e.r-u.r dr, e.f-u.f df, u.r ur FROM e JOIN u USING (household_key,category))
SELECT category, COUNT(*) n_pairs, AVG(df) focal_eff,
  AVG(dr) halo_eff, AVG(dr)/(STDDEV(dr)/SQRT(COUNT(*))) t_halo,
  AVG(df)+AVG(dr) basket_total,
  (AVG(df)+AVG(dr))/(STDDEV(df+dr)/SQRT(COUNT(*))) t_basket
FROM d GROUP BY category HAVING COUNT(*)>=100
""").df()
halo.to_csv(os.path.join(OUT, "s2_halo_category.csv"), index=False, encoding="utf-8-sig")
tot = con.execute("""
WITH hhday AS (SELECT household_key, day, SUM(net_sales) total FROM fct GROUP BY 1,2),
x AS (SELECT s.household_key, s.category, s.exposed, h.total - s.net AS rest
      FROM s JOIN hhday h USING (household_key, day)),
e AS (SELECT household_key,category,AVG(rest) r FROM x WHERE exposed=1 GROUP BY 1,2),
u AS (SELECT household_key,category,AVG(rest) r FROM x WHERE exposed=0 GROUP BY 1,2),
d AS (SELECT e.r-u.r dr FROM e JOIN u USING (household_key,category))
SELECT COUNT(*) n, AVG(dr) rest_diff, AVG(dr)/(STDDEV(dr)/SQRT(COUNT(*))) t FROM d
""").df().iloc[0]
say(f"[C] halo 전체: +${tot.rest_diff:.3f} (t={tot.t:.2f}) — 원 결과 +$2.045 (t=10.71)")

# ── D. 지면 위치 용량반응 ─────────────────────────────────────────
dose = con.execute("""
WITH p2 AS (SELECT household_key, category FROM s
            GROUP BY 1,2
            HAVING SUM(CASE WHEN exposed=1 AND front=0 THEN 1 ELSE 0 END)>=1
               AND SUM(CASE WHEN exposed=1 AND front=1 THEN 1 ELSE 0 END)>=1
               AND SUM(1-exposed)>=1),
x AS (SELECT s.*, CASE WHEN exposed=0 THEN 'none' WHEN front=1 THEN 'front'
                       ELSE 'inside' END dose
      FROM s JOIN p2 USING (household_key, category)),
m AS (SELECT household_key, category, dose, AVG(qty) q FROM x GROUP BY 1,2,3),
w AS (SELECT household_key, category,
        MAX(CASE WHEN dose='none' THEN q END) q0,
        MAX(CASE WHEN dose='inside' THEN q END) qi,
        MAX(CASE WHEN dose='front' THEN q END) qf
      FROM m GROUP BY 1,2)
SELECT COUNT(*) n_pairs, AVG(q0) q_none, AVG(qi) q_inside, AVG(qf) q_front,
  (AVG(qf)-AVG(qi))/(STDDEV(qf-qi)/SQRT(COUNT(*))) t_front_vs_inside
FROM w WHERE q0 IS NOT NULL AND qi IS NOT NULL AND qf IS NOT NULL
""").df().iloc[0]
say(f"[D] 용량반응: 없음 {dose.q_none:.3f} -> 내지 {dose.q_inside:.3f}"
    f"(+{(dose.q_inside / dose.q_none - 1) * 100:.1f}%) -> 1면 {dose.q_front:.3f}"
    f"(+{(dose.q_front / dose.q_none - 1) * 100:.1f}%), 1면vs내지 t={dose.t_front_vs_inside:.2f}"
    f" [n={int(dose.n_pairs)}] — 원 결과 +22.8%/+35.1%, t=12.04")

con.close()
with open(os.path.join(OUT, "s2_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s2 DONE")
