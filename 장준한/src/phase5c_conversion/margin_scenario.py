"""
Step 1: Gross Margin Sensitivity Analysis
Pure arithmetic on confirmed Phase 3B-0 PART A numbers
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT, TABLES_DIR, ensure_dirs  # noqa: E402
ensure_dirs()
# ──────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

# Confirmed incremental values per shopping opportunity
delta_sales = 0.019989  # incremental actual revenue
delta_reg = 0.033505    # incremental value at regular price
panel_size = 46_714_794  # total shopping opportunities

# Margin rates to evaluate
margin_rates = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

# Breakeven margin (where profit = 0)
# profit(m) = ΔSALES − (1−m)·ΔREG = 0
# ΔSALES = ΔREG − m·ΔREG
# m = 1 − ΔSALES/ΔREG
breakeven_margin = 1 - (delta_sales / delta_reg)

# Build results table
results = []

for m in margin_rates:
    # profit(m) = ΔSALES − (1−m)·ΔREG
    profit_per_opportunity = delta_sales - (1 - m) * delta_reg

    # Per 1,000 opportunities
    profit_per_1k = profit_per_opportunity * 1_000

    # Total across panel
    profit_total = profit_per_opportunity * panel_size

    results.append({
        'gross_margin_pct': int(m * 100),
        'profit_per_opportunity': profit_per_opportunity,
        'profit_per_1000_opp': profit_per_1k,
        'profit_total_panel': profit_total,
        'breakeven_flag': 'BREAKEVEN' if abs(profit_per_opportunity) < 0.00001 else ('LOSS' if profit_per_opportunity < 0 else 'PROFIT'),
    })

df = pd.DataFrame(results)

# Add breakeven row for reference
breakeven_row = {
    'gross_margin_pct': int(round(breakeven_margin * 100, 1)),
    'profit_per_opportunity': 0.0,
    'profit_per_1000_opp': 0.0,
    'profit_total_panel': 0.0,
    'breakeven_flag': 'BREAKEVEN (m*)',
}

# Insert at appropriate position
df_final = pd.concat([
    pd.DataFrame([breakeven_row]),
    df
], ignore_index=True)

# Sort by margin for readability
df_final = df_final.sort_values('gross_margin_pct').reset_index(drop=True)

print("\n=== GROSS MARGIN SENSITIVITY ANALYSIS ===\n")
print(f"Confirmed PART A incremental values per shopping opportunity:")
print(f"  ΔSALES (incremental revenue)      : ${delta_sales:.6f}")
print(f"  ΔREG (incremental regular value) : ${delta_reg:.6f}")
print(f"  Discount to shopper              : ${delta_reg - delta_sales:.6f}")
print(f"\nPanel size: {panel_size:,} shopping opportunities")
print(f"\nBreakeven gross margin m* = {breakeven_margin:.4f} = {breakeven_margin*100:.2f}%")
print(f"\nProfit scenarios:\n")
print(df_final.to_string(index=False))

# Save to CSV
output_path = str(TABLES_DIR / 'phase5c_margin_sensitivity.csv')

# Ensure directory exists
import os
os.makedirs(os.path.dirname(output_path), exist_ok=True)

df_final.to_csv(output_path, index=False)
print(f"\n[SAVED] Saved to {output_path}")

# Summary statistics
df_profitable = df_final[df_final['breakeven_flag'] == 'PROFIT']
print(f"\nMargins >= {breakeven_margin*100:.2f}% are profit-positive.")
print(f"At m=45%: profit of ${df_final[df_final['gross_margin_pct']==45]['profit_per_opportunity'].values[0]:.6f} per opp")
print(f"At m=50%: profit of ${df_final[df_final['gross_margin_pct']==50]['profit_per_opportunity'].values[0]:.6f} per opp")
