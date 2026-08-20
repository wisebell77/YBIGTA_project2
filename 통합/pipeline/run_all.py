"""통합 파이프라인 실행기 — data/ 원본 CSV만 있으면 전체 분석을 표준 정의로 재현한다.

  python 통합/pipeline/run_all.py            # s0 → s1 → s1b → s2 → s3 → s4 → s5
  python 통합/pipeline/run_all.py --from s2  # 해당 스테이지부터

s1b(시간통제 payback)는 다요인 FE 사영이라 가장 오래 걸린다(수십 분 수준).
급하면 --skip s1b 로 건너뛰고 나머지를 먼저 볼 수 있다.
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = ["s0_marts.py", "s1_incrementality.py", "s1b_payback_m3.py",
          "s2_allocation.py", "s3_crm.py", "s3c_crm_segments.py", "s4_integrate.py",
          "s5_dashboard_exports.py"]

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="from_", default=None, metavar="sN")
ap.add_argument("--skip", nargs="*", default=[], metavar="sN")
a = ap.parse_args()

todo = STAGES
if a.from_:
    idx = next(i for i, s in enumerate(STAGES) if s.startswith(a.from_))
    todo = STAGES[idx:]
todo = [s for s in todo if not any(s.startswith(k) for k in a.skip)]

env = dict(os.environ, PYTHONIOENCODING="utf-8")
for s in todo:
    t0 = time.time()
    print(f"\n{'='*70}\n▶ {s}\n{'='*70}", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, s)], env=env)
    if r.returncode != 0:
        sys.exit(f"실패: {s}")
    print(f"◀ {s} 완료 ({time.time()-t0:.0f}s)")
print("\n전체 파이프라인 완료 — 산출물: 통합/outputs/")
