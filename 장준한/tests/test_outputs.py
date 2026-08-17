"""산출물 스키마 — 아직 생성되지 않았으면 skip."""
import pytest

from common.paths import TABLES_DIR, REFERENCE_DIR

pd = pytest.importorskip("pandas")

EXPECTED = {
    "phase3b0_main_m1.csv": {"outcome", "spec", "vcov", "beta", "se", "t", "n"},
    "phase3b1_incrementality_curve.csv": {"metric", "horizon", "immediate", "post",
                                          "net_cumulative", "incrementality"},
    "phase5a_category_portfolio.csv": {"category", "visit_beta", "visit_q",
                                       "spend_beta", "spend_q", "classification_fdr"},
    "phase5b_rfm_segments.csv": {"segmentation", "level", "outcome",
                                 "diff_fe", "p", "q"},
    "FINAL_key_results.csv": {"no", "metric", "value", "unit", "part"},
}


@pytest.mark.parametrize("fname,cols", sorted(EXPECTED.items()))
def test_output_schema(fname, cols):
    p = TABLES_DIR / fname
    if not p.exists():
        pytest.skip(f"{fname} 미생성 — run_pipeline.py --all 실행 후 검사됩니다")
    have = set(pd.read_csv(p, nrows=5).columns)
    missing = cols - have
    assert not missing, f"{fname} column 누락: {sorted(missing)}"


def test_reference_results_present_and_readable():
    """reference_results 는 파이프라인 입력이 아니라 비교용이다."""
    p = REFERENCE_DIR / "FINAL_key_results.csv"
    assert p.exists(), "reference_results/FINAL_key_results.csv 가 있어야 합니다"
    df = pd.read_csv(p)
    assert len(df) > 0
    assert {"metric", "value", "part"} <= set(df.columns)


def test_reference_not_used_as_pipeline_input():
    """src/ 어디에서도 reference_results 를 읽지 않아야 한다."""
    from common.paths import PROJECT_ROOT
    offenders = []
    for f in (PROJECT_ROOT / "src").rglob("*.py"):
        # common/paths.py 는 REFERENCE_DIR 상수를 정의만 한다 (읽지 않음)
        if f.name == "paths.py":
            continue
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if "reference_results" in txt or "REFERENCE_DIR" in txt:
            offenders.append(str(f.relative_to(PROJECT_ROOT)))
    assert not offenders, f"reference_results 를 입력으로 읽는 코드: {offenders}"
