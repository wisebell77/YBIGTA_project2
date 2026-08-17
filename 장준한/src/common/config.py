"""config/config.yaml (없으면 config.example.yaml) 로더.

설정값은 원 분석에서 실제 사용한 값과 동일하다. 임의로 바꾸지 않는다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

from .paths import CONFIG_DIR, PROJECT_ROOT

DEFAULTS: Dict[str, Any] = {
    "data_dir": "data/raw",
    "interim_dir": "data/interim",
    "marts_dir": "data/marts",
    "output_dir": "outputs",
    "duckdb_memory_limit": "6GB",
    "deep_discount_threshold": 0.30,
    "full_price_threshold": 0.02,
    "pre_period_days": 84,
    "future_windows": [7, 14, 28, 56],
    "random_seed": 42,
    "causal_week_min": 9,
    "causal_week_max": 101,
    "excluded_commodity": "COUPON/MISC ITEMS",
}


def load_config(path: Path | None = None) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path is None:
        for cand in (CONFIG_DIR / "config.yaml", CONFIG_DIR / "config.example.yaml"):
            if cand.exists():
                path = cand
                break
    if path is None or not Path(path).exists():
        return cfg
    try:
        import yaml
    except ImportError:
        return cfg
    loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg.update({k: v for k, v in loaded.items() if v is not None})
    return cfg


def resolve(cfg_value: str) -> Path:
    """config 의 상대경로를 PROJECT_ROOT 기준 절대경로로."""
    p = Path(cfg_value)
    return p if p.is_absolute() else (PROJECT_ROOT / p)
