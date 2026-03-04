# PV ROI Demo Summary

- **Run ID:** `2026-02-18_1216_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-02-18T12:16:36`
- **PVGIS source:** `cache:raw_warwick_campus_2020_lat52p384_lonm1p5615.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / NPV / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly_energy.csv`): NO
- Daily export (`outputs/daily_energy.csv`): NO
- Monthly export (`outputs/monthly_summary.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (not available)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,590.3 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,189.6 kWh (33.1% of PV)
- Exported PV: 2,400.7 kWh
- Grid import: 2,010.4 kWh
- Self-sufficiency: 37.2% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £693.19
- Annual savings (Tariff B): £650.35
- Payback (Tariff A): 10.0
- Payback (Tariff B): 11.0
- NPV (Tariff A): £394.46
- NPV (Tariff B): £-48.56
- ROI (Tariff A): 53.4%
- ROI (Tariff B): 42.7%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,590.3 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,189.6 kWh (33.1% of PV)
- Exported PV: 2,400.7 kWh
- Grid import: 2,010.4 kWh
- Self-sufficiency: 37.2% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £693.19
- Savings (Tariff B): £650.35

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
  - `outputs/plots/annual_cashflow_bars.png`
- Logs:
  - `logs.txt`
