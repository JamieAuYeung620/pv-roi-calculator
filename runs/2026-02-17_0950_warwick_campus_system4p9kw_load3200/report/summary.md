# PV ROI Demo Summary

- **Run ID:** `2026-02-17_0950_warwick_campus_system4p9kw_load3200`
- **Created (local):** `2026-02-17T09:50:08`
- **PVGIS source:** `cache:raw_warwick_campus_2021_lat52p384_lonm1p5615.csv`
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

- PV generation: 4,362.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,235.9 kWh (28.3% of PV)
- Exported PV: 3,126.9 kWh
- Grid import: 1,964.1 kWh
- Self-sufficiency: 38.6% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £815.08
- Annual savings (Tariff B): £771.37
- Payback (Tariff A): 9.0
- Payback (Tariff B): 10.0
- NPV (Tariff A): £-793.90
- NPV (Tariff B): £-1,135.60
- ROI (Tariff A): 173.3%
- ROI (Tariff B): 156.6%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 4,362.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,235.9 kWh (28.3% of PV)
- Exported PV: 3,126.9 kWh
- Grid import: 1,964.1 kWh
- Self-sufficiency: 38.6% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £815.08
- Savings (Tariff B): £771.37

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
