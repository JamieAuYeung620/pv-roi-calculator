# PV ROI Demo Summary

- **Run ID:** `2026-02-17_1836_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-02-17T18:36:24`
- **PVGIS source:** `bootstrapped_from_existing:raw_warwick_campus.csv`
- **Tariff mode:** `A`

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
- annual_cashflow_bars: skipped (disabled)

## Key results (FULL dataset baseline — used for finance)

- PV generation: 3,561.5 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,187.0 kWh (33.3% of PV)
- Exported PV: 2,374.5 kWh
- Grid import: 2,013.0 kWh
- Self-sufficiency: 37.1% of load met by PV

## Finance summary (from finance model)

- Annual savings: £688.53
- Payback: 10.0
- NPV: £2,488.57
- ROI: 148.2%

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,561.5 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,187.0 kWh (33.3% of PV)
- Exported PV: 2,374.5 kWh
- Grid import: 2,013.0 kWh
- Self-sufficiency: 37.1% of load met by PV

### Period bill (Tariff A)

- Baseline (no PV): £896.00
- With PV: £207.47
- Savings: £688.53

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/monthly_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/week_timeseries.png`
- Logs:
  - `logs.txt`
