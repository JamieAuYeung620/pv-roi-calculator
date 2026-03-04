# PV ROI Demo Summary

- **Run ID:** `2026-02-17_1836_warwick_campus_system4kw_load3200_v2`
- **Created (local):** `2026-02-17T18:36:42`
- **PVGIS source:** `downloaded:raw_warwick_campus_2019_lat52p384_lonm1p5615.csv`
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

- PV generation: 3,400.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,191.8 kWh (35.0% of PV)
- Exported PV: 2,208.9 kWh
- Grid import: 2,008.2 kWh
- Self-sufficiency: 37.2% of load met by PV

## Finance summary (from finance model)

- Annual savings: £665.03
- Payback: 11.0
- NPV: £2,172.20
- ROI: 138.9%

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,400.7 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,191.8 kWh (35.0% of PV)
- Exported PV: 2,208.9 kWh
- Grid import: 2,008.2 kWh
- Self-sufficiency: 37.2% of load met by PV

### Period bill (Tariff A)

- Baseline (no PV): £896.00
- With PV: £230.97
- Savings: £665.03

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
