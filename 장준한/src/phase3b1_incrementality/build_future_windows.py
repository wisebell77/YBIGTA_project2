"""Phase 3B-1-1 — 미래 수요 잠식 / 순증분성 : post-window 마트 구축

anchor = Phase 3B-0 과 동일한 shopping opportunity
         (household_key × STORE_ID × DAY × COMMODITY_DESC, 46.7M행)

각 anchor t 에 대해 동일 household × COMMODITY_DESC 의
t+1 ~ t+H (H = 7/14/28/56) 미래구매를 집계한다. **anchor 당일은 제외**.

계산방식 — range self-join 금지:
  key = hhcat_code * 1024 + DAY   (DAY ≤ 705 < 1024 이므로 가구·카테고리 그룹이
  key 공간에서 서로 겹치지 않는다)
  구매가 발생한 (hh,cat,day) 만 모아 정렬 후 prefix-sum 을 만들고,
  searchsorted 로 t 와 t+H 의 누적값을 뽑아 차분한다.
  side='right' 이므로 t 시점 누적에는 anchor 당일이 포함되고,
  차분 결과는 정확히 (t, t+H] 구간이 된다.
  → 수억행 self-join 없이 4개 horizon 을 46.7M행 전체에 대해 수초 만에 계산.

우측중도절단: DAY + H ≤ max(DAY) 인 anchor 만 사용. 관측종료 이후를 0으로 넣지 않는다.

산출:
  data/marts/phase3b1_hhcatday.parquet   — (hh,cat,day) 구매 집계
  data/marts/phase3b1_postwindow.parquet — anchor 수준 post-window (미래구매 발생행만;
                                            없는 행은 모든 horizon 에서 0)
  data/marts/phase3b1_cleanwin.parquet   — 후속 노출 없는 anchor (없는 행은 fexp=1)
  outputs/tables/phase3b1_samples.csv    — horizon별 분석표본/중도절단
  outputs/tables/phase3b1_futureexp.csv  — 후속 전단지 노출 진단
  outputs/tables/phase3b1_rawmeans.csv   — FE 없는 원시 평균 (참고)
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

from common.fe_estimator import _codes

ROOT = str(PROJECT_ROOT)
PANEL = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")
MART = os.path.join(ROOT, "data", "marts")
OUT = os.path.join(ROOT, "outputs", "tables")
HOR = [7, 14, 28, 56]
BAR = "=" * 100
t0 = time.time()

print(f"{BAR}\nPhase 3B-1-1 — post-window 마트 구축\n{BAR}")
print("예상 소요시간: 적재 ~3분 + prefix-sum/searchsorted ~2분 + 저장 ~3분 ≈ 8분\n")

con = duckdb.connect(); con.execute("SET memory_limit='5GB'")
print("패널 적재 중... (단일 SELECT — 컬럼별 분리조회 금지)")
b = con.execute(f"""
SELECT p.household_key::INTEGER AS hh, p.DAY::SMALLINT AS day,
       c.cat_id::SMALLINT AS cat, p.purchase::TINYINT AS purchase,
       p.quantity::REAL AS quantity, p.q_w20::REAL AS q_w20,
       p.sales::REAL AS sales, p.exp_any::TINYINT AS d_any
FROM '{PANEL}' p
JOIN (SELECT COMMODITY_DESC, row_number() OVER (ORDER BY COMMODITY_DESC) - 1 AS cat_id
      FROM (SELECT DISTINCT COMMODITY_DESC FROM '{PANEL}')) c
  ON p.COMMODITY_DESC = c.COMMODITY_DESC
