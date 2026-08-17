"""Repository-root 기준 경로 해석 — 절대경로 하드코딩 금지.

PROJECT_ROOT 는 이 파일 위치(src/common/paths.py)에서 두 단계 위로 계산한다.
환경변수 DUNNHUMBY_ROOT 로 override 할 수 있으나, 기본값은 repository root 다.
"""
from __future__ import annotations
import os
from pathlib import Path

_HERE = Path(__file__).resolve()
_DEFAULT_ROOT = _HERE.parents[2]          # src/common/paths.py -> src -> <root>

PROJECT_ROOT: Path = Path(os.environ.get("DUNNHUMBY_ROOT", _DEFAULT_ROOT)).resolve()

DATA_DIR      = PROJECT_ROOT / "data"
RAW_DIR       = DATA_DIR / "raw"
INTERIM_DIR   = DATA_DIR / "interim"
MARTS_DIR     = DATA_DIR / "marts"
OUTPUTS_DIR   = PROJECT_ROOT / "outputs"
TABLES_DIR    = OUTPUTS_DIR / "tables"
FIGURES_DIR   = OUTPUTS_DIR / "figures"
TABLEAU_DIR   = OUTPUTS_DIR / "tableau"
CHECKPOINT_DIR = OUTPUTS_DIR / "checkpoints"
REPORTS_DIR   = PROJECT_ROOT / "reports"
CONFIG_DIR    = PROJECT_ROOT / "config"
REFERENCE_DIR = PROJECT_ROOT / "reference_results"

DUCKDB_PATH = INTERIM_DIR / "dunn.duckdb"

# RAW_DIR 도 포함한다 — 신규 clone 에서 data/raw/ 가 없으면 사용자가
# 어디에 CSV 를 둬야 하는지 알기 어렵기 때문이다(빈 디렉터리는 git 이 추적하지 않는다).
_WRITABLE = [RAW_DIR, INTERIM_DIR, MARTS_DIR, TABLES_DIR, FIGURES_DIR,
             TABLEAU_DIR, CHECKPOINT_DIR]


def ensure_dirs() -> None:
    """실행 중 생성되는 디렉터리를 만든다."""
    for d in _WRITABLE:
        d.mkdir(parents=True, exist_ok=True)


def duckdb_uri(p: Path) -> str:
    """DuckDB SQL 리터럴용 POSIX 경로 문자열."""
    return str(p).replace("\\", "/")


__all__ = ["PROJECT_ROOT", "DATA_DIR", "RAW_DIR", "INTERIM_DIR", "MARTS_DIR",
           "OUTPUTS_DIR", "TABLES_DIR", "FIGURES_DIR", "TABLEAU_DIR",
           "CHECKPOINT_DIR", "REPORTS_DIR", "CONFIG_DIR", "REFERENCE_DIR",
           "DUCKDB_PATH", "ensure_dirs", "duckdb_uri"]
