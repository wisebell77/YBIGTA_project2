"""s3 — 하류(CRM) 단계 (전영찬 설계 표준 재현)

주 처치 = 실현 딥할인 (구매기회 할인율 >= 30%) vs 정가 (<= 2%). 관측적/진단적 —
가구 자기선택이 포함되므로 인과로 읽지 않는다 (PART B).

  A. 당일 효과: 수량·실지출·정가환산 (legacy 공식 검증 후 표준 공식으로 재추정)
  B. 재구매 간격 / 사후 28·56일 잠식
  C. 체험 전환: 첫 구매가 딥할인일 때 56일 재구매율·정가 재구매율
  D. 28일 하류: 딥할인 vs 정가 구매 후 매장 전체 방문·지출 (카테고리별 → s4 삼각측량 입력)
  E. 가구 할인친화도 (딥할인 구매기회 비중) → s4 고객 축 교차표 입력

legacy 공식(전영찬): rate = -RETAIL_DISC / (SALES_VALUE - RETAIL_DISC)
표준 공식        : rate = retailer_disc / gross  (COUPON_MATCH_DISC 포함)
출력: ../outputs/s3_*.csv
"""
import os
import numpy as np, pandas as pd
from standards import connect, OUT, DEEP_CUT, REG_CUT, POST_MAX_DAY

con = connect()
log = []
say = lambda s: log.append(str(s))

# ── 구매기회 (전영찬 범위: 전 매장·전 기간) ───────────────────────
con.execute("""
CREATE OR REPLACE TEMP VIEW occ3 AS
SELECT household_key, commodity_desc AS category, day,
  SUM(quantity) AS qty_raw, SUM(qty_w) AS qty_w, SUM(net_sales) AS spend,
  SUM(net_sales + retail_disc_amt) AS reg_legacy,
  SUM(retail_disc_amt) / NULLIF(SUM(net_sales + retail_disc_amt), 0) AS rate_legacy,
  SUM(gross_sales) AS gross,
  SUM(retailer_disc) / NULLIF(SUM(gross_sales), 0) AS rate_std
FROM fct
WHERE commodity_desc <> 'COUPON/MISC ITEMS' AND commodity_desc IS NOT NULL
  AND quantity > 0 AND net_sales + retail_disc_amt > 0
GROUP BY 1,2,3
""")
n_occ = con.execute("SELECT COUNT(*) FROM occ3").fetchone()[0]
say(f"[표본] 구매기회 {n_occ:,}건 — 전영찬 보고서 1,855,343건")


def cluster_t(d):
    """가구 클러스터 t (평균 추정량의 클러스터-로버스트 SE)."""
    mu = d["v"].mean()
    g = d.assign(r=d.v - mu).groupby("household_key").r.sum()
    se = np.sqrt((g ** 2).sum()) / len(d)
    return mu, mu / se


def same_day(rate_col, qty_col, reg_col, label, targets=None):
    df = con.execute(f"""
    WITH o AS (SELECT household_key, category, day, {qty_col} q, spend, {reg_col} reg,
                      {rate_col} rate,
                      LEAD(day) OVER (PARTITION BY household_key, category ORDER BY day) - day AS gap
               FROM occ3),
    p AS (SELECT household_key, category FROM o
          GROUP BY 1,2 HAVING COUNT(*)>=5
             AND SUM(CASE WHEN rate>={DEEP_CUT} THEN 1 ELSE 0 END)>=2
             AND SUM(CASE WHEN rate<={REG_CUT} THEN 1 ELSE 0 END)>=2),
    m AS (SELECT o.household_key, o.category,
            AVG(CASE WHEN rate>={DEEP_CUT} THEN q END)   - AVG(CASE WHEN rate<={REG_CUT} THEN q END)   dq,
            AVG(CASE WHEN rate>={DEEP_CUT} THEN spend END)- AVG(CASE WHEN rate<={REG_CUT} THEN spend END) ds,
            AVG(CASE WHEN rate>={DEEP_CUT} THEN reg END) - AVG(CASE WHEN rate<={REG_CUT} THEN reg END) dr,
            AVG(CASE WHEN rate>={DEEP_CUT} THEN gap END) - AVG(CASE WHEN rate<={REG_CUT} THEN gap END) dg
          FROM o JOIN p USING (household_key, category) GROUP BY 1,2)
    SELECT * FROM m
    """).df()
    out = {"mode": label, "n_pairs": len(df)}
    for k, col in [("qty", "dq"), ("spend", "ds"), ("reg", "dr"), ("gap", "dg")]:
        d = df[["household_key", col]].dropna().rename(columns={col: "v"})
        mu, t = cluster_t(d)
        out[k], out[f"t_{k}"] = mu, t
    tgt = f" — 전영찬: qty +0.416(t 48.6) / spend -0.320(t -19.4) / reg +1.846 / gap -0.218" if targets else ""
    say(f"[A:{label}] n={out['n_pairs']:,} qty {out['qty']:+.3f}(t {out['t_qty']:.1f}) / "
        f"spend {out['spend']:+.3f}(t {out['t_spend']:.1f}) / reg {out['reg']:+.3f} / "
        f"gap {out['gap']:+.3f}(t {out['t_gap']:.1f}){tgt}")
    return out


