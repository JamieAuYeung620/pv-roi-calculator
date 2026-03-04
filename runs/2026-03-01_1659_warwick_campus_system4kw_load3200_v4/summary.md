# PV ROI Demo Summary

- **Run ID:** `2026-03-01_1659_warwick_campus_system4kw_load3200_v4`
- **Created (local):** `2026-03-01T16:59:47`
- **PVGIS source:** `cache:raw_warwick_campus_2020_lat52p384_lonm1p5615_tilt0_az180.csv`
- **Tariff mode:** `B`

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
- energy_split: skipped (not available)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (not available)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,752.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,188.2 kWh (31.7% of PV)
- Energy sent to grid: 2,564.2 kWh
- Energy bought from grid: 2,011.8 kWh
- Self-sufficiency: 37.1% of load met by PV

## Finance summary (from finance model)

- Annual savings: £674.58
- Payback: 10.0
- Net Present Value (NPV): £195.68
- ROI: 48.6%
- Peak window (UTC): 16:00–19:00 (end exclusive)

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,752.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,188.2 kWh (31.7% of PV)
- Energy sent to grid: 2,564.2 kWh
- Energy bought from grid: 2,011.8 kWh
- Self-sufficiency: 37.1% of load met by PV

### Period bill (Tariff B)

- Baseline (no PV): £778.28
- With PV: £103.70
- Savings: £674.58

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
  - `outputs/plots/energy_split.png`
  - `outputs/plots/monthly_bill_benefit.png`
  - `outputs/plots/week_timeseries.png`
- Logs:
  - `logs.txt`
