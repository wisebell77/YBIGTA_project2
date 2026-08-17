"""
Step 4 Simplified: Realized Discount Depth Bands
Simpler implementation focused on reliability
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────


import duckdb
import pandas as pd
from pathlib import Path

print("\n" + "="*80, flush=True)
print("STEP 4 SIMPLIFIED: Realized Discount Depth Bands Analysis", flush=True)
print("="*80, flush=True)

DB_PATH = PROJECT_ROOT / "data" / "interim" / "dunn.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("\n[1/4] Connecting to database...", flush=True)
conn = duckdb.connect(str(DB_PATH), read_only=True)
conn.execute("SET memory_limit='4GB'")
conn.execute("SET temp_directory='" + str(Path.home() / "AppData" / "Local" / "Temp" / "duckdb_temp") + "'")

print("[2/4] Building transaction table with bands...", flush=True)
# Get causal data stores
causal_stores_sql = "SELECT DISTINCT STORE_ID FROM causal_data"
store_ids = tuple(s[0] for s in conn.execute(causal_stores_sql).fetchall())
print(f"     {len(store_ids)} stores", flush=True)

# Build full tx table with bands
tx_bands_sql = f"""
CREATE TEMP TABLE tx_bands AS
SELECT
    t.household_key,
    t.STORE_ID,
    t.DAY,
    p.COMMODITY_DESC,
    t.SALES_VALUE,
    t.QUANTITY,
    CASE
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0
        THEN -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC)
        ELSE NULL
    END as rate,
    CASE
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0
        THEN (t.SALES_VALUE - t.RETAIL_DISC - t.COUPON_DISC - t.COUPON_MATCH_DISC)
        ELSE NULL
    END as reg_value,
    CASE
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0
        THEN -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC)
        ELSE NULL
    END as rate,
    CASE
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) < 0.20
        THEN '1_lt20pct'
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) >= 0.20 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) < 0.30
        THEN '2_20to30pct'
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) >= 0.30 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) < 0.40
        THEN '3_30to40pct'
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0 AND
             -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC) >= 0.40
        THEN '4_40plus_pct'
        ELSE NULL
    END as band
FROM transaction_data t
JOIN product p ON t.PRODUCT_ID = p.PRODUCT_ID
WHERE
    t.WEEK_NO BETWEEN 9 AND 101
    AND t.STORE_ID IN ({",".join(str(s) for s in store_ids)})
    AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
    AND t.SALES_VALUE > 0
    AND (t.SALES_VALUE - t.RETAIL_DISC) > 0
"""
conn.execute(tx_bands_sql)
max_day = conn.execute("SELECT MAX(DAY) FROM tx_bands").fetchall()[0][0]
print(f"     max_day={max_day}", flush=True)

print("[3/4] Computing repeats by band (this is slow)...", flush=True)
# For each band × hh × cat × occasion, check for 56-day repeat
band_analysis_sql = f"""
CREATE TEMP TABLE band_occasions AS
SELECT
    tb.band,
    COUNT(*) as n_occasions,
    ROUND(SUM(tb.QUANTITY), 2) as total_quantity,
    ROUND(AVG(tb.QUANTITY), 4) as avg_quantity,
    ROUND(SUM(tb.SALES_VALUE), 2) as total_sales,
    ROUND(AVG(tb.SALES_VALUE), 4) as avg_sales,
    ROUND(SUM(tb.reg_value), 2) as total_reg_value,
    ROUND(AVG(tb.reg_value), 4) as avg_reg_value,
    SUM(CASE
        WHEN EXISTS (
            SELECT 1 FROM tx_bands t2
            WHERE t2.household_key = tb.household_key
            AND t2.COMMODITY_DESC = tb.COMMODITY_DESC
            AND t2.DAY > tb.DAY
            AND t2.DAY <= tb.DAY + 56
        ) THEN 1
        ELSE 0
    END) as repeat_56_count,
    SUM(CASE
        WHEN EXISTS (
            SELECT 1 FROM tx_bands t2
            WHERE t2.household_key = tb.household_key
            AND t2.COMMODITY_DESC = tb.COMMODITY_DESC
            AND t2.DAY > tb.DAY
            AND t2.DAY <= tb.DAY + 56
            AND t2.rate <= 0.02
        ) THEN 1
        ELSE 0
    END) as regular_price_repeat_56_count
FROM tx_bands tb
WHERE tb.band IS NOT NULL
GROUP BY tb.band
ORDER BY tb.band
"""
conn.execute(band_analysis_sql)

print("[4/4] Calculating rates...", flush=True)
result_sql = """
SELECT
    band,
    n_occasions,
    total_quantity,
    avg_quantity,
    total_sales,
    avg_sales,
    total_reg_value,
    avg_reg_value,
    repeat_56_count,
    regular_price_repeat_56_count,
    ROUND(100.0 * repeat_56_count / NULLIF(n_occasions, 0), 2) as repeat_rate_56_pct,
    ROUND(100.0 * regular_price_repeat_56_count / NULLIF(repeat_56_count, 0), 2) as conversion_to_regular_pct
FROM band_occasions
"""

results = conn.execute(result_sql).df()

print("\n" + "="*140, flush=True)
print("STEP 4 RESULTS: Realized Discount Depth Bands", flush=True)
print("="*140, flush=True)
print(results.to_string(index=False), flush=True)

output_file = OUTPUT_DIR / "phase5c_step4_discount_bands_summary.csv"
results.to_csv(output_file, index=False)
print(f"\n[SAVED] {output_file}", flush=True)

conn.close()
print("\nDone.", flush=True)
