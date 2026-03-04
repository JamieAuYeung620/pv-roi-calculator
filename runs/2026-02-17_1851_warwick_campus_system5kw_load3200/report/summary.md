# PV ROI Demo Summary

- **Run ID:** `2026-02-17_1851_warwick_campus_system5kw_load3200`
- **Created (local):** `2026-02-17T18:51:47`
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

- PV generation: 4,451.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,240.4 kWh (27.9% of PV)
- Exported PV: 3,211.5 kWh
- Grid import: 1,959.6 kWh
- Self-sufficiency: 38.8% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £829.02
- Annual savings (Tariff B): £785.23
- Payback (Tariff A): 8.0
- Payback (Tariff B): 9.0
- NPV (Tariff A): £4,385.51
- NPV (Tariff B): £3,771.12
- ROI (Tariff A): 203.6%
- ROI (Tariff B): 185.5%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 4,451.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,240.4 kWh (27.9% of PV)
- Exported PV: 3,211.5 kWh
- Grid import: 1,959.6 kWh
- Self-sufficiency: 38.8% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £829.02
- Savings (Tariff B): £785.23

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
