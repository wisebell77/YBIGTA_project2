"""Phase 0 — CSV → parquet 캐싱 + DuckDB 뷰 정의"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT, ensure_dirs  # noqa: E402
ensure_dirs()
# ──────────────────────────────────────────────────────────────────────

import duckdb, os, time

ROOT = str(PROJECT_ROOT)
RAW = os.path.join(ROOT, "data", "raw")
CACHE = os.path.join(ROOT, "data", "interim")
DB = os.path.join(CACHE, "dunn.duckdb")


def p(path):
    return path.replace("\\", "/")


REQUIRED = ["transaction_data", "causal_data", "product"]
OPTIONAL = ["hh_demographic", "campaign_desc", "campaign_table",
            "coupon", "coupon_redempt"]
FILES = REQUIRED + OPTIONAL

# smoke: 소표본으로 코드 동작만 확인한다. 추정치를 full run 과 비교하지 말 것.
SMOKE = os.environ.get("DUNNHUMBY_SMOKE") == "1"
SMOKE_HOUSEHOLDS = 300
SMOKE_WEEK_MAX = 101


def _select(name: str, src: str) -> str:
    """smoke 모드에서만 표본을 축소한다."""
    base = f"SELECT * FROM read_csv_auto('{p(src)}', sample_size=-1)"
    if not SMOKE:
        return base
    if name == "transaction_data":
        return (f"{base} WHERE household_key IN ("
                f"SELECT DISTINCT household_key FROM read_csv_auto('{p(src)}', "
                f"sample_size=-1) ORDER BY household_key LIMIT {SMOKE_HOUSEHOLDS})"
                f" AND WEEK_NO <= {SMOKE_WEEK_MAX}")
    return base


def main():
    con = duckdb.connect(DB)
    con.execute("SET memory_limit='6GB'")
    con.execute("SET preserve_insertion_order=false")

    if SMOKE:
        print("=" * 70)
        print(f"SMOKE MODE — 가구 {SMOKE_HOUSEHOLDS}개 / WEEK <= {SMOKE_WEEK_MAX} 로 축소")
        print("이 실행의 추정치는 full run 결과와 비교할 수 없습니다.")
        print("=" * 70)

    present = []
    for name in FILES:
        src = os.path.join(RAW, name + ".csv")
        if not os.path.exists(src):
            if name in REQUIRED:
                raise SystemExit(
                    f"[Phase 0] 필수 파일 없음: {src}\n"
                    f"          data/raw/ 에 원본 CSV 를 두십시오 (docs/data_setup.md 참조)")
            print(f"{name:20s} (없음 — optional, 건너뜀)")
            continue
        dst = os.path.join(CACHE, name + ".parquet")
        t0 = time.time()
        con.execute(f"""
            COPY ({_select(name, src)})
            TO '{p(dst)}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        n = con.execute(f"SELECT COUNT(*) FROM '{p(dst)}'").fetchone()[0]
        print(f"{name:20s} {n:>12,}행  "
              f"{os.path.getsize(src)/1e6:7.1f}MB -> {os.path.getsize(dst)/1e6:6.1f}MB  "
              f"{time.time()-t0:5.1f}s")
        present.append(name)

    for name in present:
        con.execute(f"CREATE OR REPLACE VIEW {name} AS "
                    f"SELECT * FROM '{p(os.path.join(CACHE, name + '.parquet'))}'")

    print("\n-- 스키마 --")
    for name in ["transaction_data", "causal_data", "product"]:
        cols = con.execute(f"DESCRIBE {name}").fetchall()
        print(f"{name}: " + ", ".join(f"{c[0]}({c[1]})" for c in cols))

    print("\n-- 속도 확인 --")
    t0 = time.time()
    r = con.execute("SELECT COUNT(*), COUNT(DISTINCT STORE_ID), "
                    "MIN(WEEK_NO), MAX(WEEK_NO) FROM causal_data").fetchone()
    print(f"causal_data 전수 집계: {r[0]:,}행 / 점포 {r[1]} / WEEK {r[2]}~{r[3]}"
          f"  ({time.time()-t0:.2f}s)")

    con.close()


if __name__ == "__main__":
    main()
