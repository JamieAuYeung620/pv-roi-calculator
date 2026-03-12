# src/roi_calculator_finance.py
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Tuple

# Allowed dependencies only: pandas, numpy, matplotlib
try:
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")  # safer for headless runs; still fine locally
    import matplotlib.pyplot as plt
except Exception as exc:
    print("ERROR: Missing required packages. This script requires: pandas, numpy, matplotlib")
    print("Fix: Activate your virtual environment, then run:")
    print("  python -m pip install pandas numpy matplotlib")
    print("Details:", repr(exc))
    sys.exit(1)


# -----------------------------
# Helpers: repo root, safety, parsing
# -----------------------------
def get_repo_root() -> Path:
    """
    Determine repo root robustly based on this file's location.

    Assumes:
      repo_root/
        src/roi_calculator_finance.py
        outputs/
    """
    return Path(__file__).resolve().parent.parent


def slugify_location(location: str) -> str:
    """
    Convert user-provided location into a safe filename slug.
    Example: "Warwick Campus" -> "warwick_campus"
    """
    s = location.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("Location becomes empty after cleaning. Use a different --location value.")
    return s


def friendly_exit(message: str, exit_code: int = 1) -> None:
    print(message)
    sys.exit(exit_code)


def validate_inputs(args: argparse.Namespace) -> None:
    # Core metadata (stored in outputs)
    if args.system_kw <= 0:
        friendly_exit("ERROR: --system-kw must be > 0")
    if args.annual_load_kwh <= 0:
        friendly_exit("ERROR: --annual-load-kwh must be > 0")
    if args.profile not in {"home_daytime", "away_daytime"}:
        friendly_exit("ERROR: --profile must be one of: home_daytime, away_daytime")

    # Finance parameters
    if args.capex <= 0:
        friendly_exit("ERROR: --capex must be > 0")
    if args.lifetime < 1:
        friendly_exit("ERROR: --lifetime must be >= 1")
    if args.discount_rate < 0:
        friendly_exit("ERROR: --discount-rate must be >= 0")

    if not (0.0 <= args.degradation <= 0.03):
        friendly_exit("ERROR: --degradation must be between 0 and 0.03 (e.g., 0.005 for 0.5%/year)")
    if not (0.0 <= args.om_frac <= 0.05):
        friendly_exit("ERROR: --om-frac must be between 0 and 0.05 (e.g., 0.01 for 1%/year)")

    # Tariffs must be non-negative
    for name in ["tariffA_import", "tariffA_export", "tariffB_peak", "tariffB_offpeak", "tariffB_export", "tariffC_export"]:
        val = getattr(args, name)
        if val < 0:
            friendly_exit(f"ERROR: --{name.replace('_', '-')} must be >= 0")

    # Peak hour window
    if not (0 <= args.peak_start <= 23):
        friendly_exit("ERROR: --peak-start must be an integer from 0 to 23")
    if not (1 <= args.peak_end <= 24):
        friendly_exit("ERROR: --peak-end must be an integer from 1 to 24")
    if args.peak_start == args.peak_end:
        friendly_exit("ERROR: --peak-start and --peak-end must not be the same (window would be empty)")


