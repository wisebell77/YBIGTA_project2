"""Phase 3B-1-2 — 미래 수요 잠식 / 순증분성 ITT 추정

설계 (Phase 3B-0 과 동일):
  단위    household_key × STORE_ID × DAY × COMMODITY_DESC
  처치    exp_any  (category × store × week 의 mailer <> '0')
  주 FE   household_key × COMMODITY_DESC
  주 SE   household_key cluster   (강건성: household + store×category 2-way CGM)

결과변수
  당일   quantity, purchase           ← ΔQ0 (동일 표본에서 재추정)
  미래   q{H}, any{H}, trip{H}        ← ΔQ_H   (H = 7/14/28/56, anchor 당일 제외)

우측중도절단: DAY + H ≤ max(DAY) 인 anchor 만 사용.

실행순서는 우선순위(2-12)를 따른다: 28일 → 56일 → 7일 → 14일,
각 horizon 안에서 quantity → incidence → 2-way → 당일ΔQ0 → trip → 강건성.
M2/M3(시간통제)는 마지막 PASS 로 돌려 핵심결과 산출을 지연시키지 않는다.

결과는 추정 1건마다 outputs/tables/phase3b1_future.csv 에 append 저장 →
중단해도 재실행 시 완료분은 건너뛴다.

사용법:
    python src/phase3b1_02_estimate.py         # 전체 (PASS A + PASS B)
    python src/phase3b1_02_estimate.py a       # PASS A 만 (핵심결과)
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

from common.fe_estimator import feols1, _codes

ROOT = str(PROJECT_ROOT)
MART = os.path.join(ROOT, "data", "marts")
PANEL = os.path.join(MART, "opportunity.parquet").replace("\\", "/")
OUT = os.path.join(ROOT, "outputs", "tables")
CSV = os.path.join(OUT, "phase3b1_future.csv")
MODE = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
HOR = [28, 56, 7, 14]          # 우선순위 순서
BAR = "=" * 100
t0 = time.time()

print(f"{BAR}\nPhase 3B-1-2 — 미래 수요 잠식 ITT 추정\n{BAR}")
print("예상 소요시간: 적재 ~4분 + PASS A ~25분 + PASS B ~40분  (모드=%s)\n" % MODE)

done = pd.read_csv(CSV) if os.path.exists(CSV) else pd.DataFrame()
rows = done.to_dict("records")
have = set(done["job"]) if len(done) else set()
print(f"기존 저장분 {len(done)}행 — 동일 job 은 건너뜁니다\n")

# ── 적재: 단일 SELECT (병렬 parquet 스캔의 행순서 문제 회피) ──────────────
#    post-window 는 parquet 을 3중 join 해 되읽지 않고 numpy 로 재계산한다.
#    (searchsorted 방식은 46.7M행에서 수초, join 은 수 GB 메모리를 먹는다.
#     로직은 src/phase3b1_00_selftest.py 에서 브루트포스와 일치 검증 완료)
con = duckdb.connect(); con.execute("SET memory_limit='5GB'")
con.execute("SET preserve_insertion_order=false")
print("패널 적재 중...")
b = con.execute(f"""
SELECT p.household_key::INTEGER AS hh, p.STORE_ID::INTEGER AS store,
       p.WEEK_NO::SMALLINT AS week, p.DAY::SMALLINT AS day,
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

bad = int(((b["purchase"] == 0) & (b["sales"] > 0)).sum())
print(f"  self-check: purchase=0 인데 sales>0 → {bad}건")
assert bad == 0, "행 정렬 불일치 — 회귀 진행 금지"

hh = b["hh"]; cat = b["cat"]; store = b["store"]; week = b["week"]; day = b["day"]
d_any = b["d_any"]
Y = {"purchase": b["purchase"], "quantity": b["quantity"]}
qw = b["q_w20"]; purch = b["purchase"]
del b["sales"], b
DMAX = int(day.max())

# ── post-window 재계산 (phase3b1_01 과 동일 로직) ─────────────────────────
print("post-window 재계산 중...")
hhcat0 = _codes(hh.astype(np.int64) * 1000 + cat.astype(np.int64))
assert DMAX < 1024
key = hhcat0 * 1024 + day.astype(np.int64)
sel = purch == 1
uk, inv = np.unique(key[sel], return_inverse=True)
Qpad = np.concatenate([[0.0], np.cumsum(np.bincount(inv, weights=Y["quantity"][sel]
                                                    .astype(np.float64)))])
Wpad = np.concatenate([[0.0], np.cumsum(np.bincount(inv, weights=qw[sel]
                                                    .astype(np.float64)))])
