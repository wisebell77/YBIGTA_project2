"""Phase 3B-1-0 — post-window prefix-sum 로직 자가검증

소수 가구만 뽑아 prefix-sum/searchsorted 결과를 **무식한 이중루프**와 대조한다.
46.7M행에 돌리기 전에 논리 오류(당일 포함 여부, 그룹 경계 누수)를 잡는 용도.
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, sys
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

from common.fe_estimator import _codes

ROOT = str(PROJECT_ROOT)
PANEL = os.path.join(ROOT, "data", "marts", "opportunity.parquet").replace("\\", "/")
HOR = [7, 14, 28, 56]
rng = np.random.default_rng(7)

con = duckdb.connect(); con.execute("SET memory_limit='2GB'")
hhs = con.execute(f"SELECT DISTINCT household_key FROM '{PANEL}' ORDER BY 1 "
                  f"LIMIT 12").fetchnumpy()["household_key"]
lst = ",".join(str(int(x)) for x in hhs)
b = con.execute(f"""
SELECT p.household_key::INTEGER AS hh, p.DAY::SMALLINT AS day,
       c.cat_id::SMALLINT AS cat, p.purchase::TINYINT AS purchase,
       p.quantity::REAL AS quantity, p.exp_any::TINYINT AS d_any
FROM '{PANEL}' p
JOIN (SELECT COMMODITY_DESC, row_number() OVER (ORDER BY COMMODITY_DESC) - 1 AS cat_id
      FROM (SELECT DISTINCT COMMODITY_DESC FROM '{PANEL}')) c
  ON p.COMMODITY_DESC = c.COMMODITY_DESC
WHERE p.household_key IN ({lst})
""").fetchnumpy()
con.close()

hh = b["hh"].astype(np.int32); cat = b["cat"].astype(np.int16)
day = b["day"].astype(np.int16); purch = b["purchase"].astype(np.int8)
qty = b["quantity"].astype(np.float32); d_any = b["d_any"].astype(np.int8)
n = len(hh)
print(f"검증표본 {n:,}행 / 가구 {len(np.unique(hh))} / 카테고리 {len(np.unique(cat))}")

# ── 본 스크립트와 동일한 로직 ────────────────────────────────────────────
hhcat = _codes(hh.astype(np.int64) * 1000 + cat.astype(np.int64))
key = hhcat * 1024 + day.astype(np.int64)
sel = purch == 1
uk, inv = np.unique(key[sel], return_inverse=True)
g_qty = np.bincount(inv, weights=qty[sel].astype(np.float64))
g_occ = np.bincount(inv).astype(np.float64)
Qpad = np.concatenate([[0.0], np.cumsum(g_qty)])
Opad = np.concatenate([[0.0], np.cumsum(g_occ)])
uke = np.unique(key[d_any == 1])
j0 = np.searchsorted(uk, key, side="right")
e0 = np.searchsorted(uke, key, side="right")

FAST = {}
for H in HOR:
    jH = np.searchsorted(uk, key + H, side="right")
    eH = np.searchsorted(uke, key + H, side="right")
    FAST[H] = dict(q=Qpad[jH] - Qpad[j0], trip=Opad[jH] - Opad[j0],
                   any=((jH - j0) > 0).astype(np.int8),
                   fexp=((eH - e0) > 0).astype(np.int8))

# ── 무식한 브루트포스 (임의 400 anchor) ──────────────────────────────────
idx = rng.choice(n, size=400, replace=False)
print(f"\n{'H':>4s} {'q 불일치':>10s} {'trip 불일치':>12s} {'any 불일치':>11s} "
      f"{'fexp 불일치':>12s}")
allok = True
for H in HOR:
    bq = bt = ba = bf = 0
    for i in idx:
        m = (hh == hh[i]) & (cat == cat[i]) & (day > day[i]) & (day <= day[i] + H)
        q = float(qty[m][purch[m] == 1].sum())
        tr = float((purch[m] == 1).sum())
        an = int(tr > 0)
        fx = int((d_any[m] == 1).any())
        bq += abs(q - FAST[H]["q"][i]) > 1e-3
        bt += abs(tr - FAST[H]["trip"][i]) > 1e-9
        ba += an != FAST[H]["any"][i]
        bf += fx != FAST[H]["fexp"][i]
    allok &= (bq + bt + ba + bf) == 0
    print(f"{H:>4d} {bq:>10d} {bt:>12d} {ba:>11d} {bf:>12d}")

# ── anchor 당일 제외 확인: 당일 구매가 있는 anchor 라도 q0 에 포함되면 안 됨 ──
same = purch == 1
chk = 0
for i in rng.choice(np.flatnonzero(same), size=min(200, int(same.sum())),
                    replace=False):
    m = (hh == hh[i]) & (cat == cat[i]) & (day == day[i])
    sameday = float(qty[m][purch[m] == 1].sum())
    m7 = (hh == hh[i]) & (cat == cat[i]) & (day > day[i]) & (day <= day[i] + 7)
    chk += abs(FAST[7]["q"][i] - float(qty[m7][purch[m7] == 1].sum())) > 1e-3
print(f"\nanchor 당일 제외 검증 (당일구매 anchor 200건): 불일치 {chk}건 "
      f"— 당일수량이 post 에 섞이면 여기서 잡힌다")

print(f"\n{'✅ 전부 일치 — 본 계산 진행 가능' if allok and chk == 0 else '❌ 불일치 — 중단'}")
sys.exit(0 if (allok and chk == 0) else 1)
