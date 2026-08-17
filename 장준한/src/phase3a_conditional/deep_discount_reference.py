"""Phase 3A-7 — PDF 딥할인(실현할인) 보조 설계 재현
목적: ITT 결과와 PDF 숫자의 차이가 '처치 정의' 때문인지 분해하기 위한 대조군.

PDF 보조 설계 정의 (p.10):
  실현 할인율 >= 30% (딥할인)  vs  <= 2% (정가)   ... occasion 수준
  표본: 구매기회>=5 & 딥>=2 & 정가>=2
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, warnings
import numpy as np, pandas as pd, pyfixest as pf

warnings.filterwarnings("ignore")
ROOT = str(PROJECT_ROOT)
DB = os.path.join(ROOT, "data", "interim", "dunn.duckdb")
OUT = os.path.join(ROOT, "outputs", "tables")
BAR = "=" * 94
con = duckdb.connect(DB, read_only=True)

df = con.execute("""
WITH tx AS (
    SELECT t.household_key, t.DAY, t.WEEK_NO, t.STORE_ID, t.PRODUCT_ID,
           p.COMMODITY_DESC, t.QUANTITY, t.SALES_VALUE, t.RETAIL_DISC,
           t.COUPON_DISC, t.COUPON_MATCH_DISC
    FROM transaction_data t JOIN product p ON t.PRODUCT_ID=p.PRODUCT_ID
    WHERE t.WEEK_NO BETWEEN 9 AND 101
      AND t.STORE_ID IN (SELECT DISTINCT STORE_ID FROM causal_data)
      AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
      AND t.SALES_VALUE > 0
),
occ AS (
    SELECT household_key, COMMODITY_DESC, DAY, any_value(WEEK_NO) WEEK_NO,
           max(STORE_ID) STORE_ID,
           SUM(QUANTITY) q_raw, SUM(SALES_VALUE) sales,
           SUM(SALES_VALUE-RETAIL_DISC-COUPON_DISC-COUPON_MATCH_DISC) reg_value,
           SUM(-RETAIL_DISC) / NULLIF(SUM(SALES_VALUE-RETAIL_DISC),0) AS rate
    FROM tx GROUP BY 1,2,3
),
vis AS (
    SELECT household_key, DAY,
           DENSE_RANK() OVER (PARTITION BY household_key ORDER BY DAY) visit_no
    FROM (SELECT DISTINCT household_key, DAY FROM tx)
),
cls AS (
    SELECT o.*, v.visit_no,
           CASE WHEN o.rate>=0.30 THEN 1 WHEN o.rate<=0.02 THEN 0 END AS D
    FROM occ o JOIN vis v USING (household_key, DAY)
),
gaps AS (
    SELECT *,
           LEAD(DAY)      OVER w - DAY      AS gap_days,
           LEAD(visit_no) OVER w - visit_no AS gap_visits
    FROM cls
    WINDOW w AS (PARTITION BY household_key, COMMODITY_DESC ORDER BY DAY)
),
pair AS (
    SELECT household_key, COMMODITY_DESC, COUNT(*) n,
           COUNT(*) FILTER (WHERE D=1) nd, COUNT(*) FILTER (WHERE D=0) nf
    FROM gaps WHERE D IS NOT NULL GROUP BY 1,2
)
SELECT g.household_key, g.COMMODITY_DESC, g.STORE_ID, g.WEEK_NO, g.D,
       g.q_raw, g.sales, g.reg_value, g.gap_days, g.gap_visits, g.rate
FROM gaps g JOIN pair p USING (household_key, COMMODITY_DESC)
WHERE g.D IS NOT NULL AND p.n>=5 AND p.nd>=2 AND p.nf>=2
""").df()

df["cat"] = pd.factorize(df.COMMODITY_DESC)[0]
df["hh_cat"] = pd.factorize(df.household_key.astype(str)+"_"+df.cat.astype(str))[0]

print(BAR)
print("PDF 딥할인 보조 설계 재현 (실현 할인율 >=30% vs <=2%)")
print(BAR)
print(f"\n  표본: occasion {len(df):,}  가구 {df.household_key.nunique():,}  "
      f"카테고리 {df.cat.nunique()}  쌍 {df.hh_cat.nunique():,}")
print(f"        PDF 목표 — 쌍 38,322 / 가구 2,167 / 카테고리 212 / 구매기회 783,096")
print(f"  딥할인 occasion {int(df.D.sum()):,} / 정가 occasion {int((1-df.D).sum()):,}")
print(f"  딥할인 평균 할인율 {100*df.loc[df.D==1,'rate'].mean():.2f}%  "
      f"(PDF 41.2%) / 정가 {100*df.loc[df.D==0,'rate'].mean():.2f}%")

TARGETS = {"다음구매 일수": "-0.324일 (t=-1.30)", "다음구매 방문수": "-0.103회 (t=-1.85)",
           "occasion당 수량": "+0.406개 (+26.4%, t=68.5)",
           "occasion당 지출액": "-$0.325 (-9.6%, t=-27.4)",
           "occasion당 정가환산": "+$1.827 (+53.7%, t=94.1)"}
OUTCOMES = [("gap_days","다음구매 일수"), ("gap_visits","다음구매 방문수"),
            ("q_raw","occasion당 수량"), ("sales","occasion당 지출액"),
            ("reg_value","occasion당 정가환산")]

rows = []
for mlab, fe in [("M0 naive", None), ("M1 hh×cat", "hh_cat")]:
    print(f"\n  ═══ {mlab} (household cluster SE) ═══")
    print(f"  {'결과변수':18s} {'beta':>10s} {'SE':>8s} {'t':>8s} "
          f"{'정가평균':>9s} {'%효과':>9s}   PDF")
    for y, ylab in OUTCOMES:
        d = df[df[y].notna()]
        fml = f"{y} ~ D" + (f" | {fe}" if fe else "")
        m = pf.feols(fml, data=d, vcov={"CRV1": "household_key"})
        b, se, t = m.coef()["D"], m.se()["D"], m.tstat()["D"]
        base = d.loc[d.D == 0, y].mean()
        print(f"  {ylab:18s} {b:10.4f} {se:8.4f} {t:8.2f} {base:9.3f} "
              f"{100*b/base:8.2f}%   {TARGETS[ylab]}")
        rows.append(dict(design="딥할인(실현할인)", model=mlab, outcome=ylab,
                         beta=b, se=se, t=t, p=m.pvalue()["D"], base=base,
                         pct=100*b/base, n=len(d),
                         hh=d.household_key.nunique(), cat=d.cat.nunique(),
                         pdf=TARGETS[ylab]))

pd.DataFrame(rows).to_csv(os.path.join(OUT, "phase3a_pdf_deepdisc.csv"),
                          index=False, encoding="utf-8-sig")
print(f"\n{BAR}")
