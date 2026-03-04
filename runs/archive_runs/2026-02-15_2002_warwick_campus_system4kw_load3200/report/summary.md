# PV ROI Demo Summary

- **Run ID:** `2026-02-15_2002_warwick_campus_system4kw_load3200`
- **Created (local):** `2026-02-15T20:02:55`
- **PVGIS source:** `cache:raw_warwick_campus_2021_lat52p384_lonm1p5615.csv`

## Inputs

- **Location name:** warwick_campus
- **Lat/Lon:** 52.384, -1.5615
- **Year:** 2021
- **PV system size:** 4.0 kW
- **Annual load target:** 3200.0 kWh/year
- **Load profile:** away_daytime

## Key results (energy)

- **PV generation:** 3,561.5 kWh
- **Household load:** 3,200.0 kWh
- **Self-consumed PV:** 1,187.0 kWh (33.3% of PV)
- **Exported PV:** 2,374.5 kWh
- **Grid import with PV:** 2,013.0 kWh
- **Self-sufficiency:** 37.1% of load met by PV

## Key results (Tariff A quick check)

- **Tariff A import/export:** 0.280 / 0.150 £/kWh
- **Baseline bill (no PV):** £896.00
- **Bill with PV:** £207.47
- **Annual savings (recomputed):** £688.53

## Key results (Finance model: Tariff A vs B)

- **Annual savings (Tariff A):** £688.53
- **Annual savings (Tariff B):** £645.74
- **Payback (Tariff A):** 10.0
- **Payback (Tariff B):** 11.0
- **NPV (Tariff A):** £2,488.57
- **NPV (Tariff B):** £1,889.10
- **ROI (Tariff A):** 148.2%
- **ROI (Tariff B):** 130.5%

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
