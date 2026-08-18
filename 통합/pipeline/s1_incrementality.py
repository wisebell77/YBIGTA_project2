"""s1 — 상류(증분성) 단계 (장준한 설계 표준 재현)

trip(가구×매장×일, 실제 방문만) × 적격 카테고리 CROSS JOIN 기회 패널.
0구매 셀을 포함하므로 "안 사던 사람이 사게 됐는가"(외연 마진)를 잴 수 있다.

  처치 legacy  : 해당 카테고리×매장×주에 mailer <> '0' (장준한 원 정의 — 검증용)
  처치 standard: mailer 광고 코드(A,C,D,F,H,L)만 + 쿠폰/무료/진열 동반 셀 제외 (팀 표준)

추정: 가구×카테고리(pair) FE, 가구 클러스터 SE — 쌍 집계 충분통계로 계산.
  beta = Σ_p(Σxy − SxSy/n) / Σ_p(Σx² − Sx²/n),  score_h = Σ_{p∈h}(A_p − βB_p)
검증 목표(legacy): 구매확률 +24.31% / 총수량 +34.41% / 매출 +26.12% / 정가환산 +39.52%
                   / 56일 future qty +0.000158 (t 0.16)
출력: ../outputs/s1_*.csv
"""
import os, time
import numpy as np, pandas as pd
from standards import connect, OUT, WEEK_MIN, WEEK_MAX, POST_MAX_DAY

con = connect()
log = []
say = lambda s: log.append(str(s))
t0 = time.time()

# ── 기반: 스코프 거래, trips, 카테고리별 구매 ─────────────────────
con.execute(f"""
CREATE OR REPLACE TEMP VIEW tx1 AS
SELECT household_key, store_id, day, week_no, commodity_desc AS category,
       qty_w, net_sales, gross_sales
FROM fct
WHERE week_no BETWEEN {WEEK_MIN} AND {WEEK_MAX}
  AND store_id IN (SELECT DISTINCT store_id FROM causal_flag)
  AND commodity_desc <> 'COUPON/MISC ITEMS' AND commodity_desc IS NOT NULL
  AND net_sales > 0
""")

# 적격 카테고리: 매장 수준 구매기회(hh×store×day×cat)에 exp_any 를 붙여
# 쌍(n>=5, 노출>=2, 비노출>=2)이 성립하는 카테고리 (장준한 3A 표본 재현)
con.execute("""
CREATE OR REPLACE TEMP TABLE occ1 AS
SELECT t.household_key, t.store_id, t.day, t.week_no, t.category,
  SUM(t.qty_w) qty, SUM(t.net_sales) net, SUM(t.gross_sales) gross,
  COALESCE(MAX(cf.mailer_any),0) exp_any, COALESCE(MAX(cf.mailer_ad),0) exp_ad,
  COALESCE(MAX(cf.mailer_coupon),0) exp_coupon, COALESCE(MAX(cf.mailer_free),0) exp_free,
  COALESCE(MAX(cf.display_any),0) exp_disp
FROM tx1 t
LEFT JOIN cat_flag cf
  ON cf.commodity_desc=t.category AND cf.store_id=t.store_id AND cf.week_no=t.week_no
GROUP BY 1,2,3,4,5
""")
con.execute("""
CREATE OR REPLACE TEMP TABLE cats AS
SELECT DISTINCT category FROM (
  SELECT household_key, category, COUNT(*) n, SUM(exp_any) ne
  FROM occ1 GROUP BY 1,2 HAVING COUNT(*)>=5 AND SUM(exp_any)>=2 AND COUNT(*)-SUM(exp_any)>=2)
""")
n_cats = con.execute("SELECT COUNT(*) FROM cats").fetchone()[0]
say(f"[표본] 적격 카테고리 {n_cats}개 — 장준한 222개")

# ── 기회 패널 (trip × cats) ──────────────────────────────────────
con.execute("""
CREATE OR REPLACE TEMP TABLE panel AS
WITH trips AS (SELECT DISTINCT household_key, store_id, day, week_no FROM tx1),
buy AS (SELECT household_key, store_id, day, category,
          SUM(qty_w) qty, SUM(net_sales) net, SUM(gross_sales) gross
        FROM tx1 GROUP BY 1,2,3,4)
SELECT t.household_key, t.store_id, t.day, t.week_no, c.category,
  CASE WHEN b.category IS NULL THEN 0 ELSE 1 END purchase,
  COALESCE(b.qty,0) qty, COALESCE(b.net,0) net, COALESCE(b.gross,0) gross,
  COALESCE(cf.mailer_any,0) exp_any, COALESCE(cf.mailer_ad,0) exp_ad,
  COALESCE(cf.mailer_coupon,0) exp_coupon, COALESCE(cf.mailer_free,0) exp_free,
  COALESCE(cf.display_any,0) exp_disp
FROM trips t CROSS JOIN cats c
LEFT JOIN buy b ON b.household_key=t.household_key AND b.store_id=t.store_id
               AND b.day=t.day AND b.category=c.category
LEFT JOIN cat_flag cf ON cf.commodity_desc=c.category AND cf.store_id=t.store_id
                     AND cf.week_no=t.week_no
""")
n_panel = con.execute("SELECT COUNT(*) FROM panel").fetchone()[0]
say(f"[표본] 기회 패널 {n_panel:,}행 — 장준한 46,714,794행  [{time.time()-t0:.0f}s]")


