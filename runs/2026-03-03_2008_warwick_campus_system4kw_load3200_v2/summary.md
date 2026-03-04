# PV ROI Demo Summary

- **Run ID:** `2026-03-03_2008_warwick_campus_system4kw_load3200_v2`
- **Created (local):** `2026-03-03T20:08:35`
- **PVGIS source:** `downloaded:raw_warwick_campus_2022_lat52p384_lonm1p5615_tilt0_az180.csv`
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

- PV generation: 3,721.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,192.3 kWh (32.0% of PV)
- Energy sent to grid: 2,528.8 kWh
- Energy bought from grid: 2,007.7 kWh
- Self-sufficiency: 37.3% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £713.16
- Annual savings (Tariff B): £670.48
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- Net Present Value (NPV) (Tariff A): £596.31
- Net Present Value (NPV) (Tariff B): £154.85
- ROI (Tariff A): 58.2%
- ROI (Tariff B): 47.6%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,721.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,192.3 kWh (32.0% of PV)
- Energy sent to grid: 2,528.8 kWh
- Energy bought from grid: 2,007.7 kWh
- Self-sufficiency: 37.3% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £713.16
- Savings (Tariff B): £670.48

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
