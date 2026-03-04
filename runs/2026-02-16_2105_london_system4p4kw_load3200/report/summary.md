# PV ROI Demo Summary

- **Run ID:** `2026-02-16_2105_london_system4p4kw_load3200`
- **Created (local):** `2026-02-16T21:05:38`
- **PVGIS source:** `cache:raw_london_2020_lat51p5074_lonm0p1278.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / NPV / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly_energy.csv`): YES
- Daily export (`outputs/daily_energy.csv`): NO
- Monthly export (`outputs/monthly_summary.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (not available)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 4,113.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,227.0 kWh (29.8% of PV)
- Exported PV: 2,886.7 kWh
- Grid import: 1,973.0 kWh
- Self-sufficiency: 38.3% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £788.84
- Annual savings (Tariff B): £732.36
- Payback (Tariff A): 9.0
- Payback (Tariff B): 10.0
- NPV (Tariff A): £3,849.14
- NPV (Tariff B): £3,057.67
- ROI (Tariff A): 188.0%
- ROI (Tariff B): 164.6%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 4,113.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,227.0 kWh (29.8% of PV)
- Exported PV: 2,886.7 kWh
- Grid import: 1,973.0 kWh
- Self-sufficiency: 38.3% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £788.84
- Savings (Tariff B): £732.36

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/hourly_energy.csv`
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/energy_split.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
