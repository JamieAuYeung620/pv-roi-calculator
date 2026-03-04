# PV ROI Demo Summary

- **Run ID:** `2026-02-25_1238_leeds_system4kw_load3200`
- **Created (local):** `2026-02-25T12:38:33`
- **PVGIS source:** `downloaded:raw_leeds_2020_lat53p8008_lonm1p5491.csv`
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

- PV generation: 3,312.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,164.2 kWh (35.1% of PV)
- Exported PV: 2,148.1 kWh
- Grid import: 2,035.8 kWh
- Self-sufficiency: 36.4% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £648.20
- Annual savings (Tariff B): £606.35
- Payback (Tariff A): 11.0
- Payback (Tariff B): 12.0
- NPV (Tariff A): £1,943.70
- NPV (Tariff B): £1,358.00
- ROI (Tariff A): 132.2%
- ROI (Tariff B): 114.9%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,312.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,164.2 kWh (35.1% of PV)
- Exported PV: 2,148.1 kWh
- Grid import: 2,035.8 kWh
- Self-sufficiency: 36.4% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £648.20
- Savings (Tariff B): £606.35

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
