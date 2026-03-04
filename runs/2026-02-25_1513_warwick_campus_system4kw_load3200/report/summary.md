# PV ROI Demo Summary

- **Run ID:** `2026-02-25_1513_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-02-25T15:13:21`
- **PVGIS source:** `cache:raw_warwick_campus_2020_lat52p384_lonm1p5615.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / NPV / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly_energy.csv`): NO
- Daily export (`outputs/daily_energy.csv`): NO
- Monthly export (`outputs/monthly_summary.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,490.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,169.7 kWh (33.5% of PV)
- Exported PV: 2,321.0 kWh
- Grid import: 2,030.3 kWh
- Self-sufficiency: 36.6% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £675.65
- Annual savings (Tariff B): £633.27
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- NPV (Tariff A): £216.92
- NPV (Tariff B): £-221.20
- ROI (Tariff A): 49.1%
- ROI (Tariff B): 38.6%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,490.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,169.7 kWh (33.5% of PV)
- Exported PV: 2,321.0 kWh
- Grid import: 2,030.3 kWh
- Self-sufficiency: 36.6% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £675.65
- Savings (Tariff B): £633.27

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
