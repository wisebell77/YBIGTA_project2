"""Phase 3B-1-3 — 증분성 곡선 표 생성

outputs/tables/phase3b1_future.csv (추정 결과) 를 읽어
  Horizon / Immediate effect / Post effect / Net cumulative / Cannibalization / Incrementality
표를 만들어 outputs/tables/phase3b1_incrementality_curve.csv 로 저장한다.

분모 ΔQ0 는 **각 horizon 의 동일 부분표본에서 재추정한 당일 total quantity ITT beta**
(job = A|H|day0_q|M1) 를 쓴다. 우측중도절단으로 표본이 다르면 분모도 달라져야
잠식률이 내적으로 정합적이기 때문이다. 전체표본 ΔQ0 는 H=0 행에 함께 싣는다.

ΔQ_H > 0 인 경우 (post-lift) 잠식률을 억지로 음수로 적지 않고
'관측되지 않음' 으로 표기하며, cumulative multiplier 를 100% 로 cap 하지 않는다.
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import os, sys
import numpy as np, pandas as pd
sys.stdout.reconfigure(encoding="utf-8")

ROOT = str(PROJECT_ROOT)
OUT = os.path.join(ROOT, "outputs", "tables")
F = pd.read_csv(os.path.join(OUT, "phase3b1_future.csv"))
M0 = pd.read_csv(os.path.join(OUT, "phase3b0_main_m1.csv"))
HOR = [7, 14, 28, 56]
BAR = "=" * 108


def get(job, col="beta"):
    r = F[F["job"] == job]
    return float(r.iloc[0][col]) if len(r) else np.nan


def block(kind, day0_job, post_pre, label):
    """kind: 'quantity' | 'incidence'"""
    full = M0[(M0["outcome"] == ("quantity (0 포함)" if kind == "quantity"
                                 else "purchase (0/1)"))
              & (M0["vcov"] == "hh 1-way")]
    b_full = float(full.iloc[0]["beta"])
    rows = [dict(metric=label, horizon=0, n_used=int(full.iloc[0]["n"]),
                 immediate=b_full, immediate_se=float(full.iloc[0]["se"]),
                 immediate_t=float(full.iloc[0]["t"]),
                 post=0.0, post_se=np.nan, post_t=np.nan, post_pct=np.nan,
                 net_cumulative=b_full, cannibalization=0.0, incrementality=1.0,
                 cumulative_multiplier=1.0, verdict="당일 기준효과 (전체표본)")]
    for H in HOR:
        d0 = get(day0_job.format(H=H))
        pb = get(post_pre.format(H=H))
        rows.append(_row(label, H, d0, get(day0_job.format(H=H), "se"),
                         get(day0_job.format(H=H), "t"),
                         pb, get(post_pre.format(H=H), "se"),
                         get(post_pre.format(H=H), "t"),
                         get(post_pre.format(H=H), "pct"),
                         get(post_pre.format(H=H), "n")))
    return rows


def _row(label, H, d0, d0se, d0t, pb, pse, pt, ppct, nn):
    net = d0 + pb
    if np.isnan(pb) or np.isnan(d0):
        can = inc = mult = np.nan; verdict = "미계산"
    elif abs(pt) < 1.96:
        # 미래효과가 통계적 0 — 부호를 근거로 잠식/post-lift 어느 쪽도 주장하지 않는다
        can = 0.0; inc = net / d0; mult = net / d0
        verdict = "미래효과 통계적 0 — 잠식 관측되지 않음"
    elif pb < 0:
        can = (-pb) / d0; inc = 1 - can; mult = net / d0
        verdict = ("높은 증분성" if inc >= 0.9 else
                   "부분 잠식" if inc >= 0.5 else "높은 잠식")
    else:
        can = np.nan; inc = net / d0; mult = net / d0
        verdict = "post-lift (잠식 관측되지 않음)"
    return dict(metric=label, horizon=H, n_used=int(nn) if not np.isnan(nn) else -1,
                immediate=d0, immediate_se=d0se, immediate_t=d0t,
                post=pb, post_se=pse, post_t=pt, post_pct=ppct,
                net_cumulative=net, cannibalization=can, incrementality=inc,
                cumulative_multiplier=mult, verdict=verdict)


res = (block("quantity", "A|{H}|day0_q|M1", "A|{H}|q{H}|M1", "total quantity")
       + block("incidence", "A|{H}|day0_buy|M1", "A|{H}|any{H}|M1",
               "purchase incidence"))

# clean-window 강건성 곡선 — 분자·분모를 **같은 부분표본**에서 추정한 값으로 맞춘다.
# ⚠️ future exposure 는 post-treatment 변수다. 이 곡선은 인과 추정치가 아니라
#    "후속 판촉이 없었다면" 방향을 보기 위한 진단이다.
for kind, dj, pj, lab in [
        ("quantity", "A|{H}|day0_q|M1|clean", "A|{H}|q{H}|M1|clean",
         "total quantity [clean-window]"),
        ("incidence", "A|{H}|day0_buy|M1|clean", "A|{H}|any{H}|M1|clean",
         "purchase incidence [clean-window]")]:
    for H in [28, 56]:
        if not (F["job"] == pj.format(H=H)).any():
            continue
        res.append(_row(lab, H, get(dj.format(H=H)), get(dj.format(H=H), "se"),
                        get(dj.format(H=H), "t"), get(pj.format(H=H)),
                        get(pj.format(H=H), "se"), get(pj.format(H=H), "t"),
                        get(pj.format(H=H), "pct"), get(pj.format(H=H), "n")))

# 시간통제 M3(=⑧) 로 분자·분모를 **같은 스펙**으로 맞춘 강건성 곡선.
# 스펙이 다르면 잠식률이 의미를 잃으므로 ΔQ0 도 반드시 M3 로 재추정한 값을 쓴다.
if (F["job"].str.startswith("B|")).any():
    tc = pd.read_csv(os.path.join(OUT, "phase3b0_timecontrol.csv"))
    m3 = tc[(tc["spec"].str.startswith("⑧")) & (tc["outcome"] == "quantity")]
    if len(m3):
        r0 = float(m3.iloc[0]["beta"])
        res.append(dict(metric="total quantity [M3 ⑧]", horizon=0, n_used=int(m3.iloc[0]["n"]),
                        immediate=r0, immediate_se=float(m3.iloc[0]["se"]),
                        immediate_t=float(m3.iloc[0]["t"]), post=0.0, post_se=np.nan,
                        post_t=np.nan, post_pct=np.nan, net_cumulative=r0,
                        cannibalization=0.0, incrementality=1.0,
                        cumulative_multiplier=1.0, verdict="당일 기준효과 (전체표본, ⑧)"))
    for H in HOR:
        res.append(_row("total quantity [M3 ⑧]", H,
                        get(f"B|{H}|day0_q|M3"), get(f"B|{H}|day0_q|M3", "se"),
                        get(f"B|{H}|day0_q|M3", "t"),
                        get(f"B|{H}|q{H}|M3"), get(f"B|{H}|q{H}|M3", "se"),
                        get(f"B|{H}|q{H}|M3", "t"), get(f"B|{H}|q{H}|M3", "pct"),
                        get(f"B|{H}|q{H}|M3", "n")))
df = pd.DataFrame(res)
p = os.path.join(OUT, "phase3b1_incrementality_curve.csv")
df.to_csv(p, index=False, encoding="utf-8-sig")

for lab in df["metric"].unique():
    d = df[df["metric"] == lab]
    print(f"\n{BAR}\n{lab} — 증분성 곡선\n{BAR}")
    print(f"{'H':>4s} {'당일 ΔQ0':>12s} {'미래 ΔQ_H':>12s} {'(t)':>8s} "
          f"{'순누적':>12s} {'잠식률':>10s} {'순증분성':>10s} {'배수':>8s}  판정")
    for _, r in d.iterrows():
        can = "—" if np.isnan(r.cannibalization) else f"{100*r.cannibalization:9.1f}%"
        print(f"{int(r.horizon):>4d} {r.immediate:>+12.6f} {r.post:>+12.6f} "
              f"{r.post_t if not np.isnan(r.post_t) else 0:>8.2f} "
              f"{r.net_cumulative:>+12.6f} {can:>10s} "
              f"{100*r.incrementality:>9.1f}% {r.cumulative_multiplier:>8.3f}  {r.verdict}")
print(f"\n저장: {p}")
