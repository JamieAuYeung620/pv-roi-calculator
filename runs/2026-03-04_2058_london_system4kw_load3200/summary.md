# PV ROI Demo Summary

- **Run ID:** `2026-03-04_2058_london_system4kw_load3200`
- **Created (local):** `2026-03-04T20:58:37`
- **PVGIS source:** `downloaded:raw_london_2020_lat51p5074_lonm0p1278_tilt0_az180.csv`
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

- PV generation: 3,875.2 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,205.3 kWh (31.1% of PV)
- Energy sent to grid: 2,669.9 kWh
- Energy bought from grid: 1,994.7 kWh
- Self-sufficiency: 37.7% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £737.96
- Annual savings (Tariff B): £694.04
- Payback (Tariff A): 10.0
- Payback (Tariff B): 10.0
- Net Present Value (NPV) (Tariff A): £846.53
- Net Present Value (NPV) (Tariff B): £392.31
- ROI (Tariff A): 64.2%
- ROI (Tariff B): 53.3%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,875.2 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,205.3 kWh (31.1% of PV)
- Energy sent to grid: 2,669.9 kWh
- Energy bought from grid: 1,994.7 kWh
- Self-sufficiency: 37.7% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £737.96
- Savings (Tariff B): £694.04

## Confidence checks (Step 3 substitutes)

- Verification checks: PASS=4, FAIL=0
- PVGIS cross-check annual_pct_error: 9.46216224206938
- PVGIS cross-check monthly_mape_pct: 14.998944119687971
- Variability annual savings P10/P50/P90: 717.725912130638, 730.2330775165744, 742.7402429025108

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
  - `outputs/pvgis_crosscheck_monthly.csv`
  - `outputs/pvgis_crosscheck_summary.csv`
  - `outputs/plots/pvgis_crosscheck_monthly.png`
  - `outputs/variability_yearly.csv`
  - `outputs/variability_summary.csv`
  - `outputs/variability_annual_savings_vs_year.png`
  - `outputs/variability_annual_savings_vs_year_tariffB.png`
  - `outputs/variability_annual_savings_hist.png`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/energy_split.png`
  - `outputs/plots/monthly_bill_benefit.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
  - `outputs/plots/annual_cashflow_bars.png`
  - `outputs/plots/pvgis_crosscheck_monthly.png`
- Logs:
  - `logs.txt`