Opad = np.concatenate([[0.0], np.cumsum(np.bincount(inv).astype(np.float64))])
del inv, qw
uke = np.unique(key[d_any == 1])
j0 = np.searchsorted(uk, key, side="right")
e0 = np.searchsorted(uke, key, side="right")
fexp = {}
for H in [7, 14, 28, 56]:
    jH = np.searchsorted(uk, key + H, side="right")
    Y[f"q{H}"] = (Qpad[jH] - Qpad[j0]).astype(np.float32)
    Y[f"trip{H}"] = np.minimum(Opad[jH] - Opad[j0], 127).astype(np.int8)
    Y[f"any{H}"] = ((jH - j0) > 0).astype(np.int8)
    if H in (28, 56):
        Y[f"w{H}"] = (Wpad[jH] - Wpad[j0]).astype(np.float32)
        eH = np.searchsorted(uke, key + H, side="right")
        fexp[H] = ((eH - e0) > 0).astype(np.int8)
        del eH
    del jH
    print(f"  H={H:2d} 완료 ({time.time()-t0:.0f}s)")
del j0, e0, Qpad, Wpad, Opad, uk, uke, key, hhcat0, sel, purch
assert not bool(((Y["any28"] == 1) & (Y["any56"] == 0)).any()), "윈도우 포함관계 위반"
print(f"  미래구매 발생행 any56=1 {int((Y['any56']>0).sum()):,} "
      f"/ DAY max {DMAX} ({time.time()-t0:.0f}s)")

# ── horizon별 부분표본 코드 캐시 ──────────────────────────────────────────
CACHE = {}


def subset(H):
    if CACHE.get("H") != H:
        CACHE.clear()
        t1 = time.time()
        m = day <= (DMAX - H)
        CACHE["H"] = H
        CACHE["m"] = m
        CACHE["D"] = d_any[m].astype(np.float64)
        CACHE["cl"] = _codes(hh[m])
        CACHE["hhcat"] = _codes(hh[m].astype(np.int64) * 1000 + cat[m].astype(np.int64))
        print(f"  [H={H}] 부분표본 {int(m.sum()):,}행 / hh×cat "
              f"{int(CACHE['hhcat'].max())+1:,} 코드생성 {time.time()-t1:.0f}s")
    return CACHE


