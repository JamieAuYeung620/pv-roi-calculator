# PV ROI Calculator

This dissertation project provides a Streamlit app for estimating rooftop solar PV generation, household energy flows, bill savings, payback, and discounted financial outcomes using PVGIS-backed weather data.

## Quick Start

If you only want to open the app with the least effort, use one command from the repository root:

### macOS

```bash
python3 run_app.py
```

Or double-click `run_app_mac.command`.

### Windows

```bat
py -3 run_app.py
```

Or double-click `run_app_windows.bat`.

### Linux

```bash
python3 run_app.py
```

Or run:

```bash
./run_app.sh
```

What this does:

- creates `.venv/` automatically if needed
- installs packages from `requirements.txt` if they are missing
- runs a quick preflight check
- launches the Streamlit app from the correct repository location

On the first run, dependency installation may take a minute or two. Later launches should usually be just the same single command.

## Minimum-Effort Path For A Grader

1. Download or clone the repository.
2. Open a terminal in the repository root.
3. Run `python3 run_app.py` on macOS/Linux, or `py -3 run_app.py` on Windows.
4. Wait for the browser tab to open.

If the browser does not open automatically, the terminal will print a local URL such as `http://127.0.0.1:8501`.

## What You Should See

The browser should open a page titled `Solar ROI Calculator`.

You should see:

- a Streamlit app with calculator inputs for location, PV system, tariffs, and finance assumptions
- a main results area showing savings, payback, charts, and downloadable outputs after a run
- access to prior run folders stored under `runs/`

## Quick Environment Check

To run a fast preflight check without launching the browser:

### macOS / Linux

```bash
python3 run_app.py --check-only
```

### Windows

```bat
py -3 run_app.py --check-only
```

This verifies that the repository contains the required files and that the local virtual environment has the packages needed to launch the app.

## Manual Fresh-Environment Setup

If you prefer explicit setup commands rather than the automatic launcher:

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_app.py --check-only
python -m streamlit run app.py
```

### Windows

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python run_app.py --check-only
python -m streamlit run app.py
```

The existing manual Streamlit entrypoint from repo root is still:

```bash
python -m streamlit run app.py
```

## Outputs

Run-specific outputs are written to:

`runs/<run_id>/`

Typical files include:

- `runs/<run_id>/config.json`
- `runs/<run_id>/summary.md`
- `runs/<run_id>/summary.html`
- `runs/<run_id>/logs.txt`
- `runs/<run_id>/data/raw_pvgis.csv`
- `runs/<run_id>/outputs/financial_summary.csv`
- `runs/<run_id>/outputs/financial_monthly.csv`
- `runs/<run_id>/outputs/hourly.csv`, `daily.csv`, `monthly.csv` when enabled
- `runs/<run_id>/outputs/plots/*.png`

The top-level `outputs/` directory is still used as an intermediate workspace by the existing pipeline scripts, so it remains part of the project structure.

## Troubleshooting

- If the first launch seems slow, wait a little longer: the helper may be creating `.venv/` and installing Python packages.
- If Python is not found, install Python 3 and re-run the same command.
- If the browser does not open, copy the local URL shown in the terminal into your browser.
- If port `8501` is already in use, `run_app.py` will automatically choose the next available local port and print it.
- If you want to check readiness without launching the app, use `--check-only`.
- If you test a brand-new custom location and PVGIS data is not already cached, an internet connection may be needed for that data download.

## Tested Python Version

This repository was smoke-checked in this submission workspace with Python `3.14.3`.

## Existing CLI / Pipeline Scripts

The dissertation calculation and reporting scripts are still available exactly as before. For example:

```bash
python src/check_setup.py
python src/pipeline_runner.py --write-default-config demo_config.json
python src/pipeline_runner.py --config demo_config.json
```

These paths are unchanged; the new launcher is only a convenience layer for opening the Streamlit app reliably from the repository root.
