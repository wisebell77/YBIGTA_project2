"""raw 데이터 스키마 — 데이터가 없으면 skip."""
import csv
from pathlib import Path

import pytest

from common.paths import RAW_DIR

REQUIRED = {
    "transaction_data.csv": {
        "household_key", "DAY", "WEEK_NO", "STORE_ID", "PRODUCT_ID",
        "QUANTITY", "SALES_VALUE", "RETAIL_DISC", "COUPON_DISC",
        "COUPON_MATCH_DISC",
    },
    "product.csv": {"PRODUCT_ID", "COMMODITY_DESC"},
    "causal_data.csv": {"PRODUCT_ID", "STORE_ID", "WEEK_NO", "mailer", "display"},
}


def _header(p: Path):
    with p.open(newline="", encoding="utf-8-sig") as fh:
        return set(next(csv.reader(fh)))


@pytest.mark.parametrize("fname,cols", sorted(REQUIRED.items()))
def test_required_columns(fname, cols):
    p = RAW_DIR / fname
    if not p.exists():
        pytest.skip(f"{fname} 없음 — data/raw/ 에 원본 CSV 를 두면 검사합니다")
    have = _header(p)
    missing = cols - have
    assert not missing, f"{fname} 필수 column 누락: {sorted(missing)}"


def test_causal_data_is_event_log():
    """causal_data 는 미노출 행을 담지 않는 이벤트 로그여야 한다."""
    p = RAW_DIR / "causal_data.csv"
    if not p.exists():
        pytest.skip("causal_data.csv 없음")
    import duckdb
    q = str(p).replace("\\", "/")
    n = duckdb.sql(
        f"SELECT count(*) FROM read_csv_auto('{q}') "
        "WHERE mailer='0' AND display='0'").fetchone()[0]
    assert n == 0, ("causal_data 에 display=0 & mailer=0 행이 존재합니다. "
                    "이 데이터 규약이 깨지면 '조인 실패=미노출' 가정이 성립하지 않습니다")
