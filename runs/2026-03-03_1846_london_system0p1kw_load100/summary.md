# PV ROI Demo Summary

- **Run ID:** `2026-03-03_1846_london_system0p1kw_load100`
- **Created (local):** `2026-03-03T18:46:06`
- **PVGIS source:** `downloaded:raw_london_2005_lat51p5074_lonm0p1278_tilt0_az180.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / Net Present Value (NPV) / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly.csv`): NO
- Daily export (`outputs/daily.csv`): NO
- Monthly export (`outputs/monthly.csv`): NO
- Monthly financial export (`outputs/financial_monthly.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 94.7 kWh
- Load: 100.0 kWh
- Self-consumed PV: 35.0 kWh (37.0% of PV)
- Energy sent to grid: 59.7 kWh
- Energy bought from grid: 65.0 kWh
- Self-sufficiency: 35.0% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £0.00
- Annual savings (Tariff B): £0.00
- Payback (Tariff A): nan
- Payback (Tariff B): nan
- Net Present Value (NPV) (Tariff A): £-200,500.00
- Net Present Value (NPV) (Tariff B): £-200,500.00
- ROI (Tariff A): -40100.0%
- ROI (Tariff B): -40100.0%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 94.7 kWh
- Load: 100.0 kWh
- Self-consumed PV: 35.0 kWh (37.0% of PV)
- Energy sent to grid: 59.7 kWh
- Energy bought from grid: 65.0 kWh
- Self-sufficiency: 35.0% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £0.00
- Savings (Tariff B): £0.00

## Confidence checks (Step 3 substitutes)

- Verification checks: not generated.
- PVGIS cross-check: not enabled.
- Variability run: not enabled.

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/financial_monthly.csv`
  - `outputs/monthly_fdinancial_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/monthly_bill_benefit.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
