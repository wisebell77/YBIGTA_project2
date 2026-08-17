"""Phase 3B-0-6 — 시간통제 재개 스크립트 (⑧, ④만)

①②③⑤⑥은 outputs/tables/phase3b0_timecontrol.csv 에 이미 저장돼 있다.
이 스크립트는 남은 ⑧ 과 ④ 만 추정해 같은 CSV에 append 한다.

사용법:
    python src/phase3b0_06_resume.py          # ⑧만 (약 12분, 권장)
    python src/phase3b0_06_resume.py all      # ⑧ + ④ (약 87분)
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, sys, time
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

from common.fe_estimator import feols1, _codes, absorb_share

ROOT = str(PROJECT_ROOT)
PANEL = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")
CSV = os.path.join(ROOT, "outputs", "tables", "phase3b0_timecontrol.csv")
MODE = sys.argv[1] if len(sys.argv) > 1 else "eight"
con = duckdb.connect(); con.execute("SET memory_limit='6GB'")
t0 = time.time()

done = pd.read_csv(CSV) if os.path.exists(CSV) else pd.DataFrame()
have = set(zip(done.get("spec", []), done.get("outcome", [])))
print(f"기존 저장분 {len(done)}행 — 중복은 건너뜁니다")

b = con.execute(f"""
SELECT p.household_key::INTEGER AS hh, p.STORE_ID::INTEGER AS store,
       p.WEEK_NO::SMALLINT AS week, p.DAY::INTEGER AS day,
       c.cat_id::SMALLINT AS cat, p.purchase::TINYINT AS purchase,
       p.quantity::REAL AS quantity, p.sales::REAL AS sales,
       p.exp_any::TINYINT AS d_any
FROM '{PANEL}' p
JOIN (SELECT COMMODITY_DESC, row_number() OVER (ORDER BY COMMODITY_DESC) - 1 AS cat_id
      FROM (SELECT DISTINCT COMMODITY_DESC FROM '{PANEL}')) c
  ON p.COMMODITY_DESC = c.COMMODITY_DESC
""").fetchnumpy()
assert int(((b["purchase"] == 0) & (b["sales"] > 0)).sum()) == 0, "행 정렬 불일치"
print(f"적재 {len(b['hh']):,}행 ({time.time()-t0:.0f}s)")

hh = b["hh"].astype(np.int64); cat = b["cat"].astype(np.int64)
store = b["store"].astype(np.int64); week = b["week"].astype(np.int64)
day = b["day"].astype(np.int64)
purchase = b["purchase"].astype(np.float64)
quantity = b["quantity"].astype(np.float64)
sales = b["sales"].astype(np.float64)
d_any = b["d_any"].astype(np.float64); del b

cl_hh = _codes(hh)
g_hhcat = _codes(hh * 1000 + cat)
g_storecat = _codes(store * 1000 + cat)
g_week = _codes(week)
g_catmonth = _codes(cat * 1000 + day // 30)
print(f"코드 생성 완료 ({time.time()-t0:.0f}s)")

TODO = [("⑧ + cat×month + WEEK", [g_hhcat, g_catmonth, g_week])]
if MODE == "all":
    TODO.append(("④ + store×cat + WEEK", [g_hhcat, g_storecat, g_week]))

rows = done.to_dict("records")
OUTS = [(purchase, "purchase"), (quantity, "quantity"), (sales, "SALES_VALUE")]
print(f"\n{'통제':24s} {'결과변수':12s} {'beta':>11s} {'SE':>10s} {'t':>7s} "
      f"{'상대%':>8s} {'N':>12s}")
for slab, fe in TODO:
    # 흡수율 진단은 3중 FE에서 회귀 1건만큼 비싸다(반복 demeaning).
    # 기본은 건너뛰고, 필요할 때만 `absorb` 인자로 켠다.
    ab = np.nan
    if "absorb" in sys.argv:
        ta = time.time()
        ab, rsd = absorb_share(d_any, fe)
        print(f"{slab:24s} 처치변동 흡수율 {100*ab:6.2f}%  residual SD {rsd:.5f} "
              f"({time.time()-ta:.0f}s)")
    for y, ylab in OUTS:
        if (slab, ylab) in have:
            print(f"{slab:24s} {ylab:12s}  (이미 저장됨 — 건너뜀)")
            continue
        t1 = time.time()
        try:
            r = feols1(y, d_any, fe, cluster=cl_hh)
            m0 = y[d_any == 0].mean()
            print(f"{slab:24s} {ylab:12s} {r['beta']:11.6f} {r['se']:10.6f} "
                  f"{r['t']:7.2f} {100*r['beta']/m0:7.2f}% {r['n']:>12,} "
                  f"({time.time()-t1:.0f}s,{r['iters']}it)")
            rows.append(dict(spec=slab, outcome=ylab, beta=r["beta"], se=r["se"],
                             t=r["t"], pct=100*r["beta"]/m0, n=r["n"],
                             absorb=round(100*ab, 2) if ab == ab else np.nan,
                             sec=round(time.time()-t1)))
        except Exception as e:
            print(f"{slab:24s} {ylab:12s}  ERROR {str(e)[:60]}")
        pd.DataFrame(rows).to_csv(CSV, index=False, encoding="utf-8-sig")
    print()
print(f"저장: {CSV}   총 {time.time()-t0:.0f}s")
