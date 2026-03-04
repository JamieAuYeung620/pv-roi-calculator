# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1946_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-03-01T19:46:23`
- **PVGIS source:** `downloaded:raw_warwick_campus_2019_lat52p384_lonm1p5615_tilt0_az180.csv`
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

- PV generation: 3,554.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,188.6 kWh (33.4% of PV)
- Energy sent to grid: 2,366.1 kWh
- Energy bought from grid: 2,011.4 kWh
- Self-sufficiency: 37.1% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £687.72
- Annual savings (Tariff B): £645.13
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- Net Present Value (NPV) (Tariff A): £339.07
- Net Present Value (NPV) (Tariff B): £-101.38
- ROI (Tariff A): 52.1%
- ROI (Tariff B): 41.5%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,554.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,188.6 kWh (33.4% of PV)
- Energy sent to grid: 2,366.1 kWh
- Energy bought from grid: 2,011.4 kWh
- Self-sufficiency: 37.1% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £687.72
- Savings (Tariff B): £645.13

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
