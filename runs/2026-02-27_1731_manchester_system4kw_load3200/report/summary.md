# PV ROI Demo Summary

- **Run ID:** `2026-02-27_1731_manchester_system4kw_load3200`
- **Created (local):** `2026-02-27T17:31:49`
- **PVGIS source:** `bootstrapped_from_existing:raw_manchester.csv`
- **Tariff mode:** `B`

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

- PV generation: 3,297.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,149.6 kWh (34.9% of PV)
- Exported PV: 2,148.2 kWh
- Grid import: 2,050.4 kWh
- Self-sufficiency: 35.9% of load met by PV

## Finance summary (from finance model)

- Annual savings: £602.89
- Payback: 12.0
- NPV: £-528.12
- ROI: 31.2%
- Peak window (UTC): 16:00–19:00 (end exclusive)

> Note: Finance comparison plots are only available in `tariff_mode = compare`.

## Period results (analysis window)

- Window: **Full year**
- PV generation: 3,297.8 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,149.6 kWh (34.9% of PV)
- Exported PV: 2,148.2 kWh
- Grid import: 2,050.4 kWh
- Self-sufficiency: 35.9% of load met by PV

### Period bill (Tariff B)

- Baseline (no PV): £778.27
- With PV: £175.39
- Savings: £602.89

## Output files in this run folder

- Data:
  - `data/raw_pvgis.csv`
- Outputs:
  - `outputs/monthly_summary.csv`
  - `outputs/monthly_fdinancial_summary.csv`
  - `outputs/financial_summary.csv`
- Plots:
  - `outputs/plots/monthly_pv_vs_load.png`
  - `outputs/plots/monthly_bill_benefit.png`
  - `outputs/plots/week_timeseries.png`
- Logs:
  - `logs.txt`
