# PV ROI Demo Summary

- **Run ID:** `2026-02-25_1250_bristol_system4kw_load3200_v2`
- **Created (local):** `2026-02-25T12:50:42`
- **PVGIS source:** `cache:raw_bristol_2020_lat51p4545_lonm2p5879.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / NPV / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly_energy.csv`): YES
- Daily export (`outputs/daily_energy.csv`): YES
- Monthly export (`outputs/monthly_summary.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (disabled)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,728.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,199.0 kWh (32.2% of PV)
- Exported PV: 2,529.2 kWh
- Grid import: 2,001.0 kWh
- Self-sufficiency: 37.5% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £715.08
- Annual savings (Tariff B): £673.12
- Payback (Tariff A): 10.0
- Payback (Tariff B): 10.0
- NPV (Tariff A): £2,846.34
- NPV (Tariff B): £2,258.56
- ROI (Tariff A): 158.6%
- ROI (Tariff B): 141.3%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,728.1 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,199.0 kWh (32.2% of PV)
- Exported PV: 2,529.2 kWh
- Grid import: 2,001.0 kWh
- Self-sufficiency: 37.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £715.08
- Savings (Tariff B): £673.12

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/hourly_energy.csv`
  - `outputs/daily_energy.csv`
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