rows = [same_day("rate_legacy", "qty_raw", "reg_legacy", "legacy(검증)", targets=True),
        same_day("rate_std", "qty_w", "gross", "standard")]
pd.DataFrame(rows).to_csv(os.path.join(OUT, "s3_sameday.csv"), index=False, encoding="utf-8-sig")

# ── B. 사후 28·56일 (표준 공식, 기준일 <= 655) ────────────────────
post = con.execute(f"""
WITH o AS (SELECT household_key, category, day, qty_w q, rate_std rate FROM occ3),
p AS (SELECT household_key, category FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5
         AND SUM(CASE WHEN rate>={DEEP_CUT} THEN 1 ELSE 0 END)>=2
         AND SUM(CASE WHEN rate<={REG_CUT} THEN 1 ELSE 0 END)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key, category)),
w AS (SELECT a.household_key, a.category, a.day, a.rate,
        COALESCE(SUM(CASE WHEN b.day<=a.day+28 THEN b.q END),0) q28,
        COALESCE(SUM(CASE WHEN b.day<=a.day+56 THEN b.q END),0) q56
      FROM s a LEFT JOIN s b
        ON a.household_key=b.household_key AND a.category=b.category
       AND b.day>a.day AND b.day<=a.day+56
      WHERE a.day <= {POST_MAX_DAY} GROUP BY 1,2,3,4),
m AS (SELECT household_key, category,
        AVG(CASE WHEN rate>={DEEP_CUT} THEN q28 END)-AVG(CASE WHEN rate<={REG_CUT} THEN q28 END) d28,
        AVG(CASE WHEN rate>={DEEP_CUT} THEN q56 END)-AVG(CASE WHEN rate<={REG_CUT} THEN q56 END) d56
      FROM w GROUP BY 1,2)
SELECT * FROM m
""").df()
for k in ["d28", "d56"]:
    d = post[["household_key", k]].dropna().rename(columns={k: "v"})
    mu, t = cluster_t(d)
    say(f"[B] 사후 {k[1:]}일 수량 {mu:+.4f} (t {t:.2f}) — 전영찬: 28일 -0.008(t -0.81) / 56일 -0.031(t -2.01)")

# ── C. 체험 전환 (첫 구매 딥할인 여부 × 56일 재구매) ──────────────
trial = con.execute(f"""
WITH first AS (
  SELECT household_key, category, MIN(day) d0 FROM occ3 GROUP BY 1,2),
f AS (SELECT o.household_key, o.category, f.d0,
        CASE WHEN o.rate_std>={DEEP_CUT} THEN 1 ELSE 0 END deep_first
      FROM occ3 o JOIN first f
        ON o.household_key=f.household_key AND o.category=f.category AND o.day=f.d0
      WHERE f.d0 <= {POST_MAX_DAY}),
rep AS (
  SELECT f.household_key, f.category, f.deep_first,
    MAX(CASE WHEN o.day>f.d0 AND o.day<=f.d0+56 THEN 1 ELSE 0 END) any_rep,
    MAX(CASE WHEN o.day>f.d0 AND o.day<=f.d0+56 AND o.rate_std<={REG_CUT} THEN 1 ELSE 0 END) reg_rep
  FROM f LEFT JOIN occ3 o
    ON o.household_key=f.household_key AND o.category=f.category
  GROUP BY 1,2,3)
SELECT deep_first, COUNT(*) n, AVG(any_rep)*100 any_rep_pct, AVG(reg_rep)*100 reg_rep_pct
FROM rep GROUP BY 1 ORDER BY 1 DESC
""").df()
trial.to_csv(os.path.join(OUT, "s3_trial_conversion.csv"), index=False, encoding="utf-8-sig")
for r in trial.itertuples():
    say(f"[C] 첫구매 {'딥할인' if r.deep_first else '비딥할인'}: n={r.n:,} / 56일 재구매 "
        f"{r.any_rep_pct:.2f}% / 정가 재구매 {r.reg_rep_pct:.2f}% — 전영찬: 38.07/33.42, 15.24/20.75")

