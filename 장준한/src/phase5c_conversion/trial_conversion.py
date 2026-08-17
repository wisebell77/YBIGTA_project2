"""
Step 3 Simplified: Trial to Regular-Price Conversion
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
import sys

print("\n" + "="*80, flush=True)
print("STEP 3 SIMPLIFIED: Trial to Repeat to Regular-Price Conversion", flush=True)
print("="*80, flush=True)

DB_PATH = PROJECT_ROOT / "data" / "interim" / "dunn.duckdb"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Connect to DuckDB with memory limit
print("\n[1/5] Connecting to database...", flush=True)
conn = duckdb.connect(str(DB_PATH), read_only=True)
conn.execute("SET memory_limit='4GB'")
conn.execute("SET temp_directory='" + str(Path.home() / "AppData" / "Local" / "Temp" / "duckdb_temp") + "'")

print("[2/5] Building transaction table...", flush=True)
# Get causal data stores
causal_stores_sql = "SELECT DISTINCT STORE_ID FROM causal_data"
store_ids = tuple(s[0] for s in conn.execute(causal_stores_sql).fetchall())
print(f"     {len(store_ids)} stores", flush=True)

# Build tx table
tx_sql = f"""
CREATE TEMP TABLE tx AS
SELECT
    t.household_key,
    t.STORE_ID,
    t.DAY,
    p.COMMODITY_DESC,
    t.SALES_VALUE,
    t.RETAIL_DISC,
    t.WEEK_NO,
    t.QUANTITY,
    CASE
        WHEN (t.SALES_VALUE - t.RETAIL_DISC) > 0
        THEN -t.RETAIL_DISC / (t.SALES_VALUE - t.RETAIL_DISC)
        ELSE NULL
    END as rate
FROM transaction_data t
JOIN product p ON t.PRODUCT_ID = p.PRODUCT_ID
WHERE
    t.WEEK_NO BETWEEN 9 AND 101
    AND t.STORE_ID IN ({",".join(str(s) for s in store_ids)})
    AND p.COMMODITY_DESC <> 'COUPON/MISC ITEMS'
    AND t.SALES_VALUE > 0
"""
conn.execute(tx_sql)
max_day = conn.execute("SELECT MAX(DAY) FROM tx").fetchall()[0][0]
tx_count = conn.execute("SELECT COUNT(*) FROM tx").fetchall()[0][0]
print(f"     {tx_count:,} transactions, max_day={max_day}", flush=True)

print("[3/5] Finding first deep-discount purchases...", flush=True)
# Find first deep-discount per hh x cat
first_trial_sql = """
CREATE TEMP TABLE first_trial AS
SELECT
    household_key,
    COMMODITY_DESC,
    MIN(DAY) as trial_day
FROM tx
WHERE rate >= 0.30
GROUP BY household_key, COMMODITY_DESC
"""
conn.execute(first_trial_sql)
trial_count = conn.execute("SELECT COUNT(*) FROM first_trial").fetchall()[0][0]
print(f"     {trial_count:,} hh x cat with deep-discount trial", flush=True)

print("[4/5] Computing repeat and conversion (this is slow)...", flush=True)
# For each trial, find repeats and conversions - build a simpler table first
repeats_sql = f"""
CREATE TEMP TABLE trial_repeats AS
SELECT
    ft.household_key,
    ft.COMMODITY_DESC,
    ft.trial_day,
    -- 28-day window
    (ft.trial_day + 28 <= {max_day}) as eligible_28,
    CASE
        WHEN ft.trial_day + 28 <= {max_day}
        THEN (SELECT COUNT(*) > 0 FROM tx t
              WHERE t.household_key = ft.household_key
              AND t.COMMODITY_DESC = ft.COMMODITY_DESC
              AND t.DAY > ft.trial_day AND t.DAY <= ft.trial_day + 28)
        ELSE FALSE
    END as repeat_28,
    CASE
        WHEN ft.trial_day + 28 <= {max_day}
        THEN (SELECT COUNT(*) > 0 FROM tx t
              WHERE t.household_key = ft.household_key
              AND t.COMMODITY_DESC = ft.COMMODITY_DESC
              AND t.DAY > ft.trial_day AND t.DAY <= ft.trial_day + 28
              AND t.rate <= 0.02)
        ELSE FALSE
    END as convert_28,
    -- 56-day window
    (ft.trial_day + 56 <= {max_day}) as eligible_56,
    CASE
        WHEN ft.trial_day + 56 <= {max_day}
        THEN (SELECT COUNT(*) > 0 FROM tx t
              WHERE t.household_key = ft.household_key
              AND t.COMMODITY_DESC = ft.COMMODITY_DESC
              AND t.DAY > ft.trial_day AND t.DAY <= ft.trial_day + 56)
        ELSE FALSE
    END as repeat_56,
    CASE
        WHEN ft.trial_day + 56 <= {max_day}
        THEN (SELECT COUNT(*) > 0 FROM tx t
              WHERE t.household_key = ft.household_key
              AND t.COMMODITY_DESC = ft.COMMODITY_DESC
              AND t.DAY > ft.trial_day AND t.DAY <= ft.trial_day + 56
              AND t.rate <= 0.02)
        ELSE FALSE
    END as convert_56
FROM first_trial ft
"""
conn.execute(repeats_sql)
print("     Computing summary statistics...", flush=True)

print("[5/5] Aggregating results...", flush=True)
# Aggregate results
summary_sql = """
SELECT
    COUNT(*) as total_trials,
    SUM(CASE WHEN eligible_28 THEN 1 ELSE 0 END) as n_elig_28,
    SUM(CASE WHEN eligible_28 AND repeat_28 THEN 1 ELSE 0 END) as repeat_28_count,
    SUM(CASE WHEN eligible_28 AND convert_28 THEN 1 ELSE 0 END) as convert_28_count,
    SUM(CASE WHEN eligible_56 THEN 1 ELSE 0 END) as n_elig_56,
    SUM(CASE WHEN eligible_56 AND repeat_56 THEN 1 ELSE 0 END) as repeat_56_count,
    SUM(CASE WHEN eligible_56 AND convert_56 THEN 1 ELSE 0 END) as convert_56_count
FROM trial_repeats
"""
result = conn.execute(summary_sql).fetchall()[0]

# Build output dataframe
output_data = {
    'metric': ['TOTAL'],
    'total_trials': [result[0]],
    'n_eligible_28': [result[1]],
    'repeat_count_28': [result[2]],
    'convert_to_regular_28': [result[3]],
    'repeat_rate_28_pct': [round(100.0 * result[2] / max(result[1], 1), 2)],
    'conversion_rate_28_pct': [round(100.0 * result[3] / max(result[2], 1), 2)],
    'n_eligible_56': [result[4]],
    'repeat_count_56': [result[5]],
    'convert_to_regular_56': [result[6]],
    'repeat_rate_56_pct': [round(100.0 * result[5] / max(result[4], 1), 2)],
    'conversion_rate_56_pct': [round(100.0 * result[6] / max(result[5], 1), 2)]
}

df = pd.DataFrame(output_data)

print("\n" + "="*120, flush=True)
print("STEP 3 RESULTS: Trial to Regular-Price Conversion", flush=True)
print("="*120, flush=True)
print(df.to_string(index=False), flush=True)

output_file = OUTPUT_DIR / "phase5c_step3_trial_conversion.csv"
df.to_csv(output_file, index=False)
print(f"\n[SAVED] {output_file}", flush=True)

conn.close()
print("\nDone.", flush=True)
