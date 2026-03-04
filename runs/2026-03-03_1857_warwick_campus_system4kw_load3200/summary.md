# PV ROI Demo Summary

- **Run ID:** `2026-03-03_1857_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-03-03T18:57:23`
- **PVGIS source:** `downloaded:raw_warwick_campus_2005_lat52p384_lonm1p5615_tilt0_az180.csv`
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

- PV generation: 3,460.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,168.2 kWh (33.8% of PV)
- Energy sent to grid: 2,292.4 kWh
- Energy bought from grid: 2,031.8 kWh
- Self-sufficiency: 36.5% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £670.95
- Annual savings (Tariff B): £632.54
- Payback (Tariff A): 11.0
- Payback (Tariff B): 11.0
- Net Present Value (NPV) (Tariff A): £168.85
- Net Present Value (NPV) (Tariff B): £-227.82
- ROI (Tariff A): 48.0%
- ROI (Tariff B): 38.4%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,460.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,168.2 kWh (33.8% of PV)
- Energy sent to grid: 2,292.4 kWh
- Energy bought from grid: 2,031.8 kWh
- Self-sufficiency: 36.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £670.95
- Savings (Tariff B): £632.54

## Confidence checks (Step 3 substitutes)

- Verification checks: PASS=4, FAIL=0
- PVGIS cross-check: not enabled.
- Variability run: not enabled.

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/verification_checks.csv`
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
