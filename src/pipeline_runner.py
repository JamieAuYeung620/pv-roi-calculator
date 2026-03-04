# src/pipeline_runner.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, Tuple

# Required dependencies (same as your scripts)
try:
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")  # safe for headless + still OK locally
    import matplotlib.pyplot as plt
except Exception as exc:
    print("ERROR: Missing required packages. This runner requires: pandas, numpy, matplotlib")
    print("Fix: Activate your virtual environment, then run:")
    print("  python -m pip install -r requirements.txt")
    print("Details:", repr(exc))
    sys.exit(1)

from config_schema import (
    PVROIRunConfig,
    load_config_json,
    make_default_config,
    save_config_json,
    validate_config,
)
from run_manager import init_run, slugify, float_to_slug, repo_root
from report_generator import generate_run_report
from datetime import datetime, timezone
from pvgis_pipeline import fetch_pvgis_pvcalc_hourly, load_cached_csv, save_csv
from step3_confidence import (
    compute_verification_checks,
    write_verification_csv,
    summarize_distribution,
    plot_annual_savings_vs_year,
    plot_histogram,
)



ENERGY_COLS = ["pv_kwh", "load_kwh", "self_consumed_kwh", "exported_kwh", "grid_import_kwh"]


# -----------------------------
# Subprocess helper
# -----------------------------
def run_subprocess(cmd: list[str], cwd: Path, logger) -> int:
    """
    Run a command and write stdout/stderr into logs.txt.
    """
    logger.info("Running command:\n  %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)

    if result.stdout:
        logger.info("----- STDOUT START -----\n%s\n----- STDOUT END -----", result.stdout)
    if result.stderr:
        logger.info("----- STDERR START -----\n%s\n----- STDERR END -----", result.stderr)

    if result.returncode != 0:
        logger.error("Command failed with return code: %s", result.returncode)

    return result.returncode


# -----------------------------
# PVGIS cache + compatibility
# -----------------------------
def ensure_pvgis_data(cfg: PVROIRunConfig, run_dir: Path, logger) -> Tuple[Path, str]:
    """
    Ensure data/raw_<location>.csv exists (for roi_calculator_core.py),
    while storing the real cache in data/cache/.

    Returns:
      (raw_path_used_by_core, source_string)
    """
    root = repo_root()

    location_slug = slugify(cfg.location.name)
    raw_path = root / "data" / f"raw_{location_slug}.csv"

    cache_dir = root / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    lat_slug = float_to_slug(cfg.location.lat)
    lon_slug = float_to_slug(cfg.location.lon)
    tilt_slug = float_to_slug(cfg.pv.surface_tilt_deg)
    azimuth_slug = float_to_slug(cfg.pv.surface_azimuth_deg)
    cache_path = cache_dir / (
        f"raw_{location_slug}_{cfg.location.year}_lat{lat_slug}_lon{lon_slug}"
        f"_tilt{tilt_slug}_az{azimuth_slug}.csv"
    )

    # 1) Prefer cache if it exists
    if cache_path.exists() and not cfg.location.force_download:
        logger.info("PVGIS: Using cache file: %s", cache_path)
        shutil.copy2(cache_path, raw_path)
        source = f"cache:{cache_path.name}"

    # 2) If no cache, but raw_path exists (older workflow), bootstrap cache
    elif (
        raw_path.exists()
        and not cfg.location.force_download
        and float(cfg.pv.surface_tilt_deg) == 0.0
        and float(cfg.pv.surface_azimuth_deg) == 180.0
    ):
        logger.info("PVGIS: No cache file yet, but found existing data file: %s", raw_path)
        logger.info("PVGIS: Bootstrapping cache by copying raw -> cache.")
        shutil.copy2(raw_path, cache_path)
        source = f"bootstrapped_from_existing:{raw_path.name}"

    # 3) Otherwise, attempt PVGIS download using your existing script
    else:
        logger.info("PVGIS: Attempting PVGIS fetch via src/pvgis_pipeline.py ...")
        cmd = [
            sys.executable, "src/pvgis_pipeline.py",
            "--lat", str(cfg.location.lat),
            "--lon", str(cfg.location.lon),
            "--year", str(cfg.location.year),
            "--surface-tilt", str(cfg.pv.surface_tilt_deg),
            "--surface-azimuth", str(cfg.pv.surface_azimuth_deg),
            "--location", location_slug,
            "--force",
        ]

        rc = run_subprocess(cmd, cwd=root, logger=logger)

        if rc != 0:
            # Fallback: if cache exists, use it
            if cache_path.exists():
                logger.error("PVGIS fetch failed. Falling back to cached file: %s", cache_path)
                shutil.copy2(cache_path, raw_path)
                source = f"fallback_cache:{cache_path.name}"
            else:
                raise RuntimeError(
                    "PVGIS fetch failed and no cache is available.\n"
                    f"- Expected cache path: {cache_path}\n"
                    "Fix: check your internet/VPN, or run once when PVGIS is reachable to build the cache.\n"
                    f"See logs: {run_dir / 'logs.txt'}"
                )
        else:
            # Download success: copy into cache for future runs
            if not raw_path.exists():
                raise RuntimeError(
                    "PVGIS script reported success, but raw CSV was not found:\n"
                    f"  {raw_path}\n"
                    f"See logs: {run_dir / 'logs.txt'}"
                )

            shutil.copy2(raw_path, cache_path)
            source = f"downloaded:{cache_path.name}"
            logger.info("PVGIS: Saved cache file: %s", cache_path)

    # Always copy PVGIS raw into the run folder (required by run spec)
    run_raw_dest = run_dir / "data" / "raw_pvgis.csv"
    shutil.copy2(raw_path, run_raw_dest)
    logger.info("Run data saved: %s", run_raw_dest)

    return raw_path, source
def write_pvgis_provenance(cfg: PVROIRunConfig, run_dir: Path, pvgis_source: str, logger) -> Path:
    """
    Write runs/<run_id>/data/pvgis_request.txt capturing enough info to reproduce the PVGIS call.
    """
    # Try to import the pinned PVGIS base URL from your PVGIS module
    try:
        from pvgis_pipeline import PVGIS_URL  # src/pvgis_pipeline.py
    except Exception:
        PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/"

    prov_path = run_dir / "data" / "pvgis_request.txt"
    prov_path.parent.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # The parameters used by src/pvgis_pipeline.py -> pvlib.iotools.get_pvgis_hourly(...)
    params = {
        "latitude": cfg.location.lat,
        "longitude": cfg.location.lon,
        "start_year": cfg.location.year,
        "end_year": cfg.location.year,
        "surface_tilt_deg": cfg.pv.surface_tilt_deg,
        "surface_azimuth_deg": cfg.pv.surface_azimuth_deg,
        "components": True,
        "pvcalculation": False,
        "map_variables": True,
        "timeout_seconds": 60,
    }

    # Also record actual data range from the run’s copied raw_pvgis.csv (if available)
    data_range_line = "Data range: (unknown)"
    raw_run_csv = run_dir / "data" / "raw_pvgis.csv"
    try:
        if raw_run_csv.exists():
            ts = pd.read_csv(raw_run_csv, usecols=["timestamp"])
            ts["timestamp"] = pd.to_datetime(ts["timestamp"], utc=True, errors="coerce")
            ts = ts.dropna()
            if not ts.empty:
                data_min = ts["timestamp"].min()
                data_max = ts["timestamp"].max()
                data_range_line = f"Data range (UTC): {data_min} to {data_max}"
    except Exception as e:
        logger.warning("Could not read data range from raw_pvgis.csv: %s", repr(e))

    lines = []
    lines.append("Data Source: PVGIS (JRC) — via pvlib.iotools.get_pvgis_hourly")
    lines.append(f"Timestamp (UTC): {now_utc}")
    lines.append("")
    lines.append(f"PVGIS base URL: {PVGIS_URL}")
    lines.append("PVGIS endpoint: hourly time series (via pvlib.get_pvgis_hourly)")
    lines.append("")
    lines.append("Requested parameters:")
    for k, v in params.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append(f"Cache/source used by pipeline: {pvgis_source}")
    lines.append(f"{data_range_line}")
    lines.append("")
    lines.append("Repro steps (Python):")
    lines.append("1) pip install pvlib pandas")
    lines.append("2) from pvlib.iotools import get_pvgis_hourly")
    lines.append("3) call get_pvgis_hourly(...) with the parameters above and url=PVGIS base URL")

    prov_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote PVGIS provenance: %s", prov_path)
    return prov_path


# -----------------------------
# Post-processing helpers (toggles)
# -----------------------------
def load_core_hourly_energy(location_slug: str, logger) -> pd.DataFrame:
    """
    Load the hourly energy CSV produced by src/roi_calculator_core.py (top-level outputs/).
    :contentReference[oaicite:5]{index=5}
    """
    root = repo_root()
    path = root / "outputs" / f"hourly_energy_{location_slug}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing core hourly output: {path}")

    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"Hourly CSV missing 'timestamp' column: {path}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        bad = int(df["timestamp"].isna().sum())
        raise ValueError(f"Hourly CSV has {bad} unparseable timestamps: {path}")

    df = df.set_index("timestamp").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Ensure energy cols exist
    missing = [c for c in ENERGY_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Hourly CSV missing energy columns: {missing}. File: {path}")

    # Numeric safety
    for c in ENERGY_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float).clip(lower=0.0)

    logger.info("Loaded core hourly energy: %s (rows=%s)", path, len(df))
    return df


