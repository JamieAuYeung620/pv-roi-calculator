# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1739_london_system4kw_load3200`
- **Created (local):** `2026-03-01T17:39:22`
- **PVGIS source:** `downloaded:raw_london_2018_lat51p5074_lonm0p1278_tilt0_az180.csv`
- **Tariff mode:** `compare_all`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / Net Present Value (NPV) / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly.csv`): YES
- Daily export (`outputs/daily.csv`): YES
- Monthly export (`outputs/monthly.csv`): YES
- Monthly financial export (`outputs/financial_monthly.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,846.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,200.3 kWh (31.2% of PV)
- Energy sent to grid: 2,646.4 kWh
- Energy bought from grid: 1,999.7 kWh
- Self-sufficiency: 37.5% of load met by PV

## Finance summary (from finance model)

- Payback: None

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,846.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,200.3 kWh (31.2% of PV)
- Energy sent to grid: 2,646.4 kWh
- Energy bought from grid: 1,999.7 kWh
- Self-sufficiency: 37.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £733.05
- Savings (Tariff B): £689.33

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/hourly.csv`
  - `outputs/hourly_energy.csv`
  - `outputs/daily.csv`
  - `outputs/daily_energy.csv`
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
