#!/usr/bin/env python
"""Dunnhumby Promotion Incrementality — single pipeline entrypoint.

    python run_pipeline.py --help
    python run_pipeline.py --check              환경/데이터 사전점검 (분석 미실행)
    python run_pipeline.py --all                전체 파이프라인
    python run_pipeline.py --phase phase3b0     단일 phase
    python run_pipeline.py --from phase3b0      해당 phase부터 끝까지
    python run_pipeline.py --all --force        체크포인트 무시하고 재실행
    python run_pipeline.py --smoke              소표본 빠른 점검 (추정치 신뢰 금지)

⚠️ PART A(전단지 노출 ITT, 주 인과추정)와 PART B(실현 딥할인, observational)는
   성격이 다르다. 두 파트의 수치를 직접 비교하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from common.paths import (  # noqa: E402
    PROJECT_ROOT, RAW_DIR, INTERIM_DIR, MARTS_DIR, TABLES_DIR, TABLEAU_DIR,
    CHECKPOINT_DIR,
)
from common.paths import ensure_dirs as _ensure  # noqa: E402
from common.config import load_config  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BAR = "=" * 78

# ── raw 데이터 요구사항 (실제 코드가 참조하는 파일만) ────────────────────
REQUIRED_RAW = {
    "transaction_data.csv": "거래 라인 — Phase 0 이후 전 Phase",
    "product.csv":          "상품 마스터(COMMODITY_DESC) — Phase 0 이후 전 Phase",
    "causal_data.csv":      "프로모션 노출(mailer/display) — Phase 2 이후 PART A",
}
OPTIONAL_RAW = {
    "hh_demographic.csv":   "가구 인구통계 — Phase 0 캐시에만 사용",
    "campaign_desc.csv":    "캠페인 설명 — Phase 0 캐시에만 사용",
    "campaign_table.csv":   "캠페인-가구 매핑 — Phase 0 캐시에만 사용",
    "coupon.csv":           "쿠폰 — Phase 0 캐시에만 사용",
    "coupon_redempt.csv":   "쿠폰 사용 — Phase 0 캐시에만 사용",
}

# ── phase 정의: (키, 라벨, PART, [스크립트], [필수 산출물]) ───────────────
def T(*names): return [TABLES_DIR / n for n in names]
def M(*names): return [MARTS_DIR / n for n in names]

PHASES = [
    ("phase0",   "Phase 0 — raw → parquet 캐시", "-",
     ["src/phase0_prepare/prepare_data.py"],
     [INTERIM_DIR / "transaction_data.parquet", INTERIM_DIR / "product.parquet"]),
    ("phase1",   "Phase 1 — 원자료 사실 재현 검증", "-",
     ["src/phase1_validation/validate_data.py"], []),
    ("phase2",   "Phase 2 — 전단지 처치 정의·대조군 확인", "A",
     ["src/phase2_design/build_mailer_treatment.py"], []),
    ("phase3a",  "Phase 3A — occasion 조건부 효과", "A",
     ["src/phase3a_conditional/build_occasion_mart.py",
      "src/phase3a_conditional/estimate_conditional_effects.py",
      "src/phase3a_conditional/deep_discount_reference.py"],
     M("occasion.parquet") + T("phase3a_clusterse.csv", "phase3a_pdf_deepdisc.csv")),
    ("phase3b0", "Phase 3B-0 — 기회패널·총수요 (PART A 주 결과)", "A",
     ["src/phase3b0_total_demand/build_opportunity_panel.py",
      "src/phase3b0_total_demand/validate_panel.py",
      "src/phase3b0_total_demand/estimate_total_demand.py",
      "src/phase3b0_total_demand/time_control_robustness.py"],
     M("opportunity.parquet") + T("phase3b0_main_m1.csv", "phase3b0_timecontrol.csv")),
    ("phase3b1", "Phase 3B-1 — 56일 future payback", "A",
     ["src/phase3b1_incrementality/selftest_future_windows.py",
      "src/phase3b1_incrementality/build_future_windows.py",
      "src/phase3b1_incrementality/estimate_payback.py",
      "src/phase3b1_incrementality/build_incrementality_curve.py"],
     T("phase3b1_future.csv", "phase3b1_incrementality_curve.csv")),
    ("phase4a",  "Phase 4A — robustness 통합 + 95% CI", "A",
     ["src/phase4a_robustness/summarize_robustness.py"],
     T("FINAL_phase4a_robustness.csv", "FINAL_phase4a_ci.csv")),
    ("phase4b",  "Phase 4B — 딥할인 후 매장활동 (PART B)", "B",
     ["src/phase4b_relationship/estimate_future_store_activity.py"],
     T("phase4b_future28_results.csv")),
    ("phase5a",  "Phase 5A — 카테고리 포트폴리오 + FDR (PART B)", "B",
     ["src/phase5a_category/category_portfolio.py",
      "src/phase5a_category/fdr_category.py"],
     T("phase5a_category_matrix.csv", "phase5a_category_portfolio.csv")),
    ("phase5b",  "Phase 5B — period-split RFM + FE + FDR (PART B)", "B",
     ["src/phase5b_crm/build_rfm_features.py",
      "src/phase5b_crm/estimate_segment_associations.py",
      "src/phase5b_crm/fdr_segments.py"],
     T("phase5b_segment_results.csv", "phase5b_rfm_segments.csv")),
    ("phase5c",  "Phase 5C — 전환·할인깊이·마진 시나리오 (PART B)", "B",
     ["src/phase5c_conversion/margin_scenario.py",
      "src/phase5c_conversion/trial_conversion.py",
      "src/phase5c_conversion/discount_depth.py"],
     T("phase5c_margin_sensitivity.csv", "phase5c_step3_trial_conversion.csv",
       "phase5c_step4_discount_bands_summary.csv")),
    ("phase8",   "Phase 8 — 최종 표 · Tableau 산출", "-",
     ["src/phase8_finalize/build_final_tables.py",
      "src/phase8_finalize/build_tableau_outputs.py"],
     T("FINAL_key_results.csv")),
]
KEYS = [p[0] for p in PHASES]


# ── --check ──────────────────────────────────────────────────────────────
def cmd_check() -> int:
    print(BAR); print("환경 사전점검 (--check) — 분석은 실행하지 않습니다"); print(BAR)
    ok = True

    print(f"\n[1] Python  {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        print("    ✗ Python 3.9 이상이 필요합니다"); ok = False
    else:
        print("    ✓")

    print("\n[2] 필수 패키지")
    need = ["duckdb", "numpy", "pandas", "pyarrow", "scipy"]
    optional = ["yaml", "pyfixest"]
    for m in need:
        try:
            mod = __import__(m)
            print(f"    ✓ {m:10s} {getattr(mod, '__version__', '')}")
        except ImportError:
            print(f"    ✗ {m:10s} 없음 — pip install -r requirements.txt"); ok = False
    for m in optional:
        try:
            mod = __import__(m)
            print(f"    ✓ {m:10s} {getattr(mod, '__version__', '')} (optional)")
        except ImportError:
            print(f"    ! {m:10s} 없음 (optional — 일부 Phase 에 필요)")

    print(f"\n[3] Project root\n    {PROJECT_ROOT}")
    if not (PROJECT_ROOT / "run_pipeline.py").exists():
        print("    ✗ repository root 가 아닙니다"); ok = False
    else:
        print("    ✓")

    cfg = load_config()
    print(f"\n[4] Config\n    deep_discount_threshold={cfg['deep_discount_threshold']} "
          f"/ pre_period_days={cfg['pre_period_days']} "
          f"/ future_windows={cfg['future_windows']}\n"
          f"    causal_week={cfg['causal_week_min']}–{cfg['causal_week_max']} "
          f"/ duckdb_memory_limit={cfg['duckdb_memory_limit']}")

    print(f"\n[5] Raw data  ({RAW_DIR})")
    missing = [f for f in REQUIRED_RAW if not (RAW_DIR / f).exists()]
    for f, why in REQUIRED_RAW.items():
        p = RAW_DIR / f
        if p.exists():
            print(f"    ✓ {f:24s} {p.stat().st_size/1e6:8.1f} MB  — {why}")
        else:
            print(f"    ✗ {f:24s} 없음                — {why}")
    for f, why in OPTIONAL_RAW.items():
        p = RAW_DIR / f
        print(f"    {'✓' if p.exists() else '!'} {f:24s} "
              f"{'존재' if p.exists() else '없음 (optional)':>12s}  — {why}")
    if missing:
        print("\n    Missing required data files:")
        for f in missing:
            print(f"      - {RAW_DIR / f}")
        print("    → dunnhumby 원본 CSV 를 data/raw/ 에 두십시오 (docs/data_setup.md 참조)")
        ok = False

    print("\n[6] 쓰기 권한")
    try:
        _ensure()
        t = TABLES_DIR / ".write_test"
        t.write_text("ok", encoding="utf-8"); t.unlink()
        print("    ✓ outputs/ · data/interim · data/marts 생성/쓰기 가능")
    except Exception as e:  # noqa: BLE001
        print(f"    ✗ 쓰기 실패: {e}"); ok = False

    print("\n[7] 체크포인트")
    done = sorted(p.stem for p in CHECKPOINT_DIR.glob("*.done")) if CHECKPOINT_DIR.exists() else []
    print(f"    완료된 phase: {', '.join(done) if done else '(없음)'}")

    print(f"\n{BAR}\n{'✓ 실행 준비 완료' if ok else '✗ 위 문제를 해결한 뒤 다시 실행하십시오'}\n{BAR}")
    return 0 if ok else 1


# ── 실행 ────────────────────────────────────────────────────────────────
def _smoke_root() -> Path:
    """smoke 전용 샌드박스 root. data/raw 만 실제 위치를 재사용한다."""
    sb = PROJECT_ROOT / ".smoke_run"
    for d in ("data", "data/interim", "data/marts", "outputs/tables",
              "outputs/figures", "outputs/tableau", "outputs/checkpoints"):
        (sb / d).mkdir(parents=True, exist_ok=True)
    link = sb / "data" / "raw"
    if not link.exists():
        try:                                   # Windows junction / POSIX symlink
            link.symlink_to(RAW_DIR, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name == "nt":
                subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(RAW_DIR)],
                               capture_output=True)
    return sb


def phase_done(key: str, outs) -> bool:
    """체크포인트 파일 + 실제 산출물 존재를 함께 확인한다."""
    cp = CHECKPOINT_DIR / f"{key}.done"
    if not cp.exists():
        return False
    for o in outs:
        if not Path(o).exists() or Path(o).stat().st_size == 0:
            print(f"    ! 체크포인트는 있으나 산출물 누락: {Path(o).name} → 재실행")
            return False
    return True


def run_phase(key, label, part, scripts, outs, force, smoke) -> bool:
    print(f"\n{BAR}\n{label}" + (f"   [PART {part}]" if part != "-" else "") + f"\n{BAR}")
    if not force and phase_done(key, outs):
        print("    → 이미 완료 (--force 로 재실행)")
        return True
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=str(PROJECT_ROOT / "src"))
    if smoke:
        # 샌드박스 root 로 격리 — 실제 interim/marts/outputs 를 덮어쓰지 않는다.
        env["DUNNHUMBY_SMOKE"] = "1"
        env["DUNNHUMBY_ROOT"] = str(_smoke_root())
    for s in scripts:
        p = PROJECT_ROOT / s
        if not p.exists():
            print(f"    ✗ 스크립트 없음: {s}"); return False
        print(f"\n  ▶ {s}")
        t0 = time.time()
        r = subprocess.run([sys.executable, "-u", str(p)], cwd=str(PROJECT_ROOT), env=env)
        if r.returncode != 0:
            print(f"    ✗ 실패 (exit {r.returncode}) — {s}")
            return False
        print(f"    ✓ {time.time()-t0:.0f}s")
    if smoke:
        print("    (smoke — 체크포인트를 기록하지 않습니다)")
        return True
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    (CHECKPOINT_DIR / f"{key}.done").write_text(
        time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Dunnhumby promotion incrementality pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="phases: " + ", ".join(KEYS))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="환경/데이터 점검만")
    g.add_argument("--all", action="store_true", help="전체 파이프라인 실행")
    g.add_argument("--phase", metavar="KEY", help="단일 phase 실행")
    g.add_argument("--from", dest="from_", metavar="KEY", help="해당 phase부터 끝까지")
    ap.add_argument("--force", action="store_true", help="체크포인트 무시하고 재실행")
    ap.add_argument("--smoke", action="store_true",
                    help="소표본 점검 모드 (추정치를 원 결과와 비교하지 말 것)")
    a = ap.parse_args()

    if a.check:
        return cmd_check()
    if not (a.all or a.phase or a.from_ or a.smoke):
        ap.print_help(); return 0

    sel = PHASES
    if a.phase:
        if a.phase not in KEYS:
            print(f"알 수 없는 phase: {a.phase}\n사용 가능: {', '.join(KEYS)}"); return 2
        sel = [p for p in PHASES if p[0] == a.phase]
    elif a.from_:
        if a.from_ not in KEYS:
            print(f"알 수 없는 phase: {a.from_}\n사용 가능: {', '.join(KEYS)}"); return 2
        sel = PHASES[KEYS.index(a.from_):]

    if a.smoke:
        print(f"{BAR}\n⚠️ SMOKE MODE — 소표본으로 코드 동작만 확인합니다.\n"
              f"   산출 추정치를 원 full-run 결과와 비교하지 마십시오.\n"
              f"   실제 outputs/ · data/interim · data/marts 는 건드리지 않습니다\n"
              f"   (샌드박스 .smoke_run/ 에 격리 실행).\n{BAR}")

    rc = cmd_check()
    if rc != 0:
        print("\n--check 실패로 중단합니다.")
        return rc

    t0 = time.time()
    for key, label, part, scripts, outs in sel:
        if not run_phase(key, label, part, scripts, outs, a.force, a.smoke):
            print(f"\n{BAR}\n✗ {key} 에서 중단되었습니다.\n{BAR}")
            return 1
    print(f"\n{BAR}\n✓ 완료 — {len(sel)} phase / 총 {time.time()-t0:.0f}s")
    print(f"  결과: {TABLES_DIR}\n  Tableau: {TABLEAU_DIR}\n{BAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
