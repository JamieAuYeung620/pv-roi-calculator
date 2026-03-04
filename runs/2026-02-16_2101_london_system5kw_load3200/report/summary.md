# PV ROI Demo Summary

- **Run ID:** `2026-02-16_2101_london_system5kw_load3200`
- **Created (local):** `2026-02-16T21:01:48`
- **PVGIS source:** `downloaded:raw_london_2020_lat51p5074_lonm0p1278.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `full_year`
- Full dataset used for exports + plots.

> **Important:** Lifetime ROI / NPV / payback are still computed on the full dataset (baseline).

## Exports enabled

- Hourly export (`outputs/hourly_energy.csv`): YES
- Daily export (`outputs/daily_energy.csv`): NO
- Monthly export (`outputs/monthly_summary.csv`): YES

## Plots

- monthly_pv_vs_load: skipped (not available)
- week_timeseries: skipped (not available)
- energy_split: skipped (not available)
- cumulative_cashflow: skipped (not available)
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 4,674.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,255.9 kWh (26.9% of PV)
- Exported PV: 3,418.8 kWh
- Grid import: 1,944.1 kWh
- Self-sufficiency: 39.2% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £864.47
- Annual savings (Tariff B): £819.72
- Payback (Tariff A): 8.0
- Payback (Tariff B): 9.0
- NPV (Tariff A): £4,863.75
- NPV (Tariff B): £4,235.84
- ROI (Tariff A): 217.6%
- ROI (Tariff B): 199.1%

## Period results (analysis window)

- Window: **Full year**
- PV generation: 4,674.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,255.9 kWh (26.9% of PV)
- Exported PV: 3,418.8 kWh
- Grid import: 1,944.1 kWh
- Self-sufficiency: 39.2% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £864.47
- Savings (Tariff B): £819.72

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/hourly_energy.csv`
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/energy_split.png`
  - `outputs/plots/week_timeseries.png`
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
