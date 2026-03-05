# PV ROI Demo Summary

- **Run ID:** `2026-03-04_2319_edinburgh_system4kw_load3200_v2`
- **Created (local):** `2026-03-04T23:19:55`
- **PVGIS source:** `downloaded:raw_edinburgh_2020_lat55p9533_lonm3p1883_tilt0_az180.csv`
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

- PV generation: 3,271.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,127.7 kWh (34.5% of PV)
- Energy sent to grid: 2,143.9 kWh
- Energy bought from grid: 2,072.3 kWh
- Self-sufficiency: 35.2% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £637.34
- Annual savings (Tariff B): £598.30
- Payback (Tariff A): 11.0
- Payback (Tariff B): 12.0
- Net Present Value (NPV) (Tariff A): £-170.61
- Net Present Value (NPV) (Tariff B): £-573.94
- ROI (Tariff A): 39.8%
- ROI (Tariff B): 30.1%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,271.6 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,127.7 kWh (34.5% of PV)
- Energy sent to grid: 2,143.9 kWh
- Energy bought from grid: 2,072.3 kWh
- Self-sufficiency: 35.2% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £637.34
- Savings (Tariff B): £598.30

## Confidence checks (Step 3 substitutes)

- Verification checks: PASS=4, FAIL=0
- PVGIS cross-check annual_pct_error: 10.821744527746988
- PVGIS cross-check monthly_mape_pct: 20.336170521110628
- Variability annual savings P10/P50/P90: 640.7702138901284, 643.2012385693431, 645.6322632485579

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