""").fetchnumpy()
con.close()
n = len(b["hh"])
print(f"  {n:,}행 적재 ({time.time()-t0:.0f}s)")

# ── 정합성 자가검증 (행 정렬이 어긋나면 여기서 잡힌다) ─────────────────────
bad = int(((b["purchase"] == 0) & (b["sales"] > 0)).sum())
print(f"  self-check: purchase=0 인데 sales>0 → {bad}건")
assert bad == 0, "행 정렬 불일치 — 회귀 진행 금지"

hh = b["hh"].astype(np.int32); cat = b["cat"].astype(np.int16)
day = b["day"].astype(np.int16); purch = b["purchase"].astype(np.int8)
qty = b["quantity"].astype(np.float32); qw = b["q_w20"].astype(np.float32)
d_any = b["d_any"].astype(np.int8)
del b

DMAX = int(day.max())
print(f"  DAY 범위 {int(day.min())}–{DMAX} / 가구 {len(np.unique(hh)):,} "
      f"/ 카테고리 {int(cat.max())+1}")

hhcat = _codes(hh.astype(np.int64) * 1000 + cat.astype(np.int64))
assert DMAX < 1024
key = hhcat * 1024 + day.astype(np.int64)
print(f"  hh×cat pair {int(hhcat.max())+1:,} / key 구성 완료 ({time.time()-t0:.0f}s)")

# ── (hh,cat,day) 구매 집계 → prefix sum ───────────────────────────────────
sel = purch == 1
uk, inv = np.unique(key[sel], return_inverse=True)
g_qty = np.bincount(inv, weights=qty[sel].astype(np.float64))
g_qw = np.bincount(inv, weights=qw[sel].astype(np.float64))
g_occ = np.bincount(inv).astype(np.float64)      # 그 날 그 카테고리 구매 trip 수
del inv
print(f"  구매발생 (hh,cat,day) {len(uk):,}건 / anchor행 중 구매 {int(sel.sum()):,}건")

Qpad = np.concatenate([[0.0], np.cumsum(g_qty)])
Wpad = np.concatenate([[0.0], np.cumsum(g_qw)])
Opad = np.concatenate([[0.0], np.cumsum(g_occ)])
uke = np.unique(key[d_any == 1])                 # 노출 (hh,cat,day)
print(f"  노출 (hh,cat,day) {len(uke):,}건 ({time.time()-t0:.0f}s)")

j0 = np.searchsorted(uk, key, side="right")
e0 = np.searchsorted(uke, key, side="right")
print(f"  anchor 기준점 계산 완료 ({time.time()-t0:.0f}s)")

POST = {}
for H in HOR:
    jH = np.searchsorted(uk, key + H, side="right")
    POST[f"q{H}"] = (Qpad[jH] - Qpad[j0]).astype(np.float32)
    POST[f"trip{H}"] = np.minimum(Opad[jH] - Opad[j0], 127).astype(np.int8)
    POST[f"any{H}"] = ((jH - j0) > 0).astype(np.int8)
    if H in (28, 56):
        POST[f"w{H}"] = (Wpad[jH] - Wpad[j0]).astype(np.float32)
    del jH
    eH = np.searchsorted(uke, key + H, side="right")
    POST[f"fexp{H}"] = ((eH - e0) > 0).astype(np.int8)
    del eH
    print(f"  H={H:2d} 완료 ({time.time()-t0:.0f}s)")
del j0, e0, Qpad, Wpad, Opad, uk, uke, key, qw

# any28=1 ⟹ any56=1, fexp28=1 ⟹ fexp56=1 (윈도우 포함관계) 검증
assert not bool(((POST["any28"] == 1) & (POST["any56"] == 0)).any())
assert not bool(((POST["fexp28"] == 1) & (POST["fexp56"] == 0)).any())

# ── horizon별 분석표본 / 우측중도절단 ─────────────────────────────────────
print(f"\n{BAR}\n§1  horizon별 분석표본 · 우측중도절단  (관측종료 DAY {DMAX})\n{BAR}")
print(f"{'H':>4s} {'전체 anchor':>14s} {'사용 N':>14s} {'절단제외 N':>13s} "
      f"{'제외%':>7s} {'가구':>7s} {'카테고리':>8s} {'hh×cat pair':>13s}")
srows = []
for H in HOR:
    m = day <= (DMAX - H)
    nu = int(m.sum())
    nhh = len(np.unique(hh[m])); ncat = len(np.unique(cat[m]))
    npair = len(np.unique(hhcat[m]))
    print(f"{H:>4d} {n:>14,} {nu:>14,} {n-nu:>13,} {100*(n-nu)/n:>6.2f}% "
          f"{nhh:>7,} {ncat:>8,} {npair:>13,}")
    srows.append(dict(horizon=H, anchors_total=n, n_used=nu, n_censored=n - nu,
                      pct_censored=100 * (n - nu) / n, households=nhh,
                      categories=ncat, hh_cat_pairs=npair,
                      last_usable_day=DMAX - H, dmax=DMAX))
pd.DataFrame(srows).to_csv(os.path.join(OUT, "phase3b1_samples.csv"),
                           index=False, encoding="utf-8-sig")

# ── 후속 전단지 노출 진단 (2-10) ──────────────────────────────────────────
print(f"\n{BAR}\n§2  후속 전단지 노출 진단  (post-treatment 변수 — 통제변수로 넣지 않는다)\n{BAR}")
print(f"{'H':>4s} {'future노출률':>14s} {'노출anchor 이후':>16s} "
      f"{'미노출anchor 이후':>17s} {'차이':>9s} {'clean N':>14s} {'clean%':>8s}")
frows = []
for H in HOR:
    m = day <= (DMAX - H)
    fe = POST[f"fexp{H}"][m]; dm = d_any[m]
    a = float(fe.mean()); e1 = float(fe[dm == 1].mean()); e0_ = float(fe[dm == 0].mean())
    clean = int((fe == 0).sum())
    print(f"{H:>4d} {100*a:>13.2f}% {100*e1:>15.2f}% {100*e0_:>16.2f}% "
          f"{100*(e1-e0_):>8.2f}p {clean:>14,} {100*clean/int(m.sum()):>7.2f}%")
    frows.append(dict(horizon=H, future_exp_rate=a, exp_after_exposed=e1,
                      exp_after_unexposed=e0_, diff_pp=100 * (e1 - e0_),
                      clean_window_n=clean, clean_window_share=clean / int(m.sum())))
pd.DataFrame(frows).to_csv(os.path.join(OUT, "phase3b1_futureexp.csv"),
                           index=False, encoding="utf-8-sig")

# ── 원시 평균 (참고) ──────────────────────────────────────────────────────
print(f"\n{BAR}\n§3  원시 평균 (FE 없음 — 참고용)\n{BAR}")
print(f"{'H':>4s} {'결과':>8s} {'미노출':>12s} {'노출':>12s} {'차':>13s} {'상대%':>9s}")
rrows = []
for H in HOR:
    m = day <= (DMAX - H); dm = d_any[m]
    for lab in ("q", "any", "trip"):
        y = POST[f"{lab}{H}"][m].astype(np.float64)
        a0 = y[dm == 0].mean(); a1 = y[dm == 1].mean()
        print(f"{H:>4d} {lab:>8s} {a0:>12.6f} {a1:>12.6f} {a1-a0:>+13.6f} "
              f"{100*(a1-a0)/a0:>+8.2f}%")
        rrows.append(dict(horizon=H, outcome=lab, mean_unexp=a0, mean_exp=a1,
                          raw_diff=a1 - a0, raw_pct=100 * (a1 - a0) / a0))
pd.DataFrame(rrows).to_csv(os.path.join(OUT, "phase3b1_rawmeans.csv"),
                           index=False, encoding="utf-8-sig")

# ── 캐시 저장 ─────────────────────────────────────────────────────────────
print(f"\n{BAR}\n§4  parquet 캐시 저장\n{BAR}")
con = duckdb.connect(); con.execute("SET memory_limit='4GB'")

agg = pd.DataFrame({"hh": hh[sel], "cat": cat[sel], "day": day[sel],
                    "quantity": qty[sel]}).groupby(["hh", "cat", "day"],
                                                   as_index=False).agg(
    quantity=("quantity", "sum"), trips=("quantity", "size"))
con.register("agg", agg)
p1 = os.path.join(MART, "phase3b1_hhcatday.parquet").replace("\\", "/")
con.execute(f"COPY agg TO '{p1}' (FORMAT PARQUET, COMPRESSION ZSTD)")
print(f"  (hh,cat,day) 구매집계 {len(agg):,}행 → phase3b1_hhcatday.parquet "
      f"({os.path.getsize(p1)/1e6:.0f}MB)")
del agg

PCOL = [f"{p}{H}" for H in HOR for p in ("q", "trip", "any")] + ["w28", "w56"]
keep = POST["any56"] == 1
pw = pd.DataFrame({"hh": hh[keep], "cat": cat[keep], "day": day[keep],
                   **{k: POST[k][keep] for k in PCOL}}
                  ).drop_duplicates(subset=["hh", "cat", "day"])
con.register("pw", pw)
p2 = os.path.join(MART, "phase3b1_postwindow.parquet").replace("\\", "/")
con.execute(f"COPY pw TO '{p2}' (FORMAT PARQUET, COMPRESSION ZSTD)")
print(f"  anchor post-window {len(pw):,}행 → phase3b1_postwindow.parquet "
      f"({os.path.getsize(p2)/1e6:.0f}MB)")
print(f"     ※ 여기 없는 (hh,cat,day) 는 모든 horizon 에서 미래구매 0")
del pw

keepc = POST["fexp28"] == 0
cw = pd.DataFrame({"hh": hh[keepc], "cat": cat[keepc], "day": day[keepc],
                   "fexp28": POST["fexp28"][keepc], "fexp56": POST["fexp56"][keepc]}
                  ).drop_duplicates(subset=["hh", "cat", "day"])
con.register("cw", cw)
p3 = os.path.join(MART, "phase3b1_cleanwin.parquet").replace("\\", "/")
con.execute(f"COPY cw TO '{p3}' (FORMAT PARQUET, COMPRESSION ZSTD)")
print(f"  clean-window(fexp28=0) {len(cw):,}행 → phase3b1_cleanwin.parquet "
      f"({os.path.getsize(p3)/1e6:.0f}MB)")
print(f"     ※ 여기 없는 (hh,cat,day) 는 fexp28=fexp56=1")
con.close()
print(f"\n{BAR}\n완료 — 총 {time.time()-t0:.0f}s\n{BAR}")