def fe_beta(where, treat, ycols):
    """pair(hh×cat) FE + hh 클러스터 SE — 쌍 집계 충분통계."""
    agg = con.execute(f"""
    SELECT household_key, category, COUNT(*) n, SUM({treat}) sx, SUM({treat}*{treat}) sxx,
      {", ".join(f"SUM({y}) sy_{y}, SUM({treat}*{y}) sxy_{y}" for y in ycols)},
      {", ".join(f"SUM(CASE WHEN {treat}=0 THEN {y} END) y0_{y}" for y in ycols)},
      SUM(CASE WHEN {treat}=0 THEN 1 ELSE 0 END) n0
    FROM panel {where} GROUP BY 1,2
    HAVING SUM({treat})>0 AND SUM({treat})<COUNT(*)
    """).df()
    res = {}
    B = agg.sxx - agg.sx ** 2 / agg.n
    for y in ycols:
        A = agg[f"sxy_{y}"] - agg.sx * agg[f"sy_{y}"] / agg.n
        beta = A.sum() / B.sum()
        score = (A - beta * B).groupby(agg.household_key).sum()
        se = np.sqrt((score ** 2).sum()) / B.sum()
        ctrl = agg[f"y0_{y}"].sum() / agg.n0.sum()
        res[y] = dict(beta=beta, se=se, t=beta / se, ctrl=ctrl, pct=beta / ctrl * 100)
    res["_n"] = int(agg.n.sum())
    return res


ycols = ["purchase", "qty", "net", "gross"]
modes = [
    ("legacy(검증)", "", "exp_any"),
    ("standard", "WHERE exp_coupon=0 AND exp_free=0 AND exp_disp=0", "exp_ad"),
]
rows = []
for label, where, treat in modes:
    r = fe_beta(where, treat, ycols)
    say(f"[ITT:{label}] n={r['_n']:,}" + "".join(
        f" | {y} {r[y]['pct']:+.2f}% (t {r[y]['t']:.1f})" for y in ycols))
    for y in ycols:
        rows.append(dict(mode=label, outcome=y, **r[y]))
say("    — 장준한 legacy 목표: purchase +24.31 / qty +34.41 / net +26.12 / gross +39.52")
pd.DataFrame(rows).to_csv(os.path.join(OUT, "s1_itt.csv"), index=False, encoding="utf-8-sig")

# ── 56일 future payback ──────────────────────────────────────────
con.execute("""
CREATE OR REPLACE TEMP TABLE hcday AS
SELECT household_key, category, day, SUM(qty_w) q
FROM tx1 GROUP BY 1,2,3
""")
con.execute(f"""
CREATE OR REPLACE TEMP TABLE fut AS
SELECT p.household_key, p.category, p.day,
  p.exp_any, p.exp_ad, p.exp_coupon, p.exp_free, p.exp_disp,
  COALESCE(SUM(h.q),0) fq56
FROM (SELECT * FROM panel WHERE day <= {POST_MAX_DAY}) p
LEFT JOIN hcday h
  ON h.household_key=p.household_key AND h.category=p.category
 AND h.day > p.day AND h.day <= p.day + 56
GROUP BY 1,2,3,4,5,6,7,8
""")
say(f"[payback] future 창 계산 완료 [{time.time()-t0:.0f}s]")


def fe_beta_tbl(tbl, where, treat, y):
    agg = con.execute(f"""
    SELECT household_key, category, COUNT(*) n, SUM({treat}) sx, SUM({treat}*{treat}) sxx,
      SUM({y}) sy, SUM({treat}*{y}) sxy
    FROM {tbl} {where} GROUP BY 1,2
    HAVING SUM({treat})>0 AND SUM({treat})<COUNT(*)
    """).df()
    B = agg.sxx - agg.sx ** 2 / agg.n
    A = agg.sxy - agg.sx * agg.sy / agg.n
    beta = A.sum() / B.sum()
    score = (A - beta * B).groupby(agg.household_key).sum()
    se = np.sqrt((score ** 2).sum()) / B.sum()
    return beta, beta / se


pay = []
for label, where, treat in [("legacy(검증)", "", "exp_any"),
                            ("standard", "WHERE exp_coupon=0 AND exp_free=0 AND exp_disp=0", "exp_ad")]:
    b, t = fe_beta_tbl("fut", where, treat, "fq56")
    pay.append(dict(mode=label, beta=b, t=t))
    say(f"[payback:{label}] 56일 future qty {b:+.6f}/기회 (t {t:.2f}) — 장준한 +0.000158 (t 0.16)")
pd.DataFrame(pay).to_csv(os.path.join(OUT, "s1_payback56.csv"), index=False, encoding="utf-8-sig")

con.close()
with open(os.path.join(OUT, "s1_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s1 DONE")