def _parse_date_to_utc_midnight(date_str: str, label: str) -> pd.Timestamp:
    """
    Parse 'YYYY-MM-DD' into UTC midnight Timestamp.
    """
    try:
        ts = pd.Timestamp(date_str)
    except Exception:
        raise ValueError(f"{label} must be YYYY-MM-DD. Got: {date_str!r}")
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.floor("D")


def apply_analysis_window(full_hourly: pd.DataFrame, cfg: PVROIRunConfig, logger) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Returns windowed hourly dataframe + info dict.
    """
    mode = cfg.analysis_window.mode

    data_start = full_hourly.index.min()
    data_end = full_hourly.index.max()

    if mode == "full_year":
        info = {
            "mode": "full_year",
            "requested_start": None,
            "requested_end": None,
            "used_start_ts": data_start,
            "used_end_exclusive_ts": data_end + pd.Timedelta(seconds=1),
        }
        return full_hourly.copy(), info

    if mode != "custom":
        raise ValueError(f"analysis_window.mode must be 'full_year' or 'custom'. Got: {mode}")

    start_req = _parse_date_to_utc_midnight(cfg.analysis_window.start, "analysis_window.start")
    end_req = _parse_date_to_utc_midnight(cfg.analysis_window.end, "analysis_window.end")

    if end_req < start_req:
        raise ValueError("analysis_window.end must be >= analysis_window.start")

    end_excl_req = end_req + pd.Timedelta(days=1)

    # Clamp to available data range (friendly behaviour)
    used_start = max(start_req, data_start)
    used_end_excl = min(end_excl_req, data_end + pd.Timedelta(seconds=1))

    window = full_hourly.loc[(full_hourly.index >= used_start) & (full_hourly.index < used_end_excl)].copy()
    if window.empty:
        raise RuntimeError(
            "No data exists in the selected analysis_window.\n"
            f"Requested: {cfg.analysis_window.start} to {cfg.analysis_window.end}\n"
            f"Data range: {data_start} to {data_end}\n"
            "Fix: choose a window inside the data year."
        )

    info = {
        "mode": "custom",
        "requested_start": cfg.analysis_window.start,
        "requested_end": cfg.analysis_window.end,
        "used_start_ts": used_start,
        "used_end_exclusive_ts": used_end_excl,
        "clamped": (used_start != start_req) or (used_end_excl != end_excl_req),
    }
    logger.info("Analysis window applied. Mode=custom, rows=%s", len(window))
    return window, info


def export_hourly_csv(hourly_df: pd.DataFrame, out_path: Path) -> None:
    out = hourly_df[ENERGY_COLS].copy()
    out.insert(0, "timestamp", out.index)
    out.to_csv(out_path, index=False)


def export_daily_csv(hourly_df: pd.DataFrame, out_path: Path) -> None:
    daily = hourly_df[ENERGY_COLS].resample("D").sum()
    out = daily.copy()
    out.insert(0, "date", out.index.strftime("%Y-%m-%d"))
    out.to_csv(out_path, index=False)


def export_monthly_csv(hourly_df: pd.DataFrame, out_path: Path) -> pd.DataFrame:
    monthly = hourly_df[ENERGY_COLS].resample("MS").sum()
    out = monthly.copy()
    out.insert(0, "month", out.index.strftime("%Y-%m"))
    out = out.reset_index(drop=True)
    out.to_csv(out_path, index=False)
    return out


def export_monthly_financial_csv(hourly_df: pd.DataFrame, cfg: PVROIRunConfig, out_path: Path) -> pd.DataFrame:
    base = hourly_df[["load_kwh", "grid_import_kwh", "exported_kwh"]].copy()

    month_idx = base.index.to_period("M").astype(str)
    out = pd.DataFrame({"month": month_idx})
    out["load_kwh"] = base["load_kwh"].values
    out["grid_import_kwh"] = base["grid_import_kwh"].values
    out["exported_kwh"] = base["exported_kwh"].values
    out = out.groupby("month", as_index=False).sum(numeric_only=True)

    # Tariff A monthly bill components
    out["baseline_bill_tariffA_gbp"] = out["load_kwh"] * float(cfg.tariffs.tariffA_import)
    out["bill_with_pv_tariffA_gbp"] = (
        out["grid_import_kwh"] * float(cfg.tariffs.tariffA_import)
        - out["exported_kwh"] * float(cfg.tariffs.tariffA_export)
    )
    out["savings_tariffA_gbp"] = out["baseline_bill_tariffA_gbp"] - out["bill_with_pv_tariffA_gbp"]

    # Tariff B monthly bill components (TOU import + flat export)
    peak_mask = _peak_mask(base.index, int(cfg.tariffs.peak_start), int(cfg.tariffs.peak_end))
    load_peak = np.where(peak_mask, base["load_kwh"].values, 0.0)
    load_off = np.where(~peak_mask, base["load_kwh"].values, 0.0)
    import_peak = np.where(peak_mask, base["grid_import_kwh"].values, 0.0)
    import_off = np.where(~peak_mask, base["grid_import_kwh"].values, 0.0)

    tou = pd.DataFrame(
        {
            "month": month_idx,
            "load_peak_kwh": load_peak,
            "load_offpeak_kwh": load_off,
            "import_peak_kwh": import_peak,
            "import_offpeak_kwh": import_off,
        }
    ).groupby("month", as_index=False).sum(numeric_only=True)

    out = out.merge(tou, on="month", how="left")
    out["baseline_bill_tariffB_gbp"] = (
        out["load_peak_kwh"] * float(cfg.tariffs.tariffB_peak)
        + out["load_offpeak_kwh"] * float(cfg.tariffs.tariffB_offpeak)
    )
    out["bill_with_pv_tariffB_gbp"] = (
        out["import_peak_kwh"] * float(cfg.tariffs.tariffB_peak)
        + out["import_offpeak_kwh"] * float(cfg.tariffs.tariffB_offpeak)
        - out["exported_kwh"] * float(cfg.tariffs.tariffB_export)
    )
    out["savings_tariffB_gbp"] = out["baseline_bill_tariffB_gbp"] - out["bill_with_pv_tariffB_gbp"]

    # Tariff C monthly bill components (flat import as Tariff A + Tariff C export)
    out["baseline_bill_tariffC_gbp"] = out["load_kwh"] * float(cfg.tariffs.tariffA_import)
    out["bill_with_pv_tariffC_gbp"] = (
        out["grid_import_kwh"] * float(cfg.tariffs.tariffA_import)
        - out["exported_kwh"] * float(cfg.tariffs.tariffC_export)
    )
    out["savings_tariffC_gbp"] = out["baseline_bill_tariffC_gbp"] - out["bill_with_pv_tariffC_gbp"]

    # Convenience selected-tariff columns for quick plotting/reporting
    if cfg.tariff_mode == "A":
        out["baseline_bill_gbp"] = out["baseline_bill_tariffA_gbp"]
        out["bill_with_pv_gbp"] = out["bill_with_pv_tariffA_gbp"]
        out["savings_gbp"] = out["savings_tariffA_gbp"]
    elif cfg.tariff_mode == "B":
        out["baseline_bill_gbp"] = out["baseline_bill_tariffB_gbp"]
        out["bill_with_pv_gbp"] = out["bill_with_pv_tariffB_gbp"]
        out["savings_gbp"] = out["savings_tariffB_gbp"]
    elif cfg.tariff_mode == "C":
        out["baseline_bill_gbp"] = out["baseline_bill_tariffC_gbp"]
        out["bill_with_pv_gbp"] = out["bill_with_pv_tariffC_gbp"]
        out["savings_gbp"] = out["savings_tariffC_gbp"]
    else:
        out["baseline_bill_gbp"] = np.nan
        out["bill_with_pv_gbp"] = np.nan
        out["savings_gbp"] = np.nan

    out.to_csv(out_path, index=False)
    return out


def _compute_dt_hours(index_utc: pd.DatetimeIndex) -> np.ndarray:
    dt = index_utc.to_series().diff().dt.total_seconds().div(3600.0)
    positive = dt[(dt > 0) & np.isfinite(dt)]
    median = float(positive.median()) if not positive.empty else 1.0
    dt = dt.fillna(median)
    dt = dt.where(dt > 0, median)
    return dt.values.astype(float)


def _add_plot_disclaimer(data_year: int, window_label: str) -> str:
    msg = f"Based on PVGIS {int(data_year)} data. Values are estimates, not guaranteed."
    if window_label:
        msg += f" | Window: {window_label}"
    return msg


def plot_monthly_pv_vs_load(
    monthly_df: pd.DataFrame,
    png_path: Path,
    location_slug: str,
    window_label: str,
    data_year: int,
) -> None:
    # Safety: if empty, make a clear plot instead of crashing
    if monthly_df is None or monthly_df.empty:
        plt.figure(figsize=(10, 4))
        plt.title(f"Monthly solar production vs household use — {location_slug} (no data)")
        plt.xlabel("Month (within year)")
        plt.ylabel("Energy (kWh)")
        plt.tight_layout()
        plt.savefig(png_path, dpi=150)
        plt.close()
        return

    # If only one month is present, a line plot can look blank.
    one_point = len(monthly_df) == 1

    plt.figure(figsize=(10, 4))

    if one_point:
        # Use bars for a single month (always visible)
        x = monthly_df["month"].astype(str).values
        plt.bar(x, monthly_df["pv_kwh"].values, label="Solar production (kWh)")
        plt.bar(x, monthly_df["load_kwh"].values, alpha=0.7, label="Household use (kWh)")
    else:
        # Use lines with markers for multi-month
        plt.plot(monthly_df["month"], monthly_df["pv_kwh"], marker="o", label="Solar production (kWh)")
        plt.plot(monthly_df["month"], monthly_df["load_kwh"], marker="o", label="Household use (kWh)")

    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Month")
    plt.ylabel("Energy (kWh)")

    title = f"Monthly solar production vs household use — {location_slug}"
    if window_label:
        title += f" — {window_label}"
    plt.title(title)

    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year, window_label), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()



def plot_energy_split(hourly_df: pd.DataFrame, png_path: Path, location_slug: str, window_label: str, data_year: int) -> None:
    monthly = hourly_df[["self_consumed_kwh", "exported_kwh"]].resample("MS").sum()
    monthly["month"] = monthly.index.strftime("%Y-%m")
    used = monthly["self_consumed_kwh"].values
    exported = monthly["exported_kwh"].values
    x = monthly["month"].astype(str).values

    plt.figure(figsize=(10, 4))
    plt.bar(x, used, label="Used in home (kWh)")
    plt.bar(x, exported, bottom=used, label="Exported to grid (kWh)")
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Month")
    plt.ylabel("Energy (kWh)")
    title = f"Monthly solar: used at home vs exported — {location_slug}"
    if window_label:
        title += f" — {window_label}"
    plt.title(title)
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year, window_label), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def plot_monthly_bill_benefit(
    monthly_fin_df: pd.DataFrame,
    png_path: Path,
    location_slug: str,
    window_label: str,
    tariff_mode: str,
    data_year: int,
) -> None:
    if monthly_fin_df is None or monthly_fin_df.empty:
        plt.figure(figsize=(10, 4))
        plt.title(f"Monthly bill savings (estimate) — {location_slug} (no data)")
        plt.xlabel("Month (within year)")
        plt.ylabel("Bill savings and earnings (£/month)")
        plt.tight_layout()
        plt.savefig(png_path, dpi=150)
        plt.close()
        return

    plt.figure(figsize=(10, 4))

    if tariff_mode == "compare":
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffA_gbp"], marker="o", label="Bill savings and earnings: Tariff A (£)")
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffB_gbp"], marker="o", label="Bill savings and earnings: Tariff B (£)")
    elif tariff_mode == "compare_all":
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffA_gbp"], marker="o", label="Bill savings and earnings: Tariff A (£)")
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffB_gbp"], marker="o", label="Bill savings and earnings: Tariff B (£)")
        if "savings_tariffC_gbp" in monthly_fin_df.columns:
            plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffC_gbp"], marker="o", label="Bill savings and earnings: Tariff C (£)")
    elif tariff_mode == "A":
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffA_gbp"], marker="o", label="Bill savings and earnings: Tariff A (£)")
    elif tariff_mode == "B":
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffB_gbp"], marker="o", label="Bill savings and earnings: Tariff B (£)")
    elif tariff_mode == "C":
        if "savings_tariffC_gbp" in monthly_fin_df.columns:
            plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffC_gbp"], marker="o", label="Bill savings and earnings: Tariff C (£)")
    else:
        plt.plot(monthly_fin_df["month"], monthly_fin_df["savings_tariffB_gbp"], marker="o", label="Bill savings and earnings: Tariff B (£)")

    plt.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Month")
    plt.ylabel("Bill savings and earnings (£/month)")
    title = f"Monthly bill savings (estimate) — {location_slug}"
    if window_label:
        title += f" — {window_label}"
    plt.title(title)
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year, window_label), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def pick_default_week_start(index_utc: pd.DatetimeIndex) -> pd.Timestamp:
    year = int(index_utc.min().year)
    candidate = pd.Timestamp(f"{year}-06-01", tz="UTC")
    if candidate < index_utc.min() or candidate > index_utc.max():
        return index_utc.min().floor("D")
    return candidate


def plot_week_timeseries(
    hourly_df: pd.DataFrame,
    png_path: Path,
    location_slug: str,
    week_start: pd.Timestamp,
    week_days: int,
    window_label: str,
    data_year: int,
) -> None:
    start = week_start
    end = start + pd.Timedelta(days=int(week_days))

    window = hourly_df.loc[(hourly_df.index >= start) & (hourly_df.index < end)].copy()

    if window.empty:
        # fallback: first week of available data
        start = hourly_df.index.min().floor("D")
        end = start + pd.Timedelta(days=int(week_days))
        window = hourly_df.loc[(hourly_df.index >= start) & (hourly_df.index < end)].copy()

    if window.empty:
        raise RuntimeError("Week timeseries plot failed because there is no data to plot.")

    dt_hours = _compute_dt_hours(window.index)
    pv_kw = window["pv_kwh"].values / dt_hours
    load_kw = window["load_kwh"].values / dt_hours
    exported_kw = window["exported_kwh"].values / dt_hours

    plt.figure(figsize=(12, 4))
    plt.plot(window.index, pv_kw, label="Solar power (kW)")
    plt.plot(window.index, load_kw, label="Household use power (kW)")
    plt.plot(window.index, exported_kw, label="Energy sent to grid power (kW)")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Power (kW) (approx from kWh/timestep)")
    title = f"One-week household and solar power profile — {location_slug} — start {start.date()}"
    if window_label:
        title += f" — {window_label}"
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year, window_label), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def load_financial_summary(location_slug: str) -> pd.DataFrame:
    """
    Load finance summary produced by roi_calculator_finance.py.
    :contentReference[oaicite:6]{index=6}
    """
    root = repo_root()
    path = root / "outputs" / f"financial_summary_{location_slug}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing finance output: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Finance summary CSV is empty: {path}")
    return df


def build_run_financial_summary(fin_df: pd.DataFrame, cfg: PVROIRunConfig) -> pd.DataFrame:
    """
    Apply tariff_mode to decide what goes into runs/.../outputs/financial_summary.csv

    - compare / compare_all: keep multi-tariff columns
    - A: keep/rename A columns to generic names
    - B: keep/rename B columns to generic names
    - C: keep/rename C columns to generic names
    """
    mode = cfg.tariff_mode
    row = fin_df.iloc[[0]].copy()

    # Always include these for context
    base_cols = ["location", "system_kw", "annual_load_kwh", "profile", "salvage_value_gbp"]
    base_cols = [c for c in base_cols if c in row.columns]

    if mode == "compare":
        out = row.copy()
        out["tariff_mode"] = "compare"
        out["peak_start_utc"] = int(cfg.tariffs.peak_start)
        out["peak_end_utc"] = int(cfg.tariffs.peak_end)
        return out

    if mode == "compare_all":
        out = row.copy()
        out["tariff_mode"] = "compare_all"
        out["peak_start_utc"] = int(cfg.tariffs.peak_start)
        out["peak_end_utc"] = int(cfg.tariffs.peak_end)
        return out

    if mode == "A":
        keep = base_cols + [
            "tariffA_import", "tariffA_export",
            "annual_pv_kwh", "annual_self_consumed_kwh", "annual_exported_kwh",
            "annual_savings_tariffA_gbp", "payback_year_tariffA", "npv_tariffA", "roi_tariffA"
        ]
        keep = [c for c in keep if c in row.columns]
        out = row[keep].copy()
        out = out.rename(columns={
            "annual_savings_tariffA_gbp": "annual_savings_gbp",
            "payback_year_tariffA": "payback_year",
            "npv_tariffA": "npv",
            "roi_tariffA": "roi",
        })
        out["tariff_mode"] = "A"
        return out

    if mode == "B":
        keep = base_cols + [
            "tariffB_peak", "tariffB_offpeak", "tariffB_export",
            "annual_pv_kwh", "annual_self_consumed_kwh", "annual_exported_kwh",
            "annual_savings_tariffB_gbp", "payback_year_tariffB", "npv_tariffB", "roi_tariffB"
        ]
        keep = [c for c in keep if c in row.columns]
        out = row[keep].copy()
        out = out.rename(columns={
            "annual_savings_tariffB_gbp": "annual_savings_gbp",
            "payback_year_tariffB": "payback_year",
            "npv_tariffB": "npv",
            "roi_tariffB": "roi",
        })
        out["tariff_mode"] = "B"
        out["peak_start_utc"] = int(cfg.tariffs.peak_start)
        out["peak_end_utc"] = int(cfg.tariffs.peak_end)
        return out

    if mode == "C":
        keep = base_cols + [
            "tariffA_import", "tariffC_export",
            "annual_pv_kwh", "annual_self_consumed_kwh", "annual_exported_kwh",
            "annual_savings_tariffC_gbp", "payback_year_tariffC", "npv_tariffC", "roi_tariffC"
        ]
        keep = [c for c in keep if c in row.columns]
        out = row[keep].copy()
        out = out.rename(columns={
            "annual_savings_tariffC_gbp": "annual_savings_gbp",
            "payback_year_tariffC": "payback_year",
            "npv_tariffC": "npv",
            "roi_tariffC": "roi",
        })
        out["tariff_mode"] = "C"
        return out

    # Defensive
    raise ValueError(f"Unknown tariff_mode: {mode}")


def _peak_mask(index_utc: pd.DatetimeIndex, peak_start: int, peak_end: int) -> np.ndarray:
    hours = index_utc.hour.values.astype(int)
    if peak_start < peak_end:
        return (hours >= peak_start) & (hours < peak_end)
    return (hours >= peak_start) | (hours < peak_end)


def tariff_a_bill(load_kwh: float, grid_import_kwh: float, exported_kwh: float, import_price: float, export_price: float) -> Dict[str, float]:
    baseline = load_kwh * import_price
    with_pv = grid_import_kwh * import_price - exported_kwh * export_price
    savings = baseline - with_pv
    return {"baseline_gbp": float(baseline), "bill_with_pv_gbp": float(with_pv), "savings_gbp": float(savings)}


def tariff_b_bill(
    load_series: np.ndarray,
    import_series: np.ndarray,
    export_series: np.ndarray,
    peak_mask: np.ndarray,
    peak_price: float,
    offpeak_price: float,
    export_price: float,
) -> Dict[str, float]:
    baseline = float(np.sum(load_series[peak_mask])) * peak_price + float(np.sum(load_series[~peak_mask])) * offpeak_price
    with_pv = float(np.sum(import_series[peak_mask])) * peak_price + float(np.sum(import_series[~peak_mask])) * offpeak_price - float(np.sum(export_series)) * export_price
    savings = baseline - with_pv
    return {"baseline_gbp": float(baseline), "bill_with_pv_gbp": float(with_pv), "savings_gbp": float(savings)}


def write_summary_md(
    cfg: PVROIRunConfig,
    run_dir: Path,
    pvgis_source: str,
    outputs_written: Dict[str, Path],
    plots_written: Dict[str, Path],
    full_hourly: pd.DataFrame,
    window_hourly: pd.DataFrame,
    window_info: Dict[str, Any],
    fin_out_df: pd.DataFrame,
    logger,
) -> Path:
    """
    Write runs/<run_id>/summary.md (and report/summary.md for compatibility) with:
      - analysis_window used
      - exports enabled
      - plots generated
      - tariff_mode used
      - key metrics (full-year baseline + selected window)
    """
    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.md"
    legacy_summary_path = report_dir / "summary.md"

    def rel(p: Path) -> str:
        return str(p.relative_to(run_dir))

    def money(x: float) -> str:
        return f"£{x:,.2f}"

    def pct(x: float) -> str:
        return f"{100.0 * x:.1f}%"

    # Full-year totals (baseline; also what finance uses)
    full_tot = {c: float(full_hourly[c].sum()) for c in ENERGY_COLS}
    full_self_pct = (full_tot["self_consumed_kwh"] / full_tot["pv_kwh"]) if full_tot["pv_kwh"] > 0 else 0.0
    full_suff_pct = (full_tot["self_consumed_kwh"] / full_tot["load_kwh"]) if full_tot["load_kwh"] > 0 else 0.0

    # Window totals (what we export + plot)
    win_tot = {c: float(window_hourly[c].sum()) for c in ENERGY_COLS}
    win_self_pct = (win_tot["self_consumed_kwh"] / win_tot["pv_kwh"]) if win_tot["pv_kwh"] > 0 else 0.0
    win_suff_pct = (win_tot["self_consumed_kwh"] / win_tot["load_kwh"]) if win_tot["load_kwh"] > 0 else 0.0

    # Window label
    if window_info["mode"] == "custom":
        used_start = window_info["used_start_ts"].date()
        used_end_incl = (window_info["used_end_exclusive_ts"] - pd.Timedelta(seconds=1)).date()
        window_label = f"{used_start} to {used_end_incl}"
    else:
        window_label = "Full year"

    # Period savings for the selected window
    a_period = tariff_a_bill(
        load_kwh=win_tot["load_kwh"],
        grid_import_kwh=win_tot["grid_import_kwh"],
        exported_kwh=win_tot["exported_kwh"],
        import_price=float(cfg.tariffs.tariffA_import),
        export_price=float(cfg.tariffs.tariffA_export),
    )

    peak_mask = _peak_mask(window_hourly.index, int(cfg.tariffs.peak_start), int(cfg.tariffs.peak_end))
    b_period = tariff_b_bill(
        load_series=window_hourly["load_kwh"].values,
        import_series=window_hourly["grid_import_kwh"].values,
        export_series=window_hourly["exported_kwh"].values,
        peak_mask=peak_mask,
        peak_price=float(cfg.tariffs.tariffB_peak),
        offpeak_price=float(cfg.tariffs.tariffB_offpeak),
        export_price=float(cfg.tariffs.tariffB_export),
    )

    # Exports enabled flags
    exp_hourly = bool(cfg.outputs.export_hourly)
    exp_daily = bool(cfg.outputs.export_daily)
    exp_monthly = bool(cfg.outputs.export_monthly)

    # Plot flags + actual
    plot_flag_map = {
        "monthly_pv_vs_load": bool(cfg.plot_flags.monthly_pv_vs_load),
        "week_timeseries": bool(cfg.plot_flags.week_timeseries),
        "energy_split": bool(cfg.plot_flags.energy_split),
        "cumulative_cashflow": bool(cfg.plot_flags.cumulative_cashflow),
        "annual_cashflow_bars": bool(cfg.plot_flags.annual_cashflow_bars),
    }

    lines = []
    lines.append("# PV ROI Demo Summary\n")
    lines.append(f"- **Run ID:** `{cfg.meta.run_id}`")
    lines.append(f"- **Created (local):** `{cfg.meta.created_at_local}`")
    lines.append(f"- **PVGIS source:** `{pvgis_source}`")
    lines.append(f"- **Tariff mode:** `{cfg.tariff_mode}`\n")

    lines.append("## Analysis window (controls plots + exported CSVs)\n")
    lines.append(f"- **Mode:** `{window_info['mode']}`")
    if window_info["mode"] == "custom":
        lines.append(f"- **Requested:** `{window_info['requested_start']}` to `{window_info['requested_end']}` (inclusive)")
        used_start = window_info["used_start_ts"].date()
        used_end_incl = (window_info["used_end_exclusive_ts"] - pd.Timedelta(seconds=1)).date()
        lines.append(f"- **Used (after clamping):** `{used_start}` to `{used_end_incl}` (inclusive)")
        if window_info.get("clamped"):
            lines.append("- **Note:** Requested dates were partially outside the data range, so the window was clamped.")
    else:
        lines.append("- Full dataset used for exports + plots.")
    lines.append("")
    lines.append("> **Important:** Lifetime ROI / Net Present Value (NPV) / payback are still computed on the full dataset (baseline).")
    lines.append("")

    lines.append("## Exports enabled\n")
    lines.append(f"- Hourly export (`outputs/hourly.csv`): {'YES' if exp_hourly else 'NO'}")
    lines.append(f"- Daily export (`outputs/daily.csv`): {'YES' if exp_daily else 'NO'}")
    lines.append(f"- Monthly export (`outputs/monthly.csv`): {'YES' if exp_monthly else 'NO'}")
    lines.append("- Monthly financial export (`outputs/financial_monthly.csv`): YES\n")

    lines.append("## Plots\n")
    for k, enabled in plot_flag_map.items():
        created = k in plots_written
        lines.append(f"- {k}: {'generated' if created else ('skipped (disabled)' if not enabled else 'skipped (not available)')}")
    lines.append("")

    lines.append("## Key results (FULL dataset baseline — used for finance)\n")
    lines.append(f"- PV generation: {full_tot['pv_kwh']:,.1f} kWh")
    lines.append(f"- Load: {full_tot['load_kwh']:,.1f} kWh")
    lines.append(f"- Self-consumed PV: {full_tot['self_consumed_kwh']:,.1f} kWh ({full_self_pct*100:.1f}% of PV)")
    lines.append(f"- Energy sent to grid: {full_tot['exported_kwh']:,.1f} kWh")
    lines.append(f"- Energy bought from grid: {full_tot['grid_import_kwh']:,.1f} kWh")
    lines.append(f"- Self-sufficiency: {full_suff_pct*100:.1f}% of load met by PV\n")

    lines.append("## Finance summary (from finance model)\n")
    # fin_out_df is already filtered/renamed depending on tariff_mode
    fin = fin_out_df.iloc[0].to_dict()

    if cfg.tariff_mode == "compare":
        lines.append(f"- Annual savings (Tariff A): {money(float(fin.get('annual_savings_tariffA_gbp', float('nan'))))}")
        lines.append(f"- Annual savings (Tariff B): {money(float(fin.get('annual_savings_tariffB_gbp', float('nan'))))}")
        lines.append(f"- Payback (Tariff A): {fin.get('payback_year_tariffA')}")
        lines.append(f"- Payback (Tariff B): {fin.get('payback_year_tariffB')}")
        lines.append(f"- Net Present Value (NPV) (Tariff A): {money(float(fin.get('npv_tariffA', float('nan'))))}")
        lines.append(f"- Net Present Value (NPV) (Tariff B): {money(float(fin.get('npv_tariffB', float('nan'))))}")
        try:
            lines.append(f"- ROI (Tariff A): {pct(float(fin.get('roi_tariffA')))}")
            lines.append(f"- ROI (Tariff B): {pct(float(fin.get('roi_tariffB')))}")
        except Exception:
            pass
    else:
        # A or B (we renamed columns to generic names)
        if "annual_savings_gbp" in fin:
            lines.append(f"- Annual savings: {money(float(fin['annual_savings_gbp']))}")
        lines.append(f"- Payback: {fin.get('payback_year')}")
        if "npv" in fin:
            lines.append(f"- Net Present Value (NPV): {money(float(fin['npv']))}")
        if "roi" in fin:
            try:
                lines.append(f"- ROI: {pct(float(fin['roi']))}")
            except Exception:
                pass

        if cfg.tariff_mode in {"B"}:
            lines.append(f"- Peak window (UTC): {cfg.tariffs.peak_start:02d}:00–{cfg.tariffs.peak_end:02d}:00 (end exclusive)")

        lines.append("")
        lines.append("> Note: Finance comparison plots are only available in `tariff_mode = compare`.")

    lines.append("\n## Period results (analysis window)\n")
    lines.append(f"- Window: **{window_label}**")
    lines.append(f"- PV generation: {win_tot['pv_kwh']:,.1f} kWh")
    lines.append(f"- Load: {win_tot['load_kwh']:,.1f} kWh")
    lines.append(f"- Self-consumed PV: {win_tot['self_consumed_kwh']:,.1f} kWh ({win_self_pct*100:.1f}% of PV)")
    lines.append(f"- Energy sent to grid: {win_tot['exported_kwh']:,.1f} kWh")
    lines.append(f"- Energy bought from grid: {win_tot['grid_import_kwh']:,.1f} kWh")
    lines.append(f"- Self-sufficiency: {win_suff_pct*100:.1f}% of load met by PV\n")

    if cfg.tariff_mode == "A":
        lines.append("### Period bill (Tariff A)\n")
        lines.append(f"- Baseline (no PV): {money(a_period['baseline_gbp'])}")
        lines.append(f"- With PV: {money(a_period['bill_with_pv_gbp'])}")
        lines.append(f"- Savings: {money(a_period['savings_gbp'])}\n")
    elif cfg.tariff_mode == "B":
        lines.append("### Period bill (Tariff B)\n")
        lines.append(f"- Baseline (no PV): {money(b_period['baseline_gbp'])}")
        lines.append(f"- With PV: {money(b_period['bill_with_pv_gbp'])}")
        lines.append(f"- Savings: {money(b_period['savings_gbp'])}\n")
    else:
        lines.append("### Period bill (Tariff A vs B)\n")
        lines.append(f"- Savings (Tariff A): {money(a_period['savings_gbp'])}")
        lines.append(f"- Savings (Tariff B): {money(b_period['savings_gbp'])}\n")

    lines.append("## Confidence checks (Step 3 substitutes)\n")
    ver_path = run_dir / "outputs" / "verification_checks.csv"
    if ver_path.exists():
        try:
            ver_df = pd.read_csv(ver_path)
            pass_n = int((ver_df.get("status") == "PASS").sum())
            fail_n = int((ver_df.get("status") == "FAIL").sum())
            lines.append(f"- Verification checks: PASS={pass_n}, FAIL={fail_n}")
        except Exception:
            lines.append("- Verification checks: available (could not parse counts).")
    else:
        lines.append("- Verification checks: not generated.")

    cross_summary = run_dir / "outputs" / "pvgis_crosscheck_summary.csv"
    if cross_summary.exists():
        try:
            cdf = pd.read_csv(cross_summary)
            if not cdf.empty:
                crow = cdf.iloc[0].to_dict()
                lines.append(f"- PVGIS cross-check annual_pct_error: {crow.get('annual_pct_error')}")
                lines.append(f"- PVGIS cross-check monthly_mape_pct: {crow.get('monthly_mape_pct')}")
        except Exception:
            lines.append("- PVGIS cross-check summary: available (could not parse).")
    elif (run_dir / "outputs" / "pvgis_crosscheck_status.txt").exists():
        lines.append("- PVGIS cross-check: attempted but failed (see outputs/pvgis_crosscheck_status.txt).")
    else:
        lines.append("- PVGIS cross-check: not enabled.")

    var_summary = run_dir / "outputs" / "variability_summary.csv"
    if var_summary.exists():
        try:
            vdf = pd.read_csv(var_summary)
            if not vdf.empty and {"metric", "p10", "p50", "p90"}.issubset(vdf.columns):
                metric_candidates = [
                    "annual_savings_gbp",
                    "annual_savings_tariffA_gbp",
                    "annual_savings_tariffB_gbp",
                    "annual_savings_tariffC_gbp",
                ]
                row = None
                for m in metric_candidates:
                    sub = vdf[vdf["metric"] == m]
                    if not sub.empty:
                        row = sub.iloc[0]
                        break
                if row is not None:
                    lines.append(
                        f"- Variability annual savings P10/P50/P90: {row.get('p10')}, {row.get('p50')}, {row.get('p90')}"
                    )
        except Exception:
            lines.append("- Variability summary: available (could not parse).")
    elif (run_dir / "outputs" / "variability_status.txt").exists():
        lines.append("- Variability run: attempted but failed (see outputs/variability_status.txt).")
    else:
        lines.append("- Variability run: not enabled.")
    lines.append("")

    lines.append("## Output files in this run folder\n")
    lines.append("- Data:")
    lines.append("  - `data/raw_pvgis.csv`")
    lines.append("- Outputs:")
    for key, path in outputs_written.items():
        lines.append(f"  - `{rel(path)}`")
    lines.append("- Plots:")
    for key, path in plots_written.items():
        lines.append(f"  - `{rel(path)}`")
    lines.append("- Logs:")
    lines.append("  - `logs.txt`")

    text = "\n".join(lines) + "\n"
    summary_path.write_text(text, encoding="utf-8")
    legacy_summary_path.write_text(text, encoding="utf-8")
    logger.info("Wrote summary: %s", summary_path)
    return summary_path


def safe_copy_if_exists(src: Path, dst: Path, logger) -> bool:
    if not src.exists():
        logger.warning("Skip copy (missing): %s", src)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("Copied: %s -> %s", src, dst)
    return True


def _build_core_cmd(cfg: PVROIRunConfig, location_slug: str) -> list[str]:
    cmd = [
        sys.executable, "src/roi_calculator_core.py",
        "--location", location_slug,
        "--system-kw", str(cfg.pv.system_kw),
        "--annual-load-kwh", str(cfg.load.annual_load_kwh),
        "--profile", str(cfg.load.profile),
        "--seasonal-variance-pct", str(cfg.load.seasonal_variance_pct),
        "--import-tariff", str(cfg.tariffs.tariffA_import),
        "--export-tariff", str(cfg.tariffs.tariffA_export),
        "--temp-coeff", str(cfg.pv.temp_coeff),
        "--loss-frac", str(cfg.pv.loss_frac),
        "--inverter-eff", str(cfg.pv.inverter_eff),
        "--noct", str(cfg.pv.noct),
        "--week-days", str(cfg.load.week_days),
    ]
    if cfg.pv.inverter_ac_kw is not None:
        cmd += ["--inverter-ac-kw", str(cfg.pv.inverter_ac_kw)]
    if cfg.load.week_start is not None:
        cmd += ["--week-start", str(cfg.load.week_start)]
    return cmd


def _build_fin_cmd(cfg: PVROIRunConfig, location_slug: str) -> list[str]:
    return [
        sys.executable, "src/roi_calculator_finance.py",
        "--location", location_slug,
        "--system-kw", str(cfg.pv.system_kw),
        "--annual-load-kwh", str(cfg.load.annual_load_kwh),
        "--profile", str(cfg.load.profile),

        "--capex", str(cfg.finance.capex),
        "--discount-rate", str(cfg.finance.discount_rate),
        "--lifetime", str(cfg.finance.lifetime_years),
        "--degradation", str(cfg.finance.degradation),
        "--om-frac", str(cfg.finance.om_frac),
        "--salvage-value-gbp", str(cfg.finance.salvage_value_gbp),

        "--tariffA-import", str(cfg.tariffs.tariffA_import),
        "--tariffA-export", str(cfg.tariffs.tariffA_export),

        "--tariffB-peak", str(cfg.tariffs.tariffB_peak),
        "--tariffB-offpeak", str(cfg.tariffs.tariffB_offpeak),
        "--tariffB-export", str(cfg.tariffs.tariffB_export),
        "--tariffC-export", str(cfg.tariffs.tariffC_export),

        "--peak-start", str(cfg.tariffs.peak_start),
        "--peak-end", str(cfg.tariffs.peak_end),
    ]


def _selected_variability_tariff_mode(mode: str) -> str:
    if mode in {"A", "B", "C"}:
        return mode
    return "A"


def _extract_variability_row(fin_row: Dict[str, Any], mode: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["annual_pv_kwh"] = float(fin_row.get("annual_pv_kwh", float("nan")))

    if mode in {"A", "B", "C"}:
        out["annual_savings_gbp"] = float(fin_row.get("annual_savings_gbp", float("nan")))
        out["npv_gbp"] = float(fin_row.get("npv", float("nan")))
        out["payback_years"] = float(fin_row.get("payback_year", float("nan")))
        return out

    out["annual_savings_tariffA_gbp"] = float(fin_row.get("annual_savings_tariffA_gbp", float("nan")))
    out["npv_tariffA_gbp"] = float(fin_row.get("npv_tariffA", float("nan")))
    out["payback_tariffA_years"] = float(fin_row.get("payback_year_tariffA", float("nan")))
    out["annual_savings_tariffB_gbp"] = float(fin_row.get("annual_savings_tariffB_gbp", float("nan")))
    out["npv_tariffB_gbp"] = float(fin_row.get("npv_tariffB", float("nan")))
    out["payback_tariffB_years"] = float(fin_row.get("payback_year_tariffB", float("nan")))
    if mode == "compare_all" or "annual_savings_tariffC_gbp" in fin_row:
        out["annual_savings_tariffC_gbp"] = float(fin_row.get("annual_savings_tariffC_gbp", float("nan")))
        out["npv_tariffC_gbp"] = float(fin_row.get("npv_tariffC", float("nan")))
        out["payback_tariffC_years"] = float(fin_row.get("payback_year_tariffC", float("nan")))
    return out


def _plot_variability_savings(df: pd.DataFrame, out_png: Path) -> None:
    plt.figure(figsize=(9, 4))
    plt.plot(df["year"], df["annual_savings_gbp"], marker="o")
    plt.xlabel("Year")
    plt.ylabel("Annual savings (£)")
    plt.title("Historical variability: annual savings vs year")
    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()


def _safe_float_slug(x: float) -> str:
    return float_to_slug(float(x))


def _find_first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the expected columns exist: {candidates}")


def _run_pvgis_crosscheck(
    cfg: PVROIRunConfig,
    run_dir: Path,
    full_hourly: pd.DataFrame,
    location_slug: str,
    logger,
) -> Dict[str, Path]:
    out_dir = run_dir / "outputs"
    plots_dir = out_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, Path] = {}

    cache_dir = repo_root() / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = (
        f"pvgis_pvcalc_{location_slug}_{cfg.location.year}"
        f"_lat{_safe_float_slug(cfg.location.lat)}_lon{_safe_float_slug(cfg.location.lon)}"
        f"_tilt{_safe_float_slug(cfg.pv.surface_tilt_deg)}_az{_safe_float_slug(cfg.pv.surface_azimuth_deg)}"
        f"_kw{_safe_float_slug(cfg.pv.system_kw)}_loss{_safe_float_slug(100.0 * cfg.pv.loss_frac)}.csv"
    )
    cache_path = cache_dir / cache_name

    try:
        if cache_path.exists() and not cfg.location.force_download:
            pvcalc_df = load_cached_csv(cache_path)
        else:
            pvcalc_df, _ = fetch_pvgis_pvcalc_hourly(
                lat=float(cfg.location.lat),
                lon=float(cfg.location.lon),
                year=int(cfg.location.year),
                surface_tilt_deg=float(cfg.pv.surface_tilt_deg),
                surface_azimuth_deg=float(cfg.pv.surface_azimuth_deg),
                peakpower_kw=float(cfg.pv.system_kw),
                loss_percent=float(100.0 * cfg.pv.loss_frac),
            )
            save_csv(pvcalc_df, cache_path)

        power_col = _find_first_existing_column(pvcalc_df, ["P", "power", "pv_power", "P_pv"])
        power_vals = pd.to_numeric(pvcalc_df[power_col], errors="coerce").fillna(0.0)
        power_kw = power_vals / 1000.0 if float(power_vals.max()) > 100.0 else power_vals
        pvcalc_hourly = pd.DataFrame(index=pvcalc_df.index.copy())
        pvcalc_hourly["pvgis_pv_kwh"] = power_kw.astype(float)

        model_monthly = full_hourly["pv_kwh"].resample("MS").sum().rename("model_pv_kwh")
        pvgis_monthly = pvcalc_hourly["pvgis_pv_kwh"].resample("MS").sum()
        monthly = pd.concat([model_monthly, pvgis_monthly], axis=1).fillna(0.0)
        monthly["abs_error_kwh"] = (monthly["model_pv_kwh"] - monthly["pvgis_pv_kwh"]).abs()
        monthly["pct_error"] = np.where(
            monthly["pvgis_pv_kwh"] > 0,
            100.0 * (monthly["model_pv_kwh"] - monthly["pvgis_pv_kwh"]) / monthly["pvgis_pv_kwh"],
            np.nan,
        )

        monthly_out = monthly.copy()
        monthly_out.insert(0, "month", monthly_out.index.strftime("%Y-%m"))
        monthly_csv = out_dir / "pvgis_crosscheck_monthly.csv"
        monthly_out.to_csv(monthly_csv, index=False)
        written["pvgis_crosscheck_monthly.csv"] = monthly_csv

        annual_model = float(monthly["model_pv_kwh"].sum())
        annual_pvgis = float(monthly["pvgis_pv_kwh"].sum())
        annual_pct_error = (100.0 * (annual_model - annual_pvgis) / annual_pvgis) if annual_pvgis > 0 else np.nan
        mape = float(monthly.loc[monthly["pvgis_pv_kwh"] > 0, "pct_error"].abs().mean())
        summary = pd.DataFrame(
            [
                {
                    "annual_model_pv_kwh": annual_model,
                    "annual_pvgis_pv_kwh": annual_pvgis,
                    "annual_pct_error": annual_pct_error,
                    "monthly_mape_pct": mape,
                }
            ]
        )
        summary_csv = out_dir / "pvgis_crosscheck_summary.csv"
        summary.to_csv(summary_csv, index=False)
        written["pvgis_crosscheck_summary.csv"] = summary_csv

        plot_png = plots_dir / "pvgis_crosscheck_monthly.png"
        plt.figure(figsize=(10, 4))
        plt.plot(monthly_out["month"], monthly_out["model_pv_kwh"], marker="o", label="Model PV (kWh)")
        plt.plot(monthly_out["month"], monthly_out["pvgis_pv_kwh"], marker="o", label="PVGIS PVcalc (kWh)")
        plt.xlabel("Month")
        plt.ylabel("Monthly PV generation (kWh)")
        plt.title("PVGIS cross-check: monthly model PV vs PVGIS PVcalc")
        plt.xticks(rotation=45, ha="right")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plot_png, dpi=150)
        plt.close()
        written["pvgis_crosscheck_monthly.png"] = plot_png
    except Exception as e:
        logger.warning("PVGIS cross-check failed: %s", repr(e))
        status_path = out_dir / "pvgis_crosscheck_status.txt"
        status_path.write_text(str(e) + "\n", encoding="utf-8")
        written["pvgis_crosscheck_status.txt"] = status_path

    return written


# -----------------------------
# Main pipeline
# -----------------------------
def run_pipeline(cfg: PVROIRunConfig) -> Path:
    """
    Main entry point:
      run_pipeline(config) -> creates runs/<run_id>/... and returns run_dir
    """
    validate_config(cfg)

    # Create run folder + config.json + logs.txt
    config_dict = cfg.to_dict()
    run_dir, logger, resolved_config_dict = init_run(config_dict)

    # Update cfg meta from resolved config (so summary shows run_id)
    cfg = PVROIRunConfig.from_dict(resolved_config_dict)

    root = repo_root()
    logger.info("Repo root: %s", root)

    # 1) PVGIS data (cache-first, fallback on failure)
    _, pvgis_source = ensure_pvgis_data(cfg, run_dir, logger)

   
    # Provenance file for reproducibility (supervisor-friendly)
    write_pvgis_provenance(cfg, run_dir, pvgis_source, logger)


    # 2) Core step (produces outputs/hourly_energy_<location>.csv, etc.) :contentReference[oaicite:7]{index=7}
    location_slug = slugify(cfg.location.name)

    core_cmd = _build_core_cmd(cfg, location_slug)
    rc = run_subprocess(core_cmd, cwd=root, logger=logger)
    if rc != 0:
        raise RuntimeError(f"Core step failed. See logs: {run_dir / 'logs.txt'}")

    # 3) Finance step (produces outputs/financial_summary_<location>.csv, etc.) :contentReference[oaicite:8]{index=8}
    fin_cmd = _build_fin_cmd(cfg, location_slug)
    rc = run_subprocess(fin_cmd, cwd=root, logger=logger)
    if rc != 0:
        raise RuntimeError(f"Finance step failed. See logs: {run_dir / 'logs.txt'}")

    # 4) Load full hourly energy (baseline), apply analysis window for exports+plots
    full_hourly = load_core_hourly_energy(location_slug, logger)
    window_hourly, window_info = apply_analysis_window(full_hourly, cfg, logger)

    # 5) Write run-folder outputs (respect export toggles + standard names)
    out_dir = run_dir / "outputs"
    plots_dir = out_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    outputs_written: Dict[str, Path] = {}
    plots_written: Dict[str, Path] = {}

    if bool(cfg.outputs.enable_verification_checks):
        verification_df = compute_verification_checks(full_hourly, float(cfg.pv.system_kw))
        verification_csv = out_dir / "verification_checks.csv"
        write_verification_csv(verification_df, verification_csv)
        outputs_written["verification_checks.csv"] = verification_csv
        logger.info("Exported: %s", verification_csv)

    # Exports: deterministic canonical names (+ compatibility aliases)
    if cfg.outputs.export_hourly:
        p = out_dir / "hourly.csv"
        export_hourly_csv(window_hourly, p)
        outputs_written["hourly.csv"] = p
        logger.info("Exported: %s", p)
        legacy_p = out_dir / "hourly_energy.csv"
        safe_copy_if_exists(p, legacy_p, logger)
        outputs_written["hourly_energy.csv"] = legacy_p

    if cfg.outputs.export_daily:
        p = out_dir / "daily.csv"
        export_daily_csv(window_hourly, p)
        outputs_written["daily.csv"] = p
        logger.info("Exported: %s", p)
        legacy_p = out_dir / "daily_energy.csv"
        safe_copy_if_exists(p, legacy_p, logger)
        outputs_written["daily_energy.csv"] = legacy_p

    monthly_df_for_plot = None
    if cfg.outputs.export_monthly:
        p = out_dir / "monthly.csv"
        monthly_df_for_plot = export_monthly_csv(window_hourly, p)
        outputs_written["monthly.csv"] = p
        logger.info("Exported: %s", p)
        legacy_p = out_dir / "monthly_summary.csv"
        safe_copy_if_exists(p, legacy_p, logger)
        outputs_written["monthly_summary.csv"] = legacy_p
    else:
        # Still compute monthly if needed for plot
        monthly_tmp = window_hourly[ENERGY_COLS].resample("MS").sum()
        monthly_df_for_plot = monthly_tmp.copy()
        monthly_df_for_plot.insert(0, "month", monthly_df_for_plot.index.strftime("%Y-%m"))
        monthly_df_for_plot = monthly_df_for_plot.reset_index(drop=True)

    # Month-by-month financial summary (money seasonality)
    monthly_fin_path = out_dir / "financial_monthly.csv"
    monthly_fin_df = export_monthly_financial_csv(window_hourly, cfg, monthly_fin_path)
    outputs_written["financial_monthly.csv"] = monthly_fin_path
    logger.info("Exported: %s", monthly_fin_path)
    legacy_monthly_fin = out_dir / "monthly_fdinancial_summary.csv"
    safe_copy_if_exists(monthly_fin_path, legacy_monthly_fin, logger)
    outputs_written["monthly_fdinancial_summary.csv"] = legacy_monthly_fin

    # Finance summary: filter based on tariff_mode and write to run folder
    fin_df = load_financial_summary(location_slug)
    fin_out_df = build_run_financial_summary(fin_df, cfg)
    fin_path = out_dir / "financial_summary.csv"
    fin_out_df.to_csv(fin_path, index=False)
    outputs_written["financial_summary.csv"] = fin_path
    logger.info("Exported: %s", fin_path)

    # Window label for plot titles
    if window_info["mode"] == "custom":
        used_start = window_info["used_start_ts"].date()
        used_end_incl = (window_info["used_end_exclusive_ts"] - pd.Timedelta(seconds=1)).date()
        window_label = f"{used_start} to {used_end_incl}"
    else:
        window_label = ""
    data_year = int(cfg.location.year)

    # 6) Plots (respect plot_flags)
    if cfg.plot_flags.monthly_pv_vs_load:
        p = plots_dir / "monthly_pv_vs_load.png"
        plot_monthly_pv_vs_load(monthly_df_for_plot, p, location_slug, window_label, data_year)
        plots_written["monthly_pv_vs_load.png"] = p

    if cfg.plot_flags.energy_split:
        p = plots_dir / "energy_split.png"
        plot_energy_split(window_hourly, p, location_slug, window_label, data_year)
        plots_written["energy_split.png"] = p

    p = plots_dir / "monthly_bill_benefit.png"
    plot_monthly_bill_benefit(monthly_fin_df, p, location_slug, window_label, cfg.tariff_mode, data_year)
    plots_written["monthly_bill_benefit.png"] = p

    if cfg.plot_flags.week_timeseries:
        # Choose week start: config > analysis_window start (if custom) > default
        if cfg.load.week_start:
            week_start = _parse_date_to_utc_midnight(cfg.load.week_start, "load.week_start")
        elif window_info["mode"] == "custom":
            week_start = window_info["used_start_ts"].floor("D")
        else:
            week_start = pick_default_week_start(window_hourly.index)

        p = plots_dir / "week_timeseries.png"
        plot_week_timeseries(window_hourly, p, location_slug, week_start, cfg.load.week_days, window_label, data_year)
        plots_written["week_timeseries.png"] = p

    # Finance plots: map the best available finance plot into run outputs for every tariff mode.
    top_outputs = root / "outputs"
    if cfg.tariff_mode == "compare":
        if cfg.plot_flags.cumulative_cashflow:
            src = top_outputs / f"cumulative_cashflow_comparison_{location_slug}.png"
            dst = plots_dir / "cumulative_cashflow.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["cumulative_cashflow.png"] = dst

        if cfg.plot_flags.annual_cashflow_bars:
            src = top_outputs / f"annual_cashflow_bars_{location_slug}.png"
            dst = plots_dir / "annual_cashflow_bars.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["annual_cashflow_bars.png"] = dst
    elif cfg.tariff_mode == "compare_all":
        if cfg.plot_flags.cumulative_cashflow:
            src = top_outputs / f"cumulative_cashflow_comparison_all_{location_slug}.png"
            dst = plots_dir / "cumulative_cashflow.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["cumulative_cashflow.png"] = dst
        if cfg.plot_flags.annual_cashflow_bars:
            src = top_outputs / f"annual_cashflow_bars_{location_slug}.png"
            dst = plots_dir / "annual_cashflow_bars.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["annual_cashflow_bars.png"] = dst
    elif cfg.tariff_mode == "A":
        if cfg.plot_flags.cumulative_cashflow:
            src = top_outputs / f"cumulative_cashflow_tariffA_{location_slug}.png"
            dst = plots_dir / "cumulative_cashflow.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["cumulative_cashflow.png"] = dst
        if cfg.plot_flags.annual_cashflow_bars:
            src = top_outputs / f"annual_cashflow_bars_{location_slug}.png"
            dst = plots_dir / "annual_cashflow_bars.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["annual_cashflow_bars.png"] = dst
    elif cfg.tariff_mode == "B":
        if cfg.plot_flags.cumulative_cashflow:
            src = top_outputs / f"cumulative_cashflow_tariffB_{location_slug}.png"
            dst = plots_dir / "cumulative_cashflow.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["cumulative_cashflow.png"] = dst
        if cfg.plot_flags.annual_cashflow_bars:
            src = top_outputs / f"annual_cashflow_bars_{location_slug}.png"
            dst = plots_dir / "annual_cashflow_bars.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["annual_cashflow_bars.png"] = dst
    elif cfg.tariff_mode == "C":
        if cfg.plot_flags.cumulative_cashflow:
            src = top_outputs / f"cumulative_cashflow_tariffC_{location_slug}.png"
            dst = plots_dir / "cumulative_cashflow.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["cumulative_cashflow.png"] = dst
        if cfg.plot_flags.annual_cashflow_bars:
            src = top_outputs / f"annual_cashflow_bars_{location_slug}.png"
            dst = plots_dir / "annual_cashflow_bars.png"
            if safe_copy_if_exists(src, dst, logger):
                plots_written["annual_cashflow_bars.png"] = dst
    else:
        logger.info("Finance plots skipped because tariff_mode is unrecognized: %s", cfg.tariff_mode)

    if bool(cfg.outputs.enable_pvgis_crosscheck):
        cross_written = _run_pvgis_crosscheck(cfg, run_dir, full_hourly, location_slug, logger)
        for k, p in cross_written.items():
            outputs_written[k] = p
            if p.suffix.lower() == ".png":
                plots_written[p.name] = p

    # Optional: historical variability mode (multi-year sensitivity)
    if cfg.outputs.enable_variability:
        start_y = int(cfg.outputs.variability_year_start)
        end_y = int(cfg.outputs.variability_year_end)
        variability_rows: list[Dict[str, Any]] = []
        logger.info("Variability mode enabled: years %s..%s", start_y, end_y)
        try:
            base_slug = slugify(cfg.location.name)
            for y in range(start_y, end_y + 1):
                cfg_y = PVROIRunConfig.from_dict(cfg.to_dict())
                cfg_y.location.year = y
                year_slug = f"{base_slug}_{y}"
                cfg_y.location.name = year_slug

                ensure_pvgis_data(cfg_y, run_dir, logger)

                rc = run_subprocess(_build_core_cmd(cfg_y, year_slug), cwd=root, logger=logger)
                if rc != 0:
                    raise RuntimeError(f"Core step failed in variability mode for year {y}.")

                rc = run_subprocess(_build_fin_cmd(cfg_y, year_slug), cwd=root, logger=logger)
                if rc != 0:
                    raise RuntimeError(f"Finance step failed in variability mode for year {y}.")

                hourly_y = load_core_hourly_energy(year_slug, logger)
                fin_y_df = load_financial_summary(year_slug)
                fin_y = build_run_financial_summary(fin_y_df, cfg_y).iloc[0].to_dict()

                row: Dict[str, Any] = {
                    "year": y,
                    "annual_generation_kWh": float(hourly_y["pv_kwh"].sum()),
                    "self_consumption_kWh": float(hourly_y["self_consumed_kwh"].sum()),
                    "export_kWh": float(hourly_y["exported_kwh"].sum()),
                    "import_kWh": float(hourly_y["grid_import_kwh"].sum()),
                }
                row.update(_extract_variability_row(fin_y, cfg_y.tariff_mode))
                variability_rows.append(row)

            variability_yearly_df = pd.DataFrame(variability_rows).sort_values("year")
            variability_yearly_csv = out_dir / "variability_yearly.csv"
            variability_yearly_df.to_csv(variability_yearly_csv, index=False)
            outputs_written["variability_yearly.csv"] = variability_yearly_csv
            logger.info("Exported: %s", variability_yearly_csv)

            metrics_to_summarize = ["annual_pv_kwh"]
            for c in variability_yearly_df.columns:
                if c.startswith("annual_savings"):
                    metrics_to_summarize.append(c)

            summary_rows: list[Dict[str, Any]] = []
            for metric in metrics_to_summarize:
                if metric in variability_yearly_df.columns:
                    vals = pd.to_numeric(variability_yearly_df[metric], errors="coerce").dropna().tolist()
                    summary_rows.append(summarize_distribution(vals, metric))
            variability_summary_df = pd.DataFrame(summary_rows)
            variability_summary_csv = out_dir / "variability_summary.csv"
            variability_summary_df.to_csv(variability_summary_csv, index=False)
            outputs_written["variability_summary.csv"] = variability_summary_csv
            logger.info("Exported: %s", variability_summary_csv)

            main_savings_col = "annual_savings_gbp"
            if cfg.tariff_mode == "compare":
                main_savings_col = "annual_savings_tariffA_gbp"
            elif cfg.tariff_mode == "compare_all":
                main_savings_col = "annual_savings_tariffA_gbp"

            if main_savings_col in variability_yearly_df.columns:
                years = variability_yearly_df["year"].astype(int).tolist()
                savings_main = pd.to_numeric(variability_yearly_df[main_savings_col], errors="coerce").astype(float).tolist()
                variability_png = out_dir / "variability_annual_savings_vs_year.png"
                plot_annual_savings_vs_year(
                    years=years,
                    savings=savings_main,
                    out_png=variability_png,
                    title="Historical variability: annual savings vs year",
                )
                outputs_written["variability_annual_savings_vs_year.png"] = variability_png
                logger.info("Exported: %s", variability_png)

                if cfg.tariff_mode == "compare" and "annual_savings_tariffB_gbp" in variability_yearly_df.columns:
                    savings_b = pd.to_numeric(variability_yearly_df["annual_savings_tariffB_gbp"], errors="coerce").astype(float).tolist()
                    variability_b_png = out_dir / "variability_annual_savings_vs_year_tariffB.png"
                    plot_annual_savings_vs_year(
                        years=years,
                        savings=savings_b,
                        out_png=variability_b_png,
                        title="Historical variability: annual savings vs year (Tariff B)",
                    )
                    outputs_written["variability_annual_savings_vs_year_tariffB.png"] = variability_b_png
                    logger.info("Exported: %s", variability_b_png)

                summary_lookup = {
                    str(r.get("metric")): r
                    for r in variability_summary_df.to_dict(orient="records")
                }
                if main_savings_col in summary_lookup:
                    row = summary_lookup[main_savings_col]
                    hist_png = out_dir / "variability_annual_savings_hist.png"
                    plot_histogram(
                        values=savings_main,
                        out_png=hist_png,
                        title="Historical variability: annual savings distribution",
                        p10=float(row.get("p10", float("nan"))),
                        p50=float(row.get("p50", float("nan"))),
                        p90=float(row.get("p90", float("nan"))),
                        years=years,
                    )
                    outputs_written["variability_annual_savings_hist.png"] = hist_png
                    logger.info("Exported: %s", hist_png)
        except Exception as e:
            logger.warning("Variability mode failed but base run will continue: %s", repr(e))
            status_path = out_dir / "variability_status.txt"
            status_path.write_text(str(e) + "\n", encoding="utf-8")
            outputs_written["variability_status.txt"] = status_path

    # 7) Write summary.md (must include toggles used)
    summary_path = write_summary_md(
        cfg=cfg,
        run_dir=run_dir,
        pvgis_source=pvgis_source,
        outputs_written=outputs_written,
        plots_written=plots_written,
        full_hourly=full_hourly,
        window_hourly=window_hourly,
        window_info=window_info,
        fin_out_df=fin_out_df,
        logger=logger,
    )

   # Generate demo pack report (standalone HTML) — do NOT fail the run if report generation fails
    try:
        html_path = generate_run_report(run_dir)
        logger.info("Demo pack report: %s", html_path)
    except Exception as e:
        logger.warning("Demo pack report generation failed: %s", repr(e))

    logger.info("✅ Pipeline complete. Run folder: %s", run_dir)
    logger.info("Summary: %s", summary_path)
    return run_dir



def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline runner (creates runs/<run_id>/...).")
    parser.add_argument("--config", type=str, default=None, help="Path to a config JSON file.")
    parser.add_argument("--write-default-config", type=str, default=None, help="Write a default config JSON to this path and exit.")
    args = parser.parse_args()

    if args.write_default_config:
        path = Path(args.write_default_config)
        cfg = make_default_config()
        save_config_json(cfg, path)
        print(f"Wrote default config to: {path}")
        return

    if args.config:
        cfg = load_config_json(Path(args.config))
    else:
        cfg = make_default_config()

    try:
        run_dir = run_pipeline(cfg)
        print(f"\n✅ DONE. Open this run folder:\n  {run_dir}\n")
    except Exception as e:
        print("\n❌ PIPELINE FAILED (friendly):")
        print(str(e))
        print("\nTip: open the most recent runs/<run_id>/logs.txt for details.\n")
        raise


if __name__ == "__main__":
    main()
