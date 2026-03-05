# PV ROI Demo Summary

- **Run ID:** `2026-03-04_2148_warwick_campus_system4kw_load4000`
- **Created (local):** `2026-03-04T21:48:57`
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
- energy_split: skipped (not available)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (not available)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,460.6 kWh
- Load: 4,000.0 kWh
- Self-consumed PV: 1,378.4 kWh (39.8% of PV)
- Energy sent to grid: 2,082.2 kWh
- Energy bought from grid: 2,621.6 kWh
- Self-sufficiency: 34.5% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £698.28
- Annual savings (Tariff B): £652.10
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- Net Present Value (NPV) (Tariff A): £447.70
- Net Present Value (NPV) (Tariff B): £-28.72
- ROI (Tariff A): 54.7%
- ROI (Tariff B): 43.2%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,460.6 kWh
- Load: 4,000.0 kWh
- Self-consumed PV: 1,378.4 kWh (39.8% of PV)
- Energy sent to grid: 2,082.2 kWh
- Energy bought from grid: 2,621.6 kWh
- Self-sufficiency: 34.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £698.28
- Savings (Tariff B): £652.10

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
  - `outputs/plots/energy_split.png`
  - `outputs/plots/monthly_bill_benefit.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
  - `outputs/plots/annual_cashflow_bars.png`
- Logs:
  - `logs.txt`
