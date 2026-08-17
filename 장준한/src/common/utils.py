"""공용 유틸 — 로깅, DuckDB 연결, 체크포인트."""
from __future__ import annotations
import sys, time
from pathlib import Path

from .paths import CHECKPOINT_DIR

try:                                    # Windows 콘솔 cp949 대응
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                       # noqa: BLE001
    pass


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def duckdb_connect(memory_limit: str = "6GB", database: str | None = None):
    """메모리 상한이 적용된 DuckDB 연결."""
    import duckdb
    con = duckdb.connect(database) if database else duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute("SET preserve_insertion_order=false")
    return con


def checkpoint_path(phase: str) -> Path:
    return CHECKPOINT_DIR / f"{phase}.done"


def mark_done(phase: str) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path(phase).write_text(time.strftime("%Y-%m-%d %H:%M:%S"),
                                      encoding="utf-8")


def outputs_exist(paths) -> bool:
    """필수 산출물이 실제로 존재하고 비어있지 않은지."""
    for p in paths:
        p = Path(p)
        if not p.exists() or p.stat().st_size == 0:
            return False
    return True
