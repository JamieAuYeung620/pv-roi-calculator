# PV ROI Calculator (PVGIS-driven)

This project estimates solar generation, home energy flows, and financial outcomes (savings, payback, NPV/ROI) for a chosen location and system setup.

## Run Commands

From repo root:

```bash
python3 src/check_setup.py
```

Write a default config:

```bash
python3 src/pipeline_runner.py --write-default-config demo_config.json
```

Run pipeline with config:

```bash
python3 src/pipeline_runner.py --config demo_config.json
```

Run pipeline with built-in defaults:

```bash
python3 src/pipeline_runner.py
```

Run Streamlit UI:

```bash
python3 -m streamlit run app.py
```

## Where Outputs Appear

Each run writes to:

`runs/<run_id>/`

Key artifacts:

- `config.json` (full config snapshot used for that run)
- `summary.md` (human-readable summary)
- `report/summary.md` (legacy copy for compatibility)
- `summary.html` (standalone shareable report)
- `logs.txt`
- `data/raw_pvgis.csv`
- `data/pvgis_request.txt`
- `outputs/hourly.csv` (if hourly export enabled)
- `outputs/daily.csv` (if daily export enabled)
- `outputs/monthly.csv` (if monthly export enabled)
- `outputs/financial_monthly.csv`
- `outputs/financial_summary.csv`
- `outputs/plots/*.png`

Compatibility aliases are also written for older UI/report references:

- `outputs/hourly_energy.csv`
- `outputs/daily_energy.csv`
- `outputs/monthly_summary.csv`
- `outputs/monthly_fdinancial_summary.csv`

## Notes

- Top-level `outputs/` is still used as an intermediate workspace by core/finance scripts.
- Run-specific reproducible artifacts are stored under `runs/<run_id>/`.
