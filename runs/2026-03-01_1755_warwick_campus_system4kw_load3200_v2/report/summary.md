# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1755_warwick_campus_system4kw_load3200_v2`
- **Created (local):** `2026-03-01T17:55:58`
- **PVGIS source:** `downloaded:raw_warwick_campus_2020_lat52p384_lonm1p5615_tilt30_az315.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / Net Present Value (NPV) / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly.csv`): NO
- Daily export (`outputs/daily.csv`): NO
- Monthly export (`outputs/monthly.csv`): YES
- Monthly financial export (`outputs/financial_monthly.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 2,916.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,135.3 kWh (38.9% of PV)
- Energy sent to grid: 1,781.0 kWh
- Energy bought from grid: 2,064.7 kWh
- Self-sufficiency: 35.5% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £585.05
- Annual savings (Tariff B): £547.42
- Payback (Tariff A): 12.0
- Payback (Tariff B): 13.0
- Net Present Value (NPV) (Tariff A): £-699.36
- Net Present Value (NPV) (Tariff B): £-1,086.21
- ROI (Tariff A): 27.1%
- ROI (Tariff B): 17.8%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 2,916.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,135.3 kWh (38.9% of PV)
- Energy sent to grid: 1,781.0 kWh
- Energy bought from grid: 2,064.7 kWh
- Self-sufficiency: 35.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £585.05
- Savings (Tariff B): £547.42

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/monthly.csv`
  - `outputs/monthly_summary.csv`
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
