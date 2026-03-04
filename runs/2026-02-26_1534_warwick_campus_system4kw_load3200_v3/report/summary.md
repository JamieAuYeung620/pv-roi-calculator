# PV ROI Demo Summary

- **Run ID:** `2026-02-26_1534_warwick_campus_system4kw_load3200_v3`
- **Created (local):** `2026-02-26T15:34:59`
- **PVGIS source:** `cache:raw_warwick_campus_2020_lat52p384_lonm1p5615.csv`
- **Tariff mode:** `compare`

## Analysis window (controls plots + exported CSVs)

- **Mode:** `custom`
- **Requested:** `2020-08-01` to `2020-08-31` (inclusive)
- **Used (after clamping):** `2020-08-01` to `2020-08-31` (inclusive)

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

- PV generation: 3,752.4 kWh
- Load: 3,200.0 kWh
- Self-consumed PV: 1,188.2 kWh (31.7% of PV)
- Exported PV: 2,564.2 kWh
- Grid import: 2,011.8 kWh
- Self-sufficiency: 37.1% of load met by PV

## Finance summary (from finance model)

- Annual savings (Tariff A): £717.34
- Annual savings (Tariff B): £674.58
- Payback (Tariff A): 10.0
- Payback (Tariff B): 10.0
- NPV (Tariff A): £637.85
- NPV (Tariff B): £195.68
- ROI (Tariff A): 59.2%
- ROI (Tariff B): 48.6%

## Period results (analysis window)

- Window: **2020-08-01 to 2020-08-31**
- PV generation: 401.8 kWh
- Load: 236.8 kWh
- Self-consumed PV: 121.9 kWh (30.3% of PV)
- Exported PV: 279.8 kWh
- Grid import: 114.8 kWh
- Self-sufficiency: 51.5% of load met by PV

### Period bill (Tariff A vs B)

- Savings (Tariff A): £76.12
- Savings (Tariff B): £72.55

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
  - `outputs/plots/cumulative_cashflow.png`
- Logs:
  - `logs.txt`
