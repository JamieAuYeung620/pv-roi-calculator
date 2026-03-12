# src/roi_calculator_core.py
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
# Constants / model defaults
# -----------------------------
IRRADIANCE_CANDIDATES = ["poa_global", "ghi", "G(h)", "G(i)"]
TEMPERATURE_CANDIDATES = ["temp_air", "T2m"]

G_STC_W_PER_M2 = 1000.0  # Standard Test Condition irradiance (W/m²)
T_REF_C = 25.0           # Standard Test Condition cell temperature (°C)


# -----------------------------
# Helpers: paths, parsing, safety
# -----------------------------
def get_repo_root() -> Path:
    """
    Determine repo root robustly based on this file's location.

    Assumes:
      repo_root/
        src/roi_calculator_core.py
        data/
        outputs/
    """
    return Path(__file__).resolve().parent.parent


def slugify_location(location: str) -> str:
    """
    Convert a user-provided location string into a safe filename slug.
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


def detect_column(available_columns: List[str], candidates: List[str]) -> Optional[str]:
    """
    Return the first candidate column found in available_columns.
    Also tries case-insensitive matching for robustness.
    """
    available_set = set(available_columns)

    # Exact match first (best)
    for c in candidates:
        if c in available_set:
            return c

    # Case-insensitive fallback
    lower_map = {col.lower(): col for col in available_columns}
    for c in candidates:
        key = c.lower()
        if key in lower_map:
            return lower_map[key]

    return None


def load_pvgis_cached_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load PVGIS cached CSV. Requires a 'timestamp' column.
    Returns a DataFrame indexed by timezone-aware UTC timestamps, sorted ascending.
    """
    if not csv_path.exists():
        friendly_exit(
            "ERROR: Cannot find the cached PVGIS CSV:\n"
            f"  {csv_path}\n\n"
            "Fix: Make sure your cached file exists at data/raw_<location>.csv in the repo root."
        )

    df = pd.read_csv(csv_path)

    if "timestamp" not in df.columns:
        friendly_exit(
            "ERROR: The cached CSV is missing the required 'timestamp' column.\n"
            f"File: {csv_path}\n"
            f"Available columns: {list(df.columns)}\n\n"
            "Fix: Regenerate the cached CSV so it includes a 'timestamp' column (UTC)."
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        bad_rows = int(df["timestamp"].isna().sum())
        friendly_exit(
            "ERROR: Some timestamps could not be parsed into datetimes.\n"
            f"Bad timestamp rows: {bad_rows}\n"
            f"File: {csv_path}\n\n"
            "Fix: Ensure the 'timestamp' column is valid ISO datetime strings (UTC)."
        )

    df = df.set_index("timestamp").sort_index()

    # Ensure timezone-aware UTC (defensive)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    return df


def ensure_numeric_irradiance(series: pd.Series, column_name: str) -> pd.Series:
    """
    Convert irradiance column to numeric and fill missing values with 0 (safe at night).
    Also clips negative values to 0.
    """
    s = pd.to_numeric(series, errors="coerce").astype(float)
    s = s.fillna(0.0)
    s = s.clip(lower=0.0)
    if s.isna().all():
        friendly_exit(
            f"ERROR: Irradiance column '{column_name}' could not be converted to numeric values.\n"
            "Fix: Check the CSV column contents and units (expected W/m²)."
        )
    return s


def ensure_numeric_temperature(series: pd.Series, column_name: str) -> pd.Series:
    """
    Convert temperature column to numeric.
    Robust missing handling:
      - forward fill
      - then fill remaining NaNs with 0
    """
    s = pd.to_numeric(series, errors="coerce").astype(float)

    # Forward fill (works well for short gaps), then fill remaining as 0
    s = s.ffill().fillna(0.0)

    # If the entire column was NaN originally, this becomes all 0.0. Warn in that case.
    if np.isclose(float(s.abs().sum()), 0.0):
        print(
            f"WARNING: Temperature column '{column_name}' appears to be missing/empty; "
            "using 0°C fallback after filling. PV temperature derating may be unrealistic."
        )
    return s


def compute_timestep_hours(time_index: pd.DatetimeIndex) -> pd.Series:
    """
    Compute timestep in hours for each row (aligned to rows).
    - Uses diff between timestamps.
    - Fills first row with the median positive timestep.
    - Clips non-positive timesteps to the median positive timestep.
    """
    dt = time_index.to_series().diff().dt.total_seconds().div(3600.0)

    positive_dt = dt[(dt > 0) & np.isfinite(dt)]
    if positive_dt.empty:
        # Fallback for degenerate time index
        dt[:] = 1.0
        return dt.fillna(1.0)

    median_dt = float(positive_dt.median())

    dt = dt.fillna(median_dt)
    dt = dt.where(dt > 0, median_dt)

    # Guard: extremely tiny or huge timestep values can cause confusing results
    if median_dt < 0.25 or median_dt > 2.5:
        print(
            f"WARNING: Median timestep is {median_dt:.3f} hours (expected ~1.0 for hourly data). "
            "Energy calculations will still run using this timestep."
        )

    return dt


# -----------------------------
# PV model: simple PVWatts-style
# -----------------------------
def estimate_cell_temperature_noct_c(
    temp_air_c: np.ndarray,
    irradiance_w_per_m2: np.ndarray,
    noct_c: float,
) -> np.ndarray:
    """
    Simple NOCT-style cell temperature estimate:
      T_cell = T_air + (NOCT - 20) / 800 * G

    Where:
      - NOCT is typically ~45°C
      - G is irradiance on plane (W/m²)
    """
    return temp_air_c + ((noct_c - 20.0) / 800.0) * irradiance_w_per_m2


def compute_pv_ac_power_kw_pvwatts(
    irradiance_w_per_m2: np.ndarray,
    temp_air_c: np.ndarray,
    system_kw_dc: float,
    temp_coeff_per_c: float,
    loss_frac: float,
    inverter_eff: float,
    inverter_ac_kw: float,
    noct_c: float,
) -> np.ndarray:
    """
    PVWatts-style AC power model (simple, robust):
      1) DC scales with irradiance relative to 1000 W/m²
      2) Apply temperature derate using a single coefficient
      3) Apply lumped losses
      4) Convert DC->AC with inverter efficiency
      5) Clip to inverter rating
    """
    G = np.maximum(irradiance_w_per_m2, 0.0)

    t_cell = estimate_cell_temperature_noct_c(temp_air_c=temp_air_c, irradiance_w_per_m2=G, noct_c=noct_c)

    temp_factor = 1.0 + temp_coeff_per_c * (t_cell - T_REF_C)
    temp_factor = np.maximum(temp_factor, 0.0)  # avoid negative output

    p_dc_kw = system_kw_dc * (G / G_STC_W_PER_M2) * temp_factor
    p_dc_kw = np.maximum(p_dc_kw, 0.0)

    p_dc_net_kw = p_dc_kw * (1.0 - loss_frac)
    p_dc_net_kw = np.maximum(p_dc_net_kw, 0.0)

    p_ac_kw = p_dc_net_kw * inverter_eff
    p_ac_kw = np.minimum(p_ac_kw, inverter_ac_kw)
    p_ac_kw = np.maximum(p_ac_kw, 0.0)

    return p_ac_kw


# -----------------------------
# Load profile generation
# -----------------------------
def get_daily_load_shape(profile_name: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns (home_daytime_shape, away_daytime_shape) as 24-length arrays.
    Values are relative weights (not kWh yet).
    """
    # More load during daytime
    home_daytime = np.array([
        0.28, 0.24, 0.22, 0.22, 0.24, 0.30,
        0.40, 0.50, 0.56, 0.62, 0.68, 0.72,
        0.76, 0.76, 0.72, 0.66, 0.60, 0.64,
        0.74, 0.80, 0.74, 0.64, 0.48, 0.36
    ], dtype=float)

    # More load morning/evening, less midday
    away_daytime = np.array([
        0.28, 0.24, 0.22, 0.22, 0.24, 0.34,
        0.50, 0.72, 0.78, 0.60, 0.44, 0.34,
        0.28, 0.28, 0.32, 0.38, 0.50, 0.76,
        0.92, 0.98, 0.92, 0.76, 0.58, 0.38
    ], dtype=float)

    if profile_name not in {"home_daytime", "away_daytime"}:
        friendly_exit(
            "ERROR: Invalid --profile value.\n"
            "Allowed: home_daytime, away_daytime"
        )

    return home_daytime, away_daytime


def generate_hourly_load_weights(
    index_utc: pd.DatetimeIndex,
    profile_name: str,
    seasonal_variance_pct: float,
) -> np.ndarray:
    """
    Generate a synthetic household load 'shape' per hour (relative weights).

    Includes:
      - Hour-of-day pattern (different by archetype)
      - Mild weekend behaviour difference
      - Mild seasonal factor (winter slightly higher, summer slightly lower)

    Output is a positive weight per timestamp (interpretable as relative kW before scaling).
    """
    home_shape, away_shape = get_daily_load_shape(profile_name=profile_name)

    hours = index_utc.hour.values
    is_weekend = (index_utc.weekday.values >= 5)  # Saturday=5, Sunday=6

    # Base hour-of-day weights
    if profile_name == "home_daytime":
        base = home_shape[hours]
        weekend_multiplier = np.where(is_weekend, 1.05, 1.00)  # slightly higher weekend usage
    else:
        # On weekends, an "away daytime" home is often more like "home daytime".
        away_base = away_shape[hours]
        weekend_base = 0.6 * away_shape[hours] + 0.4 * home_shape[hours]
        base = np.where(is_weekend, weekend_base, away_base)
        weekend_multiplier = np.ones_like(base, dtype=float)

    # Seasonal factor: peak in mid-winter, lower in mid-summer.
    # A "Dec vs Jun swing" of X% maps to +/- X/2% around the baseline.
    day_of_year = index_utc.dayofyear.values.astype(float)
    seasonal_amplitude = float(seasonal_variance_pct) / 200.0
    seasonal_factor = 1.0 + seasonal_amplitude * np.cos(2.0 * np.pi * (day_of_year - 15.0) / 365.25)

    weights = base * weekend_multiplier * seasonal_factor

    # Defensive: ensure strictly positive weights
    weights = np.maximum(weights, 1e-6)
    return weights


def scale_load_to_annual_kwh(
    load_weights_kw_relative: np.ndarray,
    dt_hours: np.ndarray,
    annual_load_kwh: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Scale relative load weights into:
      - load_kw (kW)
      - load_kwh (kWh per timestep)

    Ensures total annual consumption equals annual_load_kwh.
    """
    if annual_load_kwh <= 0:
        friendly_exit("ERROR: --annual-load-kwh must be > 0")

    unscaled_kwh = float(np.sum(load_weights_kw_relative * dt_hours))
    if unscaled_kwh <= 0 or not np.isfinite(unscaled_kwh):
        friendly_exit("ERROR: Load scaling failed because the unscaled total energy is not positive.")

    scale_factor = annual_load_kwh / unscaled_kwh

    load_kw = load_weights_kw_relative * scale_factor
    load_kw = np.maximum(load_kw, 0.0)

    load_kwh = load_kw * dt_hours
    load_kwh = np.maximum(load_kwh, 0.0)

    # Final tiny correction so sum matches exactly (helps beginner confidence)
    total_kwh = float(np.sum(load_kwh))
    if total_kwh > 0 and np.isfinite(total_kwh):
        ratio = annual_load_kwh / total_kwh
        load_kw *= ratio
        load_kwh *= ratio

    # Defensive clip
    load_kw = np.maximum(load_kw, 0.0)
    load_kwh = np.maximum(load_kwh, 0.0)

    return load_kw, load_kwh


# -----------------------------
# Energy flows & finance
# -----------------------------
def compute_energy_flows(pv_kwh: np.ndarray, load_kwh: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Hourly energy flow logic:
      self_consumed_kwh = min(load_kwh, pv_kwh)
      exported_kwh     = max(pv_kwh - load_kwh, 0)
      grid_import_kwh  = max(load_kwh - pv_kwh, 0)
    """
    pv_kwh = np.maximum(pv_kwh, 0.0)
    load_kwh = np.maximum(load_kwh, 0.0)

    self_consumed = np.minimum(load_kwh, pv_kwh)
    exported = np.maximum(pv_kwh - load_kwh, 0.0)
    grid_import = np.maximum(load_kwh - pv_kwh, 0.0)

    # Defensive: prevent negative due to float noise
    return {
        "self_consumed_kwh": np.maximum(self_consumed, 0.0),
        "exported_kwh": np.maximum(exported, 0.0),
        "grid_import_kwh": np.maximum(grid_import, 0.0),
    }


def compute_tariff_a_metrics(
    total_load_kwh: float,
    total_grid_import_kwh: float,
    total_exported_kwh: float,
    import_tariff_gbp_per_kwh: float,
    export_tariff_gbp_per_kwh: float,
) -> Dict[str, float]:
    """
    Tariff A (flat rates):
      - Baseline cost (no PV): total_load_kwh * import_tariff
      - With PV: total_grid_import_kwh * import_tariff
      - Export revenue: total_exported_kwh * export_tariff
      - Net annual benefit: baseline - with_pv + export_revenue
    """
    baseline_cost = total_load_kwh * import_tariff_gbp_per_kwh
    import_cost_with_pv = total_grid_import_kwh * import_tariff_gbp_per_kwh
    export_revenue = total_exported_kwh * export_tariff_gbp_per_kwh
    net_benefit = baseline_cost - import_cost_with_pv + export_revenue

    effective_bill_with_pv = import_cost_with_pv - export_revenue

    return {
        "baseline_import_cost_gbp": float(baseline_cost),
        "import_cost_with_pv_gbp": float(import_cost_with_pv),
        "export_revenue_gbp": float(export_revenue),
        "net_annual_benefit_gbp": float(net_benefit),
        "effective_bill_with_pv_gbp": float(effective_bill_with_pv),
    }


def safe_ratio_percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return 100.0 * numerator / denominator


# -----------------------------
# Plotting
# -----------------------------
def save_monthly_pv_vs_load_plot(
    monthly_df: pd.DataFrame,
    png_path: Path,
    location_slug: str,
) -> None:
    """
    Plot monthly PV kWh vs load kWh (two lines).
    """
    plt.figure(figsize=(10, 4))
    plt.plot(monthly_df["month"], monthly_df["pv_kwh"], label="Solar production (kWh)")
    plt.plot(monthly_df["month"], monthly_df["load_kwh"], label="Household use (kWh)")
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Month (within year)")
    plt.ylabel("Energy (kWh)")
    plt.title(f"Monthly solar production vs household use — {location_slug}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=150)
    plt.close()


def save_week_timeseries_plot(
    hourly_df: pd.DataFrame,
    png_path: Path,
    location_slug: str,
    week_start_utc: pd.Timestamp,
    week_days: int,
) -> None:
    """
    Plot one week of PV power, load power, and exported power (kW).
    """
    start = week_start_utc
    end = start + pd.Timedelta(days=int(week_days))
    window = hourly_df.loc[(hourly_df.index >= start) & (hourly_df.index < end)].copy()

    if window.empty:
        # Fallback: take first week in dataset
        start = hourly_df.index.min().floor("D")
        end = start + pd.Timedelta(days=int(week_days))
        window = hourly_df.loc[(hourly_df.index >= start) & (hourly_df.index < end)].copy()

    if window.empty:
        friendly_exit(
            "ERROR: Cannot create week plot because no data exists in the selected time window.\n"
            f"Requested start: {week_start_utc}\n"
            f"Data range: {hourly_df.index.min()} to {hourly_df.index.max()}"
        )

    plt.figure(figsize=(12, 4))
    plt.plot(window.index, window["pv_kw"], label="Solar power (kW)")
    plt.plot(window.index, window["load_kw"], label="Household use power (kW)")
    plt.plot(window.index, window["exported_kw"], label="Energy sent to grid power (kW)")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Power (kW)")
    plt.title(f"One-week household and solar power profile — {location_slug} — starting {start.date()}")
    plt.xticks(rotation=30, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=150)
    plt.close()


def save_energy_split_plot(
    annual_self_consumed_kwh: float,
    annual_exported_kwh: float,
    png_path: Path,
    location_slug: str,
) -> None:
    """
    Plot annual split of PV energy: self-consumed vs exported (stacked bar).
    """
    plt.figure(figsize=(6, 4))
    plt.bar(["Annual solar energy"], [annual_self_consumed_kwh], label="Used in the home (kWh)")
    plt.bar(["Annual solar energy"], [annual_exported_kwh], bottom=[annual_self_consumed_kwh], label="Energy sent to grid (kWh)")
    plt.ylabel("Energy (kWh)")
    plt.title(f"Annual solar energy split — {location_slug}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=150)
    plt.close()


# -----------------------------
# Main
# -----------------------------
def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Household PV ROI calculator core (PVWatts-style PV + synthetic load + Tariff A)."
    )

    parser.add_argument("--location", type=str, required=True,
                        help="Location slug used in filename data/raw_<location>.csv (example: warwick_campus).")
    parser.add_argument("--system-kw", type=float, required=True,
                        help="PV system DC size in kW (must be > 0).")
    parser.add_argument("--annual-load-kwh", type=float, required=True,
                        help="Annual household electricity consumption in kWh/year (must be > 0).")
    parser.add_argument("--profile", type=str, required=True, choices=["home_daytime", "away_daytime"],
                        help="Synthetic load profile archetype.")
    parser.add_argument(
        "--seasonal-variance-pct",
        type=float,
        default=30.0,
        help="Seasonal load swing between December and June in percent (default: 30).",
    )
    parser.add_argument("--import-tariff", type=float, required=True,
                        help="Flat import price in £/kWh (must be >= 0).")
    parser.add_argument("--export-tariff", type=float, required=True,
                        help="Flat export price in £/kWh (must be >= 0).")

    # Optional PV model parameters (sane defaults)
    parser.add_argument("--temp-coeff", type=float, default=-0.004,
                        help="Temperature coefficient per °C (default: -0.004 /°C).")
    parser.add_argument("--loss-frac", type=float, default=0.14,
                        help="Lumped system loss fraction (default: 0.14 = 14%%).")
    parser.add_argument("--inverter-eff", type=float, default=0.96,
                        help="Inverter efficiency (default: 0.96).")
    parser.add_argument("--noct", type=float, default=45.0,
                        help="NOCT used for cell temperature estimate in °C (default: 45).")
    parser.add_argument("--inverter-ac-kw", type=float, default=None,
                        help="Optional inverter AC rating for clipping (kW). Default: equals --system-kw.")
    parser.add_argument("--week-start", type=str, default=None,
                        help="Week plot start date in YYYY-MM-DD. Default: June 1 of the dataset year.")
    parser.add_argument("--week-days", type=int, default=7,
                        help="Number of days in week plot (default: 7).")

    return parser


def validate_inputs(args: argparse.Namespace) -> None:
    if args.system_kw <= 0:
        friendly_exit("ERROR: --system-kw must be > 0")
    if args.annual_load_kwh <= 0:
        friendly_exit("ERROR: --annual-load-kwh must be > 0")
    if args.import_tariff < 0:
        friendly_exit("ERROR: --import-tariff must be >= 0")
    if args.export_tariff < 0:
        friendly_exit("ERROR: --export-tariff must be >= 0")
    if args.seasonal_variance_pct < 20 or args.seasonal_variance_pct > 40:
        friendly_exit("ERROR: --seasonal-variance-pct must be between 20 and 40")

    if not (0.0 <= args.loss_frac < 1.0):
        friendly_exit("ERROR: --loss-frac must be in [0, 1)")
    if not (0.0 < args.inverter_eff <= 1.0):
        friendly_exit("ERROR: --inverter-eff must be in (0, 1]")
    if args.week_days < 1 or args.week_days > 31:
        friendly_exit("ERROR: --week-days must be between 1 and 31")


def pick_default_week_start(index_utc: pd.DatetimeIndex) -> pd.Timestamp:
    """
    Default to June 1 of the dataset start year, otherwise fall back to the first date in data.
    """
    year = int(index_utc.min().year)
    candidate = pd.Timestamp(f"{year}-06-01", tz="UTC")
    if candidate < index_utc.min() or candidate > index_utc.max():
        return index_utc.min().floor("D")
    return candidate


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    validate_inputs(args)

    repo_root = get_repo_root()
    location_slug = slugify_location(args.location)

    csv_path = repo_root / "data" / f"raw_{location_slug}.csv"
    outputs_dir = repo_root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Load PVGIS data
    # -----------------------------
    print("\nLoading PVGIS cached CSV...")
    print(f"  {csv_path}")
    df = load_pvgis_cached_csv(csv_path)

    # If poa_global is missing but components exist, build it (helps some PVGIS exports)
    poa_parts = ["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse"]
    if "poa_global" not in df.columns and all(c in df.columns for c in poa_parts):
        df["poa_global"] = df["poa_direct"] + df["poa_sky_diffuse"] + df["poa_ground_diffuse"]
        print("Info: Computed 'poa_global' from POA components.")

    irr_col = detect_column(list(df.columns), IRRADIANCE_CANDIDATES)
    temp_col = detect_column(list(df.columns), TEMPERATURE_CANDIDATES)

    if irr_col is None or temp_col is None:
        friendly_exit(
            "ERROR: Required columns not found in the cached CSV.\n\n"
            f"Irradiance candidates (need one): {IRRADIANCE_CANDIDATES}\n"
            f"Temperature candidates (need one): {TEMPERATURE_CANDIDATES}\n\n"
            f"Available columns ({len(df.columns)}): {list(df.columns)}\n\n"
            "Fix: Ensure your cached PVGIS CSV includes one irradiance and one temperature column."
        )

    print("\nDetected columns:")
    print(f"  Irradiance:  {irr_col}  (expected units: W/m²)")
    print(f"  Temperature: {temp_col} (expected units: °C)")

    irradiance = ensure_numeric_irradiance(df[irr_col], irr_col)
    temp_air = ensure_numeric_temperature(df[temp_col], temp_col)

    # -----------------------------
    # Compute PV AC power + energy
    # -----------------------------
    dt_hours = compute_timestep_hours(df.index)
    dt_hours_values = dt_hours.values.astype(float)

    inverter_ac_kw = float(args.inverter_ac_kw) if args.inverter_ac_kw is not None else float(args.system_kw)

    pv_kw = compute_pv_ac_power_kw_pvwatts(
        irradiance_w_per_m2=irradiance.values.astype(float),
        temp_air_c=temp_air.values.astype(float),
        system_kw_dc=float(args.system_kw),
        temp_coeff_per_c=float(args.temp_coeff),
        loss_frac=float(args.loss_frac),
        inverter_eff=float(args.inverter_eff),
        inverter_ac_kw=inverter_ac_kw,
        noct_c=float(args.noct),
    )
    pv_kw = np.maximum(pv_kw, 0.0)
    pv_kwh = np.maximum(pv_kw * dt_hours_values, 0.0)

    # -----------------------------
    # Generate + scale household load
    # -----------------------------
    load_weights = generate_hourly_load_weights(
        df.index,
        profile_name=args.profile,
        seasonal_variance_pct=float(args.seasonal_variance_pct),
    )
    load_kw, load_kwh = scale_load_to_annual_kwh(
        load_weights_kw_relative=load_weights,
        dt_hours=dt_hours_values,
        annual_load_kwh=float(args.annual_load_kwh),
    )

    # -----------------------------
    # Compute self-consumption / export / import
    # -----------------------------
    flows = compute_energy_flows(pv_kwh=pv_kwh, load_kwh=load_kwh)

    # Build hourly dataframe (keep power columns for plotting too)
    hourly = pd.DataFrame(index=df.index.copy())
    hourly["pv_kw"] = pv_kw
    hourly["load_kw"] = load_kw
    hourly["pv_kwh"] = pv_kwh
    hourly["load_kwh"] = load_kwh
    hourly["self_consumed_kwh"] = flows["self_consumed_kwh"]
    hourly["exported_kwh"] = flows["exported_kwh"]
    hourly["grid_import_kwh"] = flows["grid_import_kwh"]

    # Exported power for the week plot (kW)
    hourly["exported_kw"] = np.where(
        dt_hours_values > 0,
        hourly["exported_kwh"].values / dt_hours_values,
        0.0
    )
    hourly["exported_kw"] = hourly["exported_kw"].clip(lower=0.0)

    # -----------------------------
    # Monthly aggregation
    # -----------------------------
    monthly_sum = hourly[["pv_kwh", "load_kwh", "self_consumed_kwh", "exported_kwh", "grid_import_kwh"]].resample("MS").sum()
    monthly = monthly_sum.copy()
    monthly.insert(0, "month", monthly.index.strftime("%Y-%m"))
    monthly = monthly.reset_index(drop=True)

    # -----------------------------
    # Annual totals + ratios + Tariff A
    # -----------------------------
    total_pv_kwh = float(hourly["pv_kwh"].sum())
    total_load_kwh = float(hourly["load_kwh"].sum())
    total_self_kwh = float(hourly["self_consumed_kwh"].sum())
    total_export_kwh = float(hourly["exported_kwh"].sum())
    total_import_kwh = float(hourly["grid_import_kwh"].sum())

    self_consumption_ratio_pct = safe_ratio_percent(total_self_kwh, total_pv_kwh)
    export_ratio_pct = safe_ratio_percent(total_export_kwh, total_pv_kwh)

    tariff = compute_tariff_a_metrics(
        total_load_kwh=total_load_kwh,
        total_grid_import_kwh=total_import_kwh,
        total_exported_kwh=total_export_kwh,
        import_tariff_gbp_per_kwh=float(args.import_tariff),
        export_tariff_gbp_per_kwh=float(args.export_tariff),
    )

    # Period check (helpful warning)
    total_hours = float(np.sum(dt_hours_values))
    if total_hours < 8600 or total_hours > 8900:
        print(
            f"\nWARNING: The dataset covers about {total_hours:.1f} hours (a typical year is ~8760 hours). "
            "Outputs are computed over the available period, but the load scaling targets the provided annual kWh."
        )

    # -----------------------------
    # Save CSV outputs
    # -----------------------------
    hourly_energy_csv = outputs_dir / f"hourly_energy_{location_slug}.csv"
    monthly_summary_csv = outputs_dir / f"monthly_summary_{location_slug}.csv"

    hourly_energy_out = hourly[["pv_kwh", "load_kwh", "self_consumed_kwh", "exported_kwh", "grid_import_kwh"]].copy()
    hourly_energy_out.insert(0, "timestamp", hourly_energy_out.index)
    hourly_energy_out.to_csv(hourly_energy_csv, index=False)

    monthly[["month", "pv_kwh", "load_kwh", "self_consumed_kwh", "exported_kwh", "grid_import_kwh"]].to_csv(
        monthly_summary_csv, index=False
    )

    # -----------------------------
    # Create plots
    # -----------------------------
    monthly_plot_png = outputs_dir / f"monthly_pv_vs_load_{location_slug}.png"
    week_plot_png = outputs_dir / f"week_timeseries_{location_slug}.png"
    split_plot_png = outputs_dir / f"energy_split_{location_slug}.png"

    save_monthly_pv_vs_load_plot(monthly_df=monthly, png_path=monthly_plot_png, location_slug=location_slug)

    if args.week_start is not None:
        try:
            week_start = pd.Timestamp(args.week_start)
        except Exception:
            friendly_exit(
                f"ERROR: --week-start must look like YYYY-MM-DD. Got: {args.week_start}"
            )

        if week_start.tzinfo is None:
            week_start = week_start.tz_localize("UTC")
        else:
            week_start = week_start.tz_convert("UTC")
    else:
        week_start = pick_default_week_start(hourly.index)

    save_week_timeseries_plot(
        hourly_df=hourly,
        png_path=week_plot_png,
        location_slug=location_slug,
        week_start_utc=week_start,
        week_days=int(args.week_days),
    )

    save_energy_split_plot(
        annual_self_consumed_kwh=total_self_kwh,
        annual_exported_kwh=total_export_kwh,
        png_path=split_plot_png,
        location_slug=location_slug,
    )

    # -----------------------------
    # Print summary block
    # -----------------------------
    print("\n" + "=" * 78)
    print("PV ROI Summary — Tariff A (flat import/export)")
    print("=" * 78)
    print(f"Location:                 {location_slug}")
    print(f"PV system size (DC):      {args.system_kw:.2f} kW")
    print(f"Load profile:             {args.profile}")
    print(f"Annual load target:       {args.annual_load_kwh:,.0f} kWh/year")
    print("")
    print("PV model assumptions:")
    print(f"  Lumped losses:          {args.loss_frac * 100:.1f}%")
    print(f"  Inverter efficiency:    {args.inverter_eff:.3f}")
    print(f"  Temperature coeff:      {args.temp_coeff:.4f} per °C")
    print(f"  NOCT:                   {args.noct:.1f} °C")
    print(f"  Inverter clipping:      {inverter_ac_kw:.2f} kW AC")
    print("")
    print("Energy totals (kWh):")
    print(f"  PV generation:          {total_pv_kwh:,.1f}")
    print(f"  Household load:         {total_load_kwh:,.1f}")
    print(f"  Self-consumed PV:       {total_self_kwh:,.1f}  ({self_consumption_ratio_pct:.1f}% of PV)")
    print(f"  Exported PV:            {total_export_kwh:,.1f}  ({export_ratio_pct:.1f}% of PV)")
    print(f"  Grid import with PV:    {total_import_kwh:,.1f}")
    print("")
    print("Tariffs (£/kWh):")
    print(f"  Import price:           {args.import_tariff:.3f}")
    print(f"  Export price:           {args.export_tariff:.3f}")
    print("")
    print("Bills (£):")
    print(f"  Baseline (no PV) import cost:  {tariff['baseline_import_cost_gbp']:,.2f}")
    print(f"  Import cost with PV:           {tariff['import_cost_with_pv_gbp']:,.2f}")
    print(f"  Export revenue:                {tariff['export_revenue_gbp']:,.2f}")
    print(f"  Effective bill with PV:        {tariff['effective_bill_with_pv_gbp']:,.2f}")
    print(f"  Net annual benefit:            {tariff['net_annual_benefit_gbp']:,.2f}")
    print("=" * 78)

    # -----------------------------
    # Print saved outputs
    # -----------------------------
    print("\nSaved outputs:")
    print(f"  CSV  Hourly energy:   {hourly_energy_csv}")
    print(f"  CSV  Monthly summary: {monthly_summary_csv}")
    print(f"  PNG  Monthly PV vs load: {monthly_plot_png}")
    print(f"  PNG  Week timeseries:    {week_plot_png}")
    print(f"  PNG  Annual energy split:{split_plot_png}")
    print("")


if __name__ == "__main__":
    main()
