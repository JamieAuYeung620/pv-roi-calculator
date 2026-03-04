# PV ROI Demo Summary

- **Run ID:** `2026-02-15_1955_aron_s_house_system4kw_load3200`
- **Created (local):** `2026-02-15T19:55:32`
- **PVGIS source:** `cache:raw_aron_s_house_2019_lat51p6284_lonm0p1617.csv`

## Inputs

- **Location name:** Aron's house
- **Lat/Lon:** 51.6284, -0.1617
- **Year:** 2019
- **PV system size:** 4.0 kW
- **Annual load target:** 3200.0 kWh/year
- **Load profile:** away_daytime

## Key results (energy)

- **PV generation:** 3,558.0 kWh
- **Household load:** 3,200.0 kWh
- **Self-consumed PV:** 1,201.5 kWh (33.8% of PV)
- **Exported PV:** 2,356.5 kWh
- **Grid import with PV:** 1,998.5 kWh
- **Self-sufficiency:** 37.5% of load met by PV

## Key results (Tariff A quick check)

- **Tariff A import/export:** 0.280 / 0.150 £/kWh
- **Baseline bill (no PV):** £896.00
- **Bill with PV:** £206.10
- **Annual savings (recomputed):** £689.90

## Key results (Finance model: Tariff A vs B)

- **Annual savings (Tariff A):** £689.90
- **Annual savings (Tariff B):** £645.30
- **Payback (Tariff A):** 10.0
- **Payback (Tariff B):** 11.0
- **NPV (Tariff A):** £2,508.66
- **NPV (Tariff B):** £1,883.35
- **ROI (Tariff A):** 148.8%
- **ROI (Tariff B):** 130.3%

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