def fe_extra(kind):
    """추가 FE 를 필요할 때만 생성 (메모리 절약)"""
    if kind in CACHE:
        return CACHE[kind]
    m = CACHE["m"]
    if kind == "week":
        CACHE[kind] = _codes(week[m])
    elif kind == "catmonth":
        CACHE[kind] = _codes(cat[m].astype(np.int64) * 1000
                             + (day[m].astype(np.int64) // 30))
    elif kind == "storecat":
        CACHE[kind] = _codes(store[m].astype(np.int64) * 1000
                             + cat[m].astype(np.int64))
    return CACHE[kind]


def save():
    pd.DataFrame(rows).to_csv(CSV, index=False, encoding="utf-8-sig")


def run(job, H, ycol, spec, fes, two_way=False, sub=None, sublab=""):
    """job: 고유키 / ycol: Y 의 키 / fes: ['hhcat','week',...] / sub: 추가 부분표본 마스크"""
    if job in have:
        print(f"  {job:38s} (이미 저장됨 — 건너뜀)")
        return
    C = subset(H)
    m = C["m"]
    y = Y[ycol][m].astype(np.float64)
    D = C["D"]
    G = [C["hhcat"] if f == "hhcat" else fe_extra(f) for f in fes]
    cl = C["cl"]; cl2 = fe_extra("storecat") if two_way else None
    if sub is not None:
        s = sub[m]
        y = y[s]; D = D[s]
        G = [_codes(g[s]) for g in G]
        cl = _codes(cl[s]); cl2 = _codes(cl2[s]) if cl2 is not None else None
    t1 = time.time()
    try:
        r = feols1(y, D, G, cluster=cl, cluster2=cl2)
    except Exception as e:
        print(f"  {job:38s} ERROR {str(e)[:70]}")
        return
    m0 = float(y[D == 0].mean()); m1 = float(y[D == 1].mean())
    pct = 100 * r["beta"] / m0 if m0 else np.nan
    print(f"  {job:38s} beta={r['beta']:+11.6f} SE={r['se']:9.6f} t={r['t']:8.2f} "
          f"p={r['p']:9.3g} base={m0:9.6f} {pct:+7.2f}% N={r['n']:>11,} "
          f"({time.time()-t1:.0f}s)")
    rows.append(dict(job=job, horizon=H, outcome=ycol, spec=spec,
                     vcov="hh+store×cat 2-way" if two_way else "hh 1-way",
                     sample=sublab or "full", beta=r["beta"], se=r["se"], t=r["t"],
                     p=r["p"], base_unexposed=m0, mean_exposed=m1, pct=pct,
                     n=r["n"], households=int(cl.max()) + 1,
                     categories=len(np.unique(cat[m][sub[m]] if sub is not None
                                              else cat[m])),
                     iters=r["iters"], sec=round(time.time() - t1)))
    save()


# ══ PASS A — 핵심결과 (M1 hh×cat) ═══════════════════════════════════════
print(f"\n{BAR}\nPASS A — 핵심결과  M1: household_key × COMMODITY_DESC FE\n{BAR}")
for H in HOR:
    print(f"\n── H = {H}일 ──")
    core = H in (28, 56)
    run(f"A|{H}|q{H}|M1",    H, f"q{H}",    "M1 hh×cat", ["hhcat"])
    run(f"A|{H}|any{H}|M1",  H, f"any{H}",  "M1 hh×cat", ["hhcat"])
    if core:
        run(f"A|{H}|q{H}|M1|2w",   H, f"q{H}",   "M1 hh×cat", ["hhcat"], two_way=True)
        run(f"A|{H}|any{H}|M1|2w", H, f"any{H}", "M1 hh×cat", ["hhcat"], two_way=True)
    # 동일 부분표본에서의 당일 효과 (잠식률 분모를 표본정합적으로 맞추기 위함)
    run(f"A|{H}|day0_q|M1",   H, "quantity", "M1 hh×cat", ["hhcat"])
    run(f"A|{H}|day0_buy|M1", H, "purchase", "M1 hh×cat", ["hhcat"])
    run(f"A|{H}|trip{H}|M1",  H, f"trip{H}",  "M1 hh×cat", ["hhcat"])
    if core:
        run(f"A|{H}|w{H}|M1", H, f"w{H}", "M1 hh×cat (수량 winsor20)", ["hhcat"])
        run(f"A|{H}|q{H}|M1|clean", H, f"q{H}", "M1 hh×cat", ["hhcat"],
            sub=(fexp[H] == 0), sublab="clean-window (후속노출 없음)")
        run(f"A|{H}|any{H}|M1|clean", H, f"any{H}", "M1 hh×cat", ["hhcat"],
            sub=(fexp[H] == 0), sublab="clean-window (후속노출 없음)")
        # clean-window 안에서의 당일 효과 — 잠식률 분자·분모를 같은 표본으로 맞추기 위함
        run(f"A|{H}|day0_q|M1|clean", H, "quantity", "M1 hh×cat", ["hhcat"],
            sub=(fexp[H] == 0), sublab="clean-window (후속노출 없음)")
        run(f"A|{H}|day0_buy|M1|clean", H, "purchase", "M1 hh×cat", ["hhcat"],
            sub=(fexp[H] == 0), sublab="clean-window (후속노출 없음)")

# fexp56=0 부분표본 안에서 당일 → 28일 → 56일 궤적을 **같은 표본**으로 추적한다.
# (fexp56=0 ⊂ fexp28=0 이므로 28일 clean 과 56일 clean 은 서로 다른 표본이다.
#  회복 여부를 보려면 표본을 고정해야 한다.)
print(f"\n── clean-window(fexp56=0) 고정표본 궤적 ──")
run("A|56|q28|M1|clean56", 56, "q28", "M1 hh×cat", ["hhcat"],
    sub=(fexp[56] == 0), sublab="clean56 고정표본")
run("A|56|any28|M1|clean56", 56, "any28", "M1 hh×cat", ["hhcat"],
    sub=(fexp[56] == 0), sublab="clean56 고정표본")
print(f"\nPASS A 완료 ({time.time()-t0:.0f}s)")

# ══ PASS B — 시간통제 강건성 (M2, M3) ═══════════════════════════════════
if MODE != "a":
    print(f"\n{BAR}\nPASS B1 — 시간통제 M2 (= M1 + WEEK_NO), 4개 horizon 전부\n{BAR}")
    for H in HOR:
        print(f"\n── H = {H}일 ──")
        run(f"B|{H}|q{H}|M2",   H, f"q{H}",   "M2 +WEEK", ["hhcat", "week"])
        run(f"B|{H}|any{H}|M2", H, f"any{H}", "M2 +WEEK", ["hhcat", "week"])

    # M3(3중 FE)는 Phase 3B-0 의 ⑧ 에서 전체 패널 1건에 1~2시간이 걸렸다.
    # 핵심 horizon(28·56)에만 적용하고, 잠식률 분모를 같은 스펙으로 맞추기 위해
    # 당일 효과(day0_q)도 반드시 M3 로 함께 추정한다.
    print(f"\n{BAR}\nPASS B2 — 시간통제 M3 (= M1 + cat×month(30일) + WEEK_NO)\n"
          f"  ⚠️ 매우 느림 — 핵심 horizon 28·56 에만 적용. 1건마다 CSV 저장됨\n{BAR}")
    for H in [56, 28]:
        print(f"\n── H = {H}일 ──")
        run(f"B|{H}|day0_q|M3", H, "quantity", "M3 +cat×month +WEEK",
            ["hhcat", "catmonth", "week"])
        run(f"B|{H}|q{H}|M3",   H, f"q{H}",   "M3 +cat×month +WEEK",
            ["hhcat", "catmonth", "week"])
        run(f"B|{H}|any{H}|M3", H, f"any{H}", "M3 +cat×month +WEEK",
            ["hhcat", "catmonth", "week"])

save()
print(f"\n{BAR}\n저장: {CSV}   총 {time.time()-t0:.0f}s\n{BAR}")