# ── D. 28일 하류: 매장 전체 방문·지출 (카테고리별) ────────────────
con.execute(f"""
CREATE OR REPLACE TEMP VIEW hhday3 AS
SELECT household_key, day, SUM(net_sales) total FROM fct GROUP BY 1,2
""")
down = con.execute(f"""
WITH o AS (SELECT household_key, category, day, rate_std rate FROM occ3),
p AS (SELECT household_key, category FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5
         AND SUM(CASE WHEN rate>={DEEP_CUT} THEN 1 ELSE 0 END)>=2
         AND SUM(CASE WHEN rate<={REG_CUT} THEN 1 ELSE 0 END)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key, category)
      WHERE (rate>={DEEP_CUT} OR rate<={REG_CUT}) AND day <= {POST_MAX_DAY}),
w AS (SELECT s.household_key, s.category, s.day, s.rate,
        COUNT(DISTINCT h.day) visits28, COALESCE(SUM(h.total),0) spend28
      FROM s LEFT JOIN hhday3 h
        ON h.household_key=s.household_key AND h.day>s.day AND h.day<=s.day+28
      GROUP BY 1,2,3,4),
m AS (SELECT household_key, category,
        AVG(CASE WHEN rate>={DEEP_CUT} THEN visits28 END)-AVG(CASE WHEN rate<={REG_CUT} THEN visits28 END) dv,
        AVG(CASE WHEN rate>={DEEP_CUT} THEN spend28 END)-AVG(CASE WHEN rate<={REG_CUT} THEN spend28 END) dsp
      FROM w GROUP BY 1,2)
SELECT category, COUNT(*) n_pairs,
  AVG(dv) visit28_diff, AVG(dv)/(STDDEV(dv)/SQRT(COUNT(*))) t_visit,
  AVG(dsp) spend28_diff, AVG(dsp)/(STDDEV(dsp)/SQRT(COUNT(*))) t_spend
FROM m GROUP BY category HAVING COUNT(*)>=20
""").df()
down["quadrant"] = np.where((down.visit28_diff > 0) & (down.spend28_diff > 0), "Q1 강화",
                    np.where((down.visit28_diff > 0), "Q2 방문증가·지출감소",
                    np.where((down.spend28_diff > 0), "Q3 방문감소·지출증가", "Q4 약화")))
down.to_csv(os.path.join(OUT, "s3_downstream28_category.csv"), index=False, encoding="utf-8-sig")

dall = con.execute(f"""
WITH o AS (SELECT household_key, category, day, rate_std rate FROM occ3),
p AS (SELECT household_key, category FROM o
      GROUP BY 1,2 HAVING COUNT(*)>=5
         AND SUM(CASE WHEN rate>={DEEP_CUT} THEN 1 ELSE 0 END)>=2
         AND SUM(CASE WHEN rate<={REG_CUT} THEN 1 ELSE 0 END)>=2),
s AS (SELECT o.* FROM o JOIN p USING (household_key, category)
      WHERE (rate>={DEEP_CUT} OR rate<={REG_CUT}) AND day <= {POST_MAX_DAY}),
w AS (SELECT s.household_key, s.category, s.day, s.rate, COALESCE(SUM(h.total),0) spend28
      FROM s LEFT JOIN hhday3 h
        ON h.household_key=s.household_key AND h.day>s.day AND h.day<=s.day+28
      GROUP BY 1,2,3,4),
m AS (SELECT household_key, category,
        AVG(CASE WHEN rate>={DEEP_CUT} THEN spend28 END)-AVG(CASE WHEN rate<={REG_CUT} THEN spend28 END) dsp
      FROM w GROUP BY 1,2)
SELECT AVG(dsp) d, AVG(dsp)/(STDDEV(dsp)/SQRT(COUNT(*))) t, COUNT(*) n FROM m
""").df().iloc[0]
say(f"[D] 28일 매장전체 지출(딥-정가, 전체): {dall.d:+.2f}$ (t {dall.t:.2f}, n={int(dall.n):,}) "
    f"/ 사분면 분포 {down.quadrant.value_counts().to_dict()}")

# ── E. 할인친화도 (s4 고객 축 입력) ───────────────────────────────
aff = con.execute(f"""
SELECT household_key, COUNT(*) occasions,
  AVG(CASE WHEN rate_std>={DEEP_CUT} THEN 1.0 ELSE 0 END) affinity
FROM occ3 GROUP BY 1
""").df()
aff.to_csv(os.path.join(OUT, "s3_household_affinity.csv"), index=False, encoding="utf-8-sig")
say(f"[E] 가구 할인친화도 {len(aff):,}가구 저장")

con.close()
with open(os.path.join(OUT, "s3_log.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))
print("\n".join(log))
print("s3 DONE")
