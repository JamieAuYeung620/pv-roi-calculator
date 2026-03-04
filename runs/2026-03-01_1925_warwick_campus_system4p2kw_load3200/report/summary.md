# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1925_warwick_campus_system4p2kw_load3200`
- **Created (local):** `2026-03-01T19:25:13`
- **PVGIS source:** `downloaded:raw_warwick_campus_2020_lat52p384_lonm1p5615_tilt0_az180.csv`
- **Tariff mode:** `compare`

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

- PV generation: 3,940.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,200.3 kWh (30.5% of PV)
- Energy sent to grid: 2,739.8 kWh
- Energy bought from grid: 1,999.7 kWh
- Self-sufficiency: 37.5% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £747.05
- Annual savings (Tariff B): £704.05
- Payback (Tariff A): 9.0
- Payback (Tariff B): 10.0
- Net Present Value (NPV) (Tariff A): £937.84
- Net Present Value (NPV) (Tariff B): £493.11
- ROI (Tariff A): 66.4%
- ROI (Tariff B): 55.7%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,940.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,200.3 kWh (30.5% of PV)
- Energy sent to grid: 2,739.8 kWh
- Energy bought from grid: 1,999.7 kWh
- Self-sufficiency: 37.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £747.05
- Savings (Tariff B): £704.05

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
