# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1957_warwick_campus_system4kw_load3200_v3`
- **Created (local):** `2026-03-01T19:57:44`
- **PVGIS source:** `downloaded:raw_warwick_campus_2023_lat52p384_lonm1p5615_tilt0_az180.csv`
- **Tariff mode:** `compare_all`

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

- PV generation: 3,793.0 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,193.8 kWh (31.5% of PV)
- Energy sent to grid: 2,599.3 kWh
- Energy bought from grid: 2,006.2 kWh
- Self-sufficiency: 37.3% of load met by PV

## Finance summary (from finance model)

- Payback: None

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,793.0 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,193.8 kWh (31.5% of PV)
- Energy sent to grid: 2,599.3 kWh
- Energy bought from grid: 2,006.2 kWh
- Self-sufficiency: 37.3% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £724.15
- Savings (Tariff B): £682.07

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
