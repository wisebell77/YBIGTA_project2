"""팀 공통 표준 — 모든 스테이지가 이 모듈만 참조한다 (single source of truth).

처치정의_표준.md 의 합의 사항을 코드로 고정한 것.
개인 폴더의 원 분석은 아카이브로 보존되며, 이 파이프라인은 표준 정의로
전체 분석을 재현한다.
"""
import os
import duckdb

# ── 처치 정의 ──────────────────────────────────────────────────────
MAILER_AD = ("A", "C", "D", "F", "H", "L")   # 전단지 처치 = 광고 코드만
MAILER_COUPON = ("J", "P")                    # 전단지 내 쿠폰 — 처치 아님
MAILER_FREE = ("X", "Z")                      # 무료 증정 — 처치 아님 (동어반복 방지)

# ── 분석 상수 ──────────────────────────────────────────────────────
WEEK_MIN, WEEK_MAX = 9, 101   # causal 커버리지
DEEP_CUT = 0.30               # 고할인: 구매기회 할인율 >= 30%
REG_CUT = 0.02                # 정가: <= 2%
WINSOR = 20                   # 수량 winsorize 상한
POST_MAX_DAY = 711 - 56       # 56일 사후창 확보를 위한 기준일 상한
JUNK_CATS = ("COUPON", "MISC ITEMS", "NO COMMODITY DESCRIPTION", "COUPON/MISC ITEMS")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "outputs"))
DB = os.path.join(HERE, "marts.duckdb")


def find_data(up=6):
    d = HERE
    for _ in range(up):
        c = os.path.join(d, "data")
        if os.path.isfile(os.path.join(c, "transaction_data.csv")):
            return c.replace("\\", "/")
        d = os.path.dirname(d)
    raise SystemExit("data/ 없음 — dunnhumby CSV 8종을 저장소 최상위 data/ 에 둘 것")


def connect(read_only=False):
    con = duckdb.connect(DB, read_only=read_only)
    con.execute("PRAGMA threads=8")
    con.execute("SET memory_limit='6GB'")
    return con


def junk_sql(col="commodity_desc"):
    inner = ",".join(f"'{c}'" for c in JUNK_CATS)
    return f"{col} NOT IN ({inner})"


def codes_sql(codes):
    return "(" + ",".join(f"'{c}'" for c in codes) + ")"
