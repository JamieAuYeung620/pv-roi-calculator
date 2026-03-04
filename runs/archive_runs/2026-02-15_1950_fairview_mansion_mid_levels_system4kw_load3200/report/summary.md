# PV ROI Demo Summary

- **Run ID:** `2026-02-15_1950_fairview_mansion_mid_levels_system4kw_load3200`
- **Created (local):** `2026-02-15T19:50:12`
- **PVGIS source:** `downloaded:raw_fairview_mansion_mid_levels_2019_lat22p2828_lon114p1472.csv`

## Inputs

- **Location name:** fairview_mansion_mid_levels
- **Lat/Lon:** 22.2828, 114.1472
- **Year:** 2019
- **PV system size:** 4.0 kW
- **Annual load target:** 3200.0 kWh/year
- **Load profile:** away_daytime

## Key results (energy)

- **PV generation:** 5,122.8 kWh
- **Household load:** 3,200.0 kWh
- **Self-consumed PV:** 1,115.3 kWh (21.8% of PV)
- **Exported PV:** 4,007.4 kWh
- **Grid import with PV:** 2,084.7 kWh
- **Self-sufficiency:** 34.9% of load met by PV

## Key results (Tariff A quick check)

- **Tariff A import/export:** 0.280 / 0.150 £/kWh
- **Baseline bill (no PV):** £896.00
- **Bill with PV:** £-17.41
- **Annual savings (recomputed):** £913.41

## Key results (Finance model: Tariff A vs B)

- **Annual savings (Tariff A):** £913.41
- **Annual savings (Tariff B):** £846.49
- **Payback (Tariff A):** 8.0
- **Payback (Tariff B):** 8.0
- **NPV (Tariff A):** £5,514.28
- **NPV (Tariff B):** £4,578.02
- **ROI (Tariff A):** 236.5%
- **ROI (Tariff B):** 208.9%

## Output files in this run folder

- `outputs/hourly_energy.csv`
- `outputs/monthly_summary.csv`
- `outputs/financial_summary.csv`
- `outputs/plots/monthly_pv_vs_load.png`
- `outputs/plots/week_timeseries.png`
- `outputs/plots/energy_split.png`
- `outputs/plots/cumulative_cashflow.png`
- `outputs/plots/annual_cashflow_bars.png`
- `logs.txt`
