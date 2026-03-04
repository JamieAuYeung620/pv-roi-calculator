# PV ROI Demo Summary

- **Run ID:** `2026-02-25_1512_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-02-25T15:12:48`
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

- PV generation: 3,621.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,179.2 kWh (32.6% of PV)
- Exported PV: 2,442.3 kWh
- Grid import: 2,020.8 kWh
- Self-sufficiency: 36.9% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £696.53
- Annual savings (Tariff B): £653.95
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- NPV (Tariff A): £427.74
- NPV (Tariff B): £-12.48
- ROI (Tariff A): 54.2%
- ROI (Tariff B): 43.6%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,621.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,179.2 kWh (32.6% of PV)
- Exported PV: 2,442.3 kWh
- Grid import: 2,020.8 kWh
- Self-sufficiency: 36.9% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £696.53
- Savings (Tariff B): £653.95

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