def load_hourly_energy_csv(hourly_csv_path: Path) -> pd.DataFrame:
    """
    Load outputs/hourly_energy_<location>.csv produced by the core step.

    Expected columns include:
      timestamp (UTC), pv_kwh, load_kwh, exported_kwh, grid_import_kwh
    If some flow columns are missing, they are recomputed from pv_kwh and load_kwh.

    Returns a DataFrame indexed by timezone-aware UTC timestamps.
    """
    if not hourly_csv_path.exists():
        friendly_exit(
            "ERROR: Missing required hourly energy file:\n"
            f"  {hourly_csv_path}\n\n"
            "Fix: Run the core step first to generate it. Example:\n"
            "  python src/roi_calculator_core.py "
            "--location warwick_campus --system-kw 4 --annual-load-kwh 3200 "
            "--profile away_daytime --import-tariff 0.28 --export-tariff 0.15\n"
        )

    df = pd.read_csv(hourly_csv_path)

    if "timestamp" not in df.columns:
        friendly_exit(
            "ERROR: The hourly energy CSV is missing the required 'timestamp' column.\n"
            f"File: {hourly_csv_path}\n"
            f"Available columns: {list(df.columns)}\n"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        bad = int(df["timestamp"].isna().sum())
        friendly_exit(
            "ERROR: Some timestamps could not be parsed into UTC datetimes.\n"
            f"Bad timestamp rows: {bad}\n"
            f"File: {hourly_csv_path}\n"
        )

    df = df.set_index("timestamp").sort_index()

    # Ensure timezone-aware UTC (defensive)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Required minimal energy columns
    required_min = ["pv_kwh", "load_kwh"]
    missing_min = [c for c in required_min if c not in df.columns]
    if missing_min:
        friendly_exit(
            "ERROR: Hourly CSV is missing required columns.\n"
            f"Missing: {missing_min}\n"
            f"Available columns: {list(df.columns)}\n"
            f"File: {hourly_csv_path}\n"
        )

    # Convert energy columns to numeric safely and clamp
    for col in ["pv_kwh", "load_kwh", "exported_kwh", "grid_import_kwh", "self_consumed_kwh"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)

    # Clamp negative values defensively (and warn)
    for col in ["pv_kwh", "load_kwh", "exported_kwh", "grid_import_kwh", "self_consumed_kwh"]:
        if col in df.columns:
            neg_count = int((df[col] < 0).sum())
            if neg_count > 0:
                print(f"WARNING: Found {neg_count} negative values in '{col}'. Clamping them to 0.")
                df[col] = df[col].clip(lower=0.0)

    # Recompute missing flow columns from pv_kwh + load_kwh
    pv = df["pv_kwh"].values
    load = df["load_kwh"].values

    if "exported_kwh" not in df.columns:
        df["exported_kwh"] = np.maximum(pv - load, 0.0)

    if "grid_import_kwh" not in df.columns:
        df["grid_import_kwh"] = np.maximum(load - pv, 0.0)

    if "self_consumed_kwh" not in df.columns:
        df["self_consumed_kwh"] = np.minimum(load, pv)

    # Final clamp (avoid float noise)
    for col in ["exported_kwh", "grid_import_kwh", "self_consumed_kwh"]:
        df[col] = df[col].clip(lower=0.0)

    # Handle duplicate timestamps (rare, but can happen with bad merges)
    if df.index.has_duplicates:
        print("WARNING: Duplicate timestamps found. Grouping by timestamp and summing energy columns.")
        df = df.groupby(df.index).sum(numeric_only=True).sort_index()

    return df


# -----------------------------
# Tariff logic
# -----------------------------
def peak_mask_from_hours(index_utc: pd.DatetimeIndex, peak_start: int, peak_end: int) -> np.ndarray:
    """
    Create a boolean mask for peak hours based on timestamp hour (UTC).

    Interpretation:
      - Peak window is [peak_start, peak_end) using 24h clock.
      - If peak_start < peak_end: hours >= start AND < end
      - If peak_start > peak_end: wrap-around overnight (hours >= start OR < end)
      - peak_end can be 24 (meaning up to midnight)
    """
    hours = index_utc.hour.values.astype(int)

    if peak_start < peak_end:
        return (hours >= peak_start) & (hours < peak_end)
    else:
        # Wrap-around window (e.g., 22 -> 6)
        # If peak_end == 24, hours < 24 is always true, so this behaves correctly.
        return (hours >= peak_start) | (hours < peak_end)


def compute_tariff_a_annual(
    total_load_kwh: float,
    total_grid_import_kwh: float,
    total_exported_kwh: float,
    import_price: float,
    export_price: float,
) -> Dict[str, float]:
    """
    Tariff A (flat import + flat export):
      baseline_bill = load * import_price
      bill_with_pv = grid_import * import_price - exported * export_price
      savings = baseline_bill - bill_with_pv
    """
    baseline_bill = total_load_kwh * import_price
    import_cost = total_grid_import_kwh * import_price
    export_revenue = total_exported_kwh * export_price
    bill_with_pv = import_cost - export_revenue
    savings = baseline_bill - bill_with_pv

    return {
        "baseline_bill_gbp": float(baseline_bill),
        "import_cost_with_pv_gbp": float(import_cost),
        "export_revenue_gbp": float(export_revenue),
        "bill_with_pv_gbp": float(bill_with_pv),
        "savings_gbp": float(savings),
    }


def compute_tariff_b_annual(
    load_kwh: np.ndarray,
    grid_import_kwh: np.ndarray,
    exported_kwh: np.ndarray,
    peak_mask: np.ndarray,
    peak_price: float,
    offpeak_price: float,
    export_price: float,
) -> Dict[str, float]:
    """
    Tariff B (TOU import + flat export):
      baseline_bill = load_peak*peak_price + load_offpeak*offpeak_price
      bill_with_pv = import_peak*peak_price + import_offpeak*offpeak_price - export*export_price
      savings = baseline_bill - bill_with_pv
    """
    load_peak = float(np.sum(load_kwh[peak_mask]))
    load_offpeak = float(np.sum(load_kwh[~peak_mask]))

    import_peak = float(np.sum(grid_import_kwh[peak_mask]))
    import_offpeak = float(np.sum(grid_import_kwh[~peak_mask]))

    baseline_bill = load_peak * peak_price + load_offpeak * offpeak_price
    import_cost = import_peak * peak_price + import_offpeak * offpeak_price
    export_revenue = float(np.sum(exported_kwh)) * export_price
    bill_with_pv = import_cost - export_revenue
    savings = baseline_bill - bill_with_pv

    return {
        "baseline_bill_gbp": float(baseline_bill),
        "import_cost_with_pv_gbp": float(import_cost),
        "export_revenue_gbp": float(export_revenue),
        "bill_with_pv_gbp": float(bill_with_pv),
        "savings_gbp": float(savings),
        "baseline_load_peak_kwh": float(load_peak),
        "baseline_load_offpeak_kwh": float(load_offpeak),
        "import_peak_kwh": float(import_peak),
        "import_offpeak_kwh": float(import_offpeak),
    }


# -----------------------------
# Lifetime cashflow model
# -----------------------------
def compute_yearly_cashflows_with_degradation(
    hourly: pd.DataFrame,
    lifetime_years: int,
    degradation_per_year: float,
    om_cost_gbp_per_year: float,
    salvage_value_gbp: float,
    discount_rate: float,
    tariffA_import: float,
    tariffA_export: float,
    tariffB_peak: float,
    tariffB_offpeak: float,
    tariffB_export: float,
    tariffC_export: float,
    peak_mask: np.ndarray,
) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Build year-by-year net cashflows for Tariff A, Tariff B, and Tariff C, including:
      - Year 0: capex is applied outside this function (we only build years 1..N here)
      - Years 1..N: (annual savings based on degraded PV) - O&M
      - Terminal salvage/disposal value applied once in final year

    Savings are recalculated each year by degrading hourly PV energy and recomputing:
      self-consumed / export / grid import from (load_kwh vs degraded pv_kwh).
    """
    load_kwh = hourly["load_kwh"].values.astype(float)
    pv_kwh_base = hourly["pv_kwh"].values.astype(float)

    # Baselines (no PV) are constant over years (assuming tariffs + load constant)
    baseline_a = float(np.sum(load_kwh)) * tariffA_import
    baseline_b = (
        float(np.sum(load_kwh[peak_mask])) * tariffB_peak
        + float(np.sum(load_kwh[~peak_mask])) * tariffB_offpeak
    )

    years = np.arange(0, lifetime_years + 1, dtype=int)

    # Arrays include year 0 placeholder (we fill year 0 outside this function)
    net_cf_a = np.zeros(lifetime_years + 1, dtype=float)
    net_cf_b = np.zeros(lifetime_years + 1, dtype=float)
    net_cf_c = np.zeros(lifetime_years + 1, dtype=float)

    # Year 1..N
    for y in range(1, lifetime_years + 1):
        factor = (1.0 - degradation_per_year) ** (y - 1)
        pv_kwh = np.maximum(pv_kwh_base * factor, 0.0)

        # Recompute flows (do not rely on precomputed flows because PV changes)
        exported = np.maximum(pv_kwh - load_kwh, 0.0)
        grid_import = np.maximum(load_kwh - pv_kwh, 0.0)

        # Tariff A bill with PV
        bill_with_pv_a = float(np.sum(grid_import)) * tariffA_import - float(np.sum(exported)) * tariffA_export
        savings_a = baseline_a - bill_with_pv_a
        net_cf_a[y] = savings_a - om_cost_gbp_per_year

        # Tariff B bill with PV (TOU on grid import)
        import_peak = float(np.sum(grid_import[peak_mask]))
        import_offpeak = float(np.sum(grid_import[~peak_mask]))
        bill_with_pv_b = import_peak * tariffB_peak + import_offpeak * tariffB_offpeak - float(np.sum(exported)) * tariffB_export
        savings_b = baseline_b - bill_with_pv_b
        net_cf_b[y] = savings_b - om_cost_gbp_per_year

        # Tariff C bill with PV (same flat import as A + Tariff C export)
        bill_with_pv_c = float(np.sum(grid_import)) * tariffA_import - float(np.sum(exported)) * tariffC_export
        savings_c = baseline_a - bill_with_pv_c
        net_cf_c[y] = savings_c - om_cost_gbp_per_year

    # Terminal one-off salvage/disposal value at end-of-life
    net_cf_a[lifetime_years] += float(salvage_value_gbp)
    net_cf_b[lifetime_years] += float(salvage_value_gbp)
    net_cf_c[lifetime_years] += float(salvage_value_gbp)

    # Discount factors (year 0 factor = 1)
    discount_factors = (1.0 / ((1.0 + discount_rate) ** years)).astype(float)

    return {
        "tariffA": {
            "years": years,
            "net_cashflow_gbp": net_cf_a,
            "discount_factors": discount_factors,
            "baseline_bill_gbp": np.full_like(net_cf_a, baseline_a, dtype=float),
        },
        "tariffB": {
            "years": years,
            "net_cashflow_gbp": net_cf_b,
            "discount_factors": discount_factors,
            "baseline_bill_gbp": np.full_like(net_cf_b, baseline_b, dtype=float),
        },
        "tariffC": {
            "years": years,
            "net_cashflow_gbp": net_cf_c,
            "discount_factors": discount_factors,
            "baseline_bill_gbp": np.full_like(net_cf_c, baseline_a, dtype=float),
        },
    }


def compute_payback_year(cumulative_cashflow: np.ndarray) -> float:
    """
    Simple payback year: first year where cumulative cashflow >= 0.
    Returns NaN if never paid back within lifetime.
    """
    idx = np.where(cumulative_cashflow >= 0.0)[0]
    if idx.size == 0:
        return float("nan")
    return float(idx[0])  # year index


def compute_npv(cashflows: np.ndarray, discount_factors: np.ndarray) -> float:
    return float(np.sum(cashflows * discount_factors))


def compute_roi(total_net_cashflow: float, capex: float) -> float:
    """
    ROI definition used here (simple, undiscounted):
      ROI = (Total net cashflow over lifetime) / capex

    Where Total net cashflow includes:
      - Year 0: -capex
      - Years 1..N: annual_savings - O&M

    Interpretation:
      ROI = 0.50  means 50% net profit over lifetime relative to capex.
      ROI = -0.20 means you did not recover full cost over lifetime.
    """
    if capex <= 0:
        return float("nan")
    return float(total_net_cashflow / capex)


def _add_plot_disclaimer(data_year: int) -> str:
    return f"Based on PVGIS {int(data_year)} data. Values are estimates, not guaranteed."


# -----------------------------
# Plotting
# -----------------------------
def save_cumulative_cashflow_plot(
    years: np.ndarray,
    cumulative_a: np.ndarray,
    cumulative_b: np.ndarray,
    png_path: Path,
    location_slug: str,
    data_year: int,
) -> None:
    def payback_intersection_x(years_arr: np.ndarray, cumulative_arr: np.ndarray) -> float:
        idx = np.where(cumulative_arr >= 0.0)[0]
        if idx.size == 0:
            return float("nan")
        i = int(idx[0])
        if i == 0:
            return float(years_arr[0])
        x0 = float(years_arr[i - 1])
        x1 = float(years_arr[i])
        y0 = float(cumulative_arr[i - 1])
        y1 = float(cumulative_arr[i])
        if y1 == y0:
            return x1
        frac = (0.0 - y0) / (y1 - y0)
        frac = min(max(frac, 0.0), 1.0)
        return x0 + frac * (x1 - x0)

    payback_a_x = payback_intersection_x(np.array(years), np.array(cumulative_a))
    payback_b_x = payback_intersection_x(np.array(years), np.array(cumulative_b))

    plt.figure(figsize=(10, 4))
    plt.plot(years, cumulative_a, label="Tariff A cumulative cashflow (£)")
    plt.plot(years, cumulative_b, label="Tariff B cumulative cashflow (£)")
    plt.axhline(0.0, linewidth=1.0)

    if np.isfinite(payback_a_x):
        plt.scatter([payback_a_x], [0.0], s=60, zorder=6, label=f"Tariff A payback (~Year {payback_a_x:.1f})")
    if np.isfinite(payback_b_x):
        plt.scatter([payback_b_x], [0.0], s=60, zorder=6, label=f"Tariff B payback (~Year {payback_b_x:.1f})")

    plt.xlabel("Year of system life (years)")
    plt.ylabel("Cumulative cashflow (£)")
    plt.title(f"Cumulative bill savings and earnings — {location_slug}")
    plt.text(0.02, 0.95, "Payback = where the line crosses £0", transform=plt.gca().transAxes, va="top", fontsize=9)
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def save_cumulative_cashflow_plot_all(
    years: np.ndarray,
    cumulative_a: np.ndarray,
    cumulative_b: np.ndarray,
    cumulative_c: np.ndarray,
    png_path: Path,
    location_slug: str,
    data_year: int,
) -> None:
    def payback_intersection_x(years_arr: np.ndarray, cumulative_arr: np.ndarray) -> float:
        idx = np.where(cumulative_arr >= 0.0)[0]
        if idx.size == 0:
            return float("nan")
        i = int(idx[0])
        if i == 0:
            return float(years_arr[0])
        x0 = float(years_arr[i - 1])
        x1 = float(years_arr[i])
        y0 = float(cumulative_arr[i - 1])
        y1 = float(cumulative_arr[i])
        if y1 == y0:
            return x1
        frac = (0.0 - y0) / (y1 - y0)
        frac = min(max(frac, 0.0), 1.0)
        return x0 + frac * (x1 - x0)

    payback_a_x = payback_intersection_x(np.array(years), np.array(cumulative_a))
    payback_b_x = payback_intersection_x(np.array(years), np.array(cumulative_b))
    payback_c_x = payback_intersection_x(np.array(years), np.array(cumulative_c))

    plt.figure(figsize=(10, 4))
    plt.plot(years, cumulative_a, label="Tariff A cumulative cashflow (£)")
    plt.plot(years, cumulative_b, label="Tariff B cumulative cashflow (£)")
    plt.plot(years, cumulative_c, label="Tariff C cumulative cashflow (£)")
    plt.axhline(0.0, linewidth=1.0)

    if np.isfinite(payback_a_x):
        plt.scatter([payback_a_x], [0.0], s=60, zorder=6, label=f"Tariff A payback (~Year {payback_a_x:.1f})")
    if np.isfinite(payback_b_x):
        plt.scatter([payback_b_x], [0.0], s=60, zorder=6, label=f"Tariff B payback (~Year {payback_b_x:.1f})")
    if np.isfinite(payback_c_x):
        plt.scatter([payback_c_x], [0.0], s=60, zorder=6, label=f"Tariff C payback (~Year {payback_c_x:.1f})")

    plt.xlabel("Year of system life (years)")
    plt.ylabel("Cumulative cashflow (£)")
    plt.title(f"Cumulative bill savings and earnings — {location_slug}")
    plt.text(0.02, 0.95, "Payback = where the line crosses £0", transform=plt.gca().transAxes, va="top", fontsize=9)
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def save_cumulative_cashflow_plot_single(
    years: np.ndarray,
    cumulative: np.ndarray,
    png_path: Path,
    location_slug: str,
    data_year: int,
    tariff_label: str,
) -> None:
    def payback_intersection_x(years_arr: np.ndarray, cumulative_arr: np.ndarray) -> float:
        idx = np.where(cumulative_arr >= 0.0)[0]
        if idx.size == 0:
            return float("nan")
        i = int(idx[0])
        if i == 0:
            return float(years_arr[0])
        x0 = float(years_arr[i - 1])
        x1 = float(years_arr[i])
        y0 = float(cumulative_arr[i - 1])
        y1 = float(cumulative_arr[i])
        if y1 == y0:
            return x1
        frac = (0.0 - y0) / (y1 - y0)
        frac = min(max(frac, 0.0), 1.0)
        return x0 + frac * (x1 - x0)

    payback_x = payback_intersection_x(np.array(years), np.array(cumulative))

    plt.figure(figsize=(10, 4))
    plt.plot(years, cumulative, label=f"Tariff {tariff_label} cumulative cashflow (£)")
    plt.axhline(0.0, linewidth=1.0)

    if np.isfinite(payback_x):
        plt.scatter([payback_x], [0.0], s=60, zorder=6, label=f"Tariff {tariff_label} payback (~Year {payback_x:.1f})")

    plt.xlabel("Year of system life (years)")
    plt.ylabel("Cumulative cashflow (£)")
    plt.title(f"Cumulative bill savings and earnings — {location_slug}")
    plt.text(0.02, 0.95, "Payback = where the line crosses £0", transform=plt.gca().transAxes, va="top", fontsize=9)
    plt.legend()
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year), fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


def save_annual_cashflow_bars_plot(
    years: np.ndarray,
    cashflow_a: np.ndarray,
    cashflow_b: np.ndarray,
    png_path: Path,
    location_slug: str,
    data_year: int,
) -> None:
    year0_a = float(cashflow_a[0]) if len(cashflow_a) > 0 else float("nan")
    year0_b = float(cashflow_b[0]) if len(cashflow_b) > 0 else float("nan")

    # Exclude Year 0 (CAPEX) so annual operating-year differences are visible.
    mask = years >= 1
    x = years[mask].astype(float)
    cashflow_a = cashflow_a[mask]
    cashflow_b = cashflow_b[mask]
    width = 0.38

    plt.figure(figsize=(11, 4))
    plt.bar(x - width / 2, cashflow_a, width=width, label="Tariff A net cashflow (£)")
    plt.bar(x + width / 2, cashflow_b, width=width, label="Tariff B net cashflow (£)")
    plt.axhline(0.0, linewidth=1.0)
    plt.xlabel("Year of system life (years)")
    plt.ylabel("Annual net cashflow (£)")
    plt.title(f"Yearly bill savings and earnings — {location_slug}")
    plt.legend()
    year0_note = f"Upfront cost (Year 0): Tariff A {year0_a:,.0f} GBP, Tariff B {year0_b:,.0f} GBP (excluded from bars)"
    plt.figtext(0.01, 0.035, year0_note, fontsize=8)
    plt.figtext(0.01, 0.01, _add_plot_disclaimer(data_year), fontsize=8)
    plt.tight_layout(rect=(0, 0.07, 1, 1))
    plt.savefig(png_path, dpi=150)
    plt.close()


# -----------------------------
# CLI
# -----------------------------
def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PV ROI finance extension: Tariff A vs Tariff B + lifetime cashflows (reads core hourly CSV)."
    )

    # Metadata (also used for filenames and output summary table)
    parser.add_argument("--location", type=str, required=True,
                        help="Location slug used in filenames (example: warwick_campus).")
    parser.add_argument("--system-kw", type=float, required=True,
                        help="PV system size in kW (stored in output summary; must be > 0).")
    parser.add_argument("--annual-load-kwh", type=float, required=True,
                        help="Annual load in kWh/year (stored in output summary; must be > 0).")
    parser.add_argument("--profile", type=str, required=True, choices=["home_daytime", "away_daytime"],
                        help="Load profile name (stored in output summary).")

    # Finance model parameters
    parser.add_argument("--capex", type=float, required=True,
                        help="Upfront installed cost in £ (year 0; must be > 0).")
    parser.add_argument("--discount-rate", type=float, default=0.05,
                        help="Discount rate for NPV (default: 0.05).")
    parser.add_argument("--lifetime", type=int, default=25,
                        help="System lifetime in years (default: 25).")
    parser.add_argument("--degradation", type=float, default=0.005,
                        help="PV degradation per year as a fraction (default: 0.005 = 0.5%%/year).")
    parser.add_argument("--om-frac", type=float, default=0.01,
                        help="O&M cost fraction of capex per year (default: 0.01 = 1%%/year).")
    parser.add_argument("--salvage-value-gbp", type=float, default=0.0,
                        help="End-of-life salvage/disposal value in £ (default: 0.0; can be negative).")

    # Tariff A (flat)
    parser.add_argument("--tariffA-import", dest="tariffA_import", type=float, default=0.28,
                        help="Tariff A import price in £/kWh (default: 0.28).")
    parser.add_argument("--tariffA-export", dest="tariffA_export", type=float, default=0.15,
                        help="Tariff A export price in £/kWh (default: 0.15).")

    # Tariff B (TOU import + flat export)
    parser.add_argument("--tariffB-peak", dest="tariffB_peak", type=float, default=0.35,
                        help="Tariff B peak import price in £/kWh (default: 0.35).")
    parser.add_argument("--tariffB-offpeak", dest="tariffB_offpeak", type=float, default=0.22,
                        help="Tariff B off-peak import price in £/kWh (default: 0.22).")
    parser.add_argument("--tariffB-export", dest="tariffB_export", type=float, default=0.15,
                        help="Tariff B export price in £/kWh (default: 0.15).")
    parser.add_argument("--tariffC-export", dest="tariffC_export", type=float, default=0.05,
                        help="Tariff C export price in £/kWh (default: 0.05).")

    # Peak window hours (interpreted on timestamp hour in UTC)
    parser.add_argument("--peak-start", type=int, default=16,
                        help="Peak start hour (0-23), inclusive. Default: 16.")
    parser.add_argument("--peak-end", type=int, default=19,
                        help="Peak end hour (1-24), exclusive. Default: 19.")

    return parser


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    validate_inputs(args)

    repo_root = get_repo_root()
    outputs_dir = repo_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    location_slug = slugify_location(args.location)

    # Load hourly energy file produced by the core step
    hourly_csv_path = outputs_dir / f"hourly_energy_{location_slug}.csv"
    print("\nLoading hourly energy CSV from core step...")
    print(f"  {hourly_csv_path}")
    hourly = load_hourly_energy_csv(hourly_csv_path)
    data_year = int(hourly.index.min().year)

    # Compute annual totals (as represented by the CSV period)
    annual_pv_kwh = float(hourly["pv_kwh"].sum())
    annual_load_kwh = float(hourly["load_kwh"].sum())
    annual_self_kwh = float(hourly["self_consumed_kwh"].sum())
    annual_export_kwh = float(hourly["exported_kwh"].sum())
    annual_import_kwh = float(hourly["grid_import_kwh"].sum())

    # Optional sanity check vs CLI annual load (core step usually matches exactly)
    if annual_load_kwh > 0:
        pct_diff = 100.0 * abs(annual_load_kwh - float(args.annual_load_kwh)) / float(args.annual_load_kwh)
        if pct_diff > 2.0:
            print(
                f"WARNING: Hourly file load total ({annual_load_kwh:,.1f} kWh) differs from "
                f"--annual-load-kwh ({args.annual_load_kwh:,.1f} kWh) by {pct_diff:.1f}%. "
                "This can happen if the hourly CSV is not a full year or was generated with different inputs."
            )

    # Build peak mask (UTC hour-based)
    peak_mask = peak_mask_from_hours(hourly.index, peak_start=args.peak_start, peak_end=args.peak_end)

    # Compute annual bills/savings for year 1 using the stored flows
    tariffA_annual = compute_tariff_a_annual(
        total_load_kwh=annual_load_kwh,
        total_grid_import_kwh=annual_import_kwh,
        total_exported_kwh=annual_export_kwh,
        import_price=float(args.tariffA_import),
        export_price=float(args.tariffA_export),
    )

    tariffB_annual = compute_tariff_b_annual(
        load_kwh=hourly["load_kwh"].values,
        grid_import_kwh=hourly["grid_import_kwh"].values,
        exported_kwh=hourly["exported_kwh"].values,
        peak_mask=peak_mask,
        peak_price=float(args.tariffB_peak),
        offpeak_price=float(args.tariffB_offpeak),
        export_price=float(args.tariffB_export),
    )
    tariffC_annual = compute_tariff_a_annual(
        total_load_kwh=annual_load_kwh,
        total_grid_import_kwh=annual_import_kwh,
        total_exported_kwh=annual_export_kwh,
        import_price=float(args.tariffA_import),
        export_price=float(args.tariffC_export),
    )

    # Lifetime cashflow model
    capex = float(args.capex)
    om_cost = capex * float(args.om_frac)  # £/year
    lifetime_years = int(args.lifetime)

    cashflows = compute_yearly_cashflows_with_degradation(
        hourly=hourly,
        lifetime_years=lifetime_years,
        degradation_per_year=float(args.degradation),
        om_cost_gbp_per_year=float(om_cost),
        salvage_value_gbp=float(args.salvage_value_gbp),
        discount_rate=float(args.discount_rate),
        tariffA_import=float(args.tariffA_import),
        tariffA_export=float(args.tariffA_export),
        tariffB_peak=float(args.tariffB_peak),
        tariffB_offpeak=float(args.tariffB_offpeak),
        tariffB_export=float(args.tariffB_export),
        tariffC_export=float(args.tariffC_export),
        peak_mask=peak_mask,
    )

    # Insert capex at year 0
    years = cashflows["tariffA"]["years"]
    cf_a = cashflows["tariffA"]["net_cashflow_gbp"].copy()
    cf_b = cashflows["tariffB"]["net_cashflow_gbp"].copy()
    cf_c = cashflows["tariffC"]["net_cashflow_gbp"].copy()
    cf_a[0] = -capex
    cf_b[0] = -capex
    cf_c[0] = -capex

    cumulative_a = np.cumsum(cf_a)
    cumulative_b = np.cumsum(cf_b)
    cumulative_c = np.cumsum(cf_c)

    discount_factors = cashflows["tariffA"]["discount_factors"]  # same years/discounting for both
    npv_a = compute_npv(cf_a, discount_factors)
    npv_b = compute_npv(cf_b, discount_factors)
    npv_c = compute_npv(cf_c, discount_factors)

    payback_a = compute_payback_year(cumulative_a)
    payback_b = compute_payback_year(cumulative_b)
    payback_c = compute_payback_year(cumulative_c)

    roi_a = compute_roi(total_net_cashflow=float(np.sum(cf_a)), capex=capex)
    roi_b = compute_roi(total_net_cashflow=float(np.sum(cf_b)), capex=capex)
    roi_c = compute_roi(total_net_cashflow=float(np.sum(cf_c)), capex=capex)

    # Save financial summary CSV (single row)
    financial_summary_path = outputs_dir / f"financial_summary_{location_slug}.csv"
    summary_row = {
        "location": location_slug,
        "system_kw": float(args.system_kw),
        "annual_load_kwh": float(args.annual_load_kwh),
        "profile": args.profile,

        "tariffA_import": float(args.tariffA_import),
        "tariffA_export": float(args.tariffA_export),
        "tariffB_peak": float(args.tariffB_peak),
        "tariffB_offpeak": float(args.tariffB_offpeak),
        "tariffB_export": float(args.tariffB_export),
        "tariffC_export": float(args.tariffC_export),
        "salvage_value_gbp": float(args.salvage_value_gbp),

        "annual_pv_kwh": annual_pv_kwh,
        "annual_self_consumed_kwh": annual_self_kwh,
        "annual_exported_kwh": annual_export_kwh,

        "annual_savings_tariffA_gbp": float(tariffA_annual["savings_gbp"]),
        "annual_savings_tariffB_gbp": float(tariffB_annual["savings_gbp"]),
        "annual_savings_tariffC_gbp": float(tariffC_annual["savings_gbp"]),

        "payback_year_tariffA": payback_a,
        "payback_year_tariffB": payback_b,
        "payback_year_tariffC": payback_c,

        "npv_tariffA": npv_a,
        "npv_tariffB": npv_b,
        "npv_tariffC": npv_c,

        "roi_tariffA": roi_a,
        "roi_tariffB": roi_b,
        "roi_tariffC": roi_c,
    }
    pd.DataFrame([summary_row]).to_csv(financial_summary_path, index=False)

    # Plots
    cumulative_png = outputs_dir / f"cumulative_cashflow_comparison_{location_slug}.png"
    cumulative_all_png = outputs_dir / f"cumulative_cashflow_comparison_all_{location_slug}.png"
    annual_bars_png = outputs_dir / f"annual_cashflow_bars_{location_slug}.png"
    cumulative_a_png = outputs_dir / f"cumulative_cashflow_tariffA_{location_slug}.png"
    cumulative_b_png = outputs_dir / f"cumulative_cashflow_tariffB_{location_slug}.png"
    cumulative_c_png = outputs_dir / f"cumulative_cashflow_tariffC_{location_slug}.png"

    save_cumulative_cashflow_plot(
        years=years,
        cumulative_a=cumulative_a,
        cumulative_b=cumulative_b,
        png_path=cumulative_png,
        location_slug=location_slug,
        data_year=data_year,
    )
    save_cumulative_cashflow_plot_all(
        years=years,
        cumulative_a=cumulative_a,
        cumulative_b=cumulative_b,
        cumulative_c=cumulative_c,
        png_path=cumulative_all_png,
        location_slug=location_slug,
        data_year=data_year,
    )
    save_cumulative_cashflow_plot_single(
        years=years,
        cumulative=cumulative_a,
        png_path=cumulative_a_png,
        location_slug=location_slug,
        data_year=data_year,
        tariff_label="A",
    )
    save_cumulative_cashflow_plot_single(
        years=years,
        cumulative=cumulative_b,
        png_path=cumulative_b_png,
        location_slug=location_slug,
        data_year=data_year,
        tariff_label="B",
    )
    save_cumulative_cashflow_plot_single(
        years=years,
        cumulative=cumulative_c,
        png_path=cumulative_c_png,
        location_slug=location_slug,
        data_year=data_year,
        tariff_label="C",
    )

    save_annual_cashflow_bars_plot(
        years=years,
        cashflow_a=cf_a,
        cashflow_b=cf_b,
        png_path=annual_bars_png,
        location_slug=location_slug,
        data_year=data_year,
    )

    # Clean summary block
    def fmt_money(x: float) -> str:
        return f"£{x:,.2f}"

    def fmt_year(y: float) -> str:
        return "Not reached" if not np.isfinite(y) else f"Year {int(y)}"

    better_annual = "Tariff A" if tariffA_annual["savings_gbp"] > tariffB_annual["savings_gbp"] else "Tariff B"
    better_npv = "Tariff A" if npv_a > npv_b else "Tariff B"

    print("\n" + "=" * 78)
    print("Finance Summary — Tariff A (Flat) vs Tariff B (TOU import + flat export)")
    print("=" * 78)
    print(f"Location:                 {location_slug}")
    print(f"System size:              {float(args.system_kw):.2f} kW")
    print(f"Profile:                  {args.profile}")
    print(f"Annual load (target):     {float(args.annual_load_kwh):,.0f} kWh/year")
    print("")
    print("Annual energy (from hourly CSV):")
    print(f"  PV generation:          {annual_pv_kwh:,.1f} kWh")
    print(f"  Household load:         {annual_load_kwh:,.1f} kWh")
    print(f"  Self-consumed PV:       {annual_self_kwh:,.1f} kWh")
    print(f"  Exported PV:            {annual_export_kwh:,.1f} kWh")
    print(f"  Grid import with PV:    {annual_import_kwh:,.1f} kWh")
    print("")
    print("Tariff A (flat):")
    print(f"  Import:                 {float(args.tariffA_import):.3f} £/kWh")
    print(f"  Export:                 {float(args.tariffA_export):.3f} £/kWh")
    print(f"  Baseline bill (no PV):  {fmt_money(tariffA_annual['baseline_bill_gbp'])}")
    print(f"  Bill with PV:           {fmt_money(tariffA_annual['bill_with_pv_gbp'])}")
    print(f"  Annual savings:         {fmt_money(tariffA_annual['savings_gbp'])}")
    print("")
    print("Tariff B (TOU import, flat export):")
    print(f"  Peak import:            {float(args.tariffB_peak):.3f} £/kWh")
    print(f"  Off-peak import:        {float(args.tariffB_offpeak):.3f} £/kWh")
    print(f"  Export:                 {float(args.tariffB_export):.3f} £/kWh")
    print(f"  Peak window (UTC):      {args.peak_start:02d}:00–{args.peak_end:02d}:00  (end is exclusive)")
    print(f"  Baseline bill (no PV):  {fmt_money(tariffB_annual['baseline_bill_gbp'])}")
    print(f"  Bill with PV:           {fmt_money(tariffB_annual['bill_with_pv_gbp'])}")
    print(f"  Annual savings:         {fmt_money(tariffB_annual['savings_gbp'])}")
    print("")
    print("Lifetime model assumptions:")
    print(f"  Capex (Year 0):         {fmt_money(-capex)} (cashflow)")
    print(f"  O&M cost:               {fmt_money(om_cost)} per year")
    print(f"  PV degradation:         {float(args.degradation) * 100:.2f}% per year")
    print(f"  Discount rate:          {float(args.discount_rate) * 100:.2f}%")
    print(f"  Lifetime:               {lifetime_years} years")
    print("")
    print("Lifetime financial metrics (includes capex + O&M; savings degrade with PV):")
    print(f"  Tariff A payback:       {fmt_year(payback_a)}")
    print(f"  Tariff B payback:       {fmt_year(payback_b)}")
    print(f"  Tariff A NPV:           {fmt_money(npv_a)}")
    print(f"  Tariff B NPV:           {fmt_money(npv_b)}")
    print(f"  Tariff A ROI:           {roi_a * 100:.1f}%  (ROI = total net cashflow / capex)")
    print(f"  Tariff B ROI:           {roi_b * 100:.1f}%  (ROI = total net cashflow / capex)")
    print("")
    print(f"Quick comparison:")
    print(f"  Higher annual savings:  {better_annual}")
    print(f"  Higher NPV:             {better_npv}")
    print("=" * 78)

    print("\nSaved outputs:")
    print(f"  CSV  Financial summary: {financial_summary_path}")
    print(f"  PNG  Cumulative cashflow comparison: {cumulative_png}")
    print(f"  PNG  Cumulative cashflow comparison (all): {cumulative_all_png}")
    print(f"  PNG  Annual cashflow bars:           {annual_bars_png}")
    print("")


if __name__ == "__main__":
    main()
