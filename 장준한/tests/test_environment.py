"""환경 점검 — 핵심 패키지 import 가능 여부."""
import importlib
import sys

import pytest

CORE = ["duckdb", "numpy", "pandas", "pyarrow", "scipy"]


def test_python_version():
    assert sys.version_info >= (3, 9), "Python 3.9 이상이 필요합니다"


@pytest.mark.parametrize("mod", CORE)
def test_core_imports(mod):
    importlib.import_module(mod)


def test_project_modules_import():
    from common import paths, config, utils  # noqa: F401
    from common.fe_estimator import feols1  # noqa: F401
