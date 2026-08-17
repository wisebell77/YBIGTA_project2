"""경로 규약 — PROJECT_ROOT 가 release 내부인지, 금지 절대경로가 없는지.

주의: 이 파일 자신은 금지 패턴 문자열을 담고 있으므로 스캔 대상에서 제외한다.
스캔 범위는 실제 파이프라인 코드(src/, config/, run_pipeline.py)로 한정한다.
"""
import re

from common.paths import PROJECT_ROOT, RAW_DIR, TABLES_DIR

# 드라이브 절대경로 / 개인 계정 / 상위 원 프로젝트 참조
_PAT = (
    r"[A-Za-z]:[\\/](?:Users|Desktop)"
    r"|" + "821" + "09"
    r"|OneDrive"
)
FORBIDDEN = re.compile(_PAT)

SCAN_EXT = {".py", ".yaml", ".yml", ".toml", ".cfg", ".txt"}
# 상위 디렉터리 탈출 참조 패턴 (문자열을 조각내어 자기검출 회피)
ESCAPE_TOKENS = ["parents" + "[3]", "PROJECT_ROOT." + "parent"]


def _pipeline_files():
    for base in (PROJECT_ROOT / "src", PROJECT_ROOT / "config"):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in SCAN_EXT and "__pycache__" not in p.parts:
                yield p
    for extra in ("run_pipeline.py", "requirements.txt"):
        f = PROJECT_ROOT / extra
        if f.exists():
            yield f


def test_project_root_is_this_repository():
    assert (PROJECT_ROOT / "run_pipeline.py").exists()
    assert (PROJECT_ROOT / "src" / "common" / "paths.py").exists()


def test_derived_paths_inside_root():
    for p in (RAW_DIR, TABLES_DIR):
        assert PROJECT_ROOT in p.parents


def test_no_forbidden_absolute_paths():
    bad = []
    for f in _pipeline_files():
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                bad.append(f"{f.relative_to(PROJECT_ROOT)}:{i}")
    assert not bad, "금지된 절대경로/개인경로 발견:\n" + "\n".join(bad)


def test_pipeline_does_not_escape_repository():
    """상위 디렉터리(원 프로젝트)의 산출물을 참조하지 않아야 한다."""
    offenders = []
    for f in _pipeline_files():
        if f.suffix != ".py":
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if any(tok in text for tok in ESCAPE_TOKENS):
            offenders.append(str(f.relative_to(PROJECT_ROOT)))
    assert not offenders, f"repository 밖을 참조: {offenders}"
