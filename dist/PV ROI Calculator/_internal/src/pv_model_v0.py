from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path
from typing import List, Optional, Tuple

# Keep these consistent with Day 1 (same candidates, preferred first)
# Day 1 uses: ["poa_global", "ghi", "G(h)", "G(i)"] and ["temp_air", "T2m"]
IRRADIANCE_CANDIDATES = ["poa_global", "ghi", "G(h)", "G(i)"]
TEMPERATURE_CANDIDATES = ["temp_air", "T2m"]

G_STC_W_PER_M2 = 1000.0  # Standard Test Condition irradiance
T_REF_C = 25.0           # Standard Test Condition temperature


def repo_root() -> Path:
    # src/pv_model_v0.py -> repo root is one folder up from src/
    return Path(__file__).resolve().parent.parent


def slugify_location(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("Location name becomes empty after cleaning. Use a different --location.")
    return s


def pick_existing_column(available: List[str], candidates: List[str]) -> Optional[str]:
    """Return the first candidate that exists in available, else None."""
    for c in candidates:
        if c in available:
            return c
    return None


def load_cached_csv(csv_path: Path):
    """
    Load cached PVGIS CSV and return a DataFrame indexed by timezone-aware UTC timestamps.
    Requires a 'timestamp' column.
    """
    try:
        import pandas as pd
    except Exception as e:
        print("ERROR: pandas is not installed.")
        print("Fix: Activate your venv and run: python -m pip install -r requirements.txt")
        print("Details:", repr(e))
        sys.exit(1)

    if not csv_path.exists():
        print(f"ERROR: Cannot find cached CSV at: {csv_path}")
        print("Fix: Run Day 1 to generate it, e.g.:")
        print("  python src/day1_pvgis_pipeline.py --location warwick_campus --year 2020")
        sys.exit(1)

    df = pd.read_csv(csv_path)

    if "timestamp" not in df.columns:
        print("ERROR: Cached CSV is missing the required 'timestamp' column.")
        print(f"File: {csv_path}")
        print(f"Available columns: {list(df.columns)}")
        print("Fix: Re-run Day 1 to regenerate the CSV.")
        sys.exit(1)

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        bad = int(df["timestamp"].isna().sum())
        print("ERROR: Some timestamps could not be parsed.")
        print(f"Bad timestamp rows: {bad}")
        print("Fix: Re-run Day 1; do not manually edit the timestamp column.")
        sys.exit(1)

    df = df.set_index("timestamp").sort_index()
    return df


def ensure_numeric(series, name: str):
    """Convert a column to numeric safely; crash with a helpful error if it fails."""
    import pandas as pd

    out = pd.to_numeric(series, errors="coerce")
    if out.isna().all():
        print(f"ERROR: Column '{name}' could not be converted to numeric values.")
        print("Fix: Check you selected the right column and that the CSV is not corrupted.")
        sys.exit(1)
    # Fill occasional NaNs by assuming 0 (safe for irradiance/power at night)
    return out.fillna(0.0)


def estimate_cell_temperature_c(
    temp_air_c,
    irradiance_w_per_m2,
    noct_c: float,
) :
    """
    Simple NOCT-style cell temperature estimate:
      T_cell = T_air + (NOCT - 20) / 800 * G

    This is a common simple approximation when you only have air temp + irradiance.
    """
    return temp_air_c + ((noct_c - 20.0) / 800.0) * irradiance_w_per_m2


def pvwatts_power_ac_kw(
    irradiance_w_per_m2,
    temp_air_c,
    system_kw_dc: float,
    temp_coeff_per_c: float,
    system_loss_frac: float,
    inverter_eff: float,
    inverter_ac_kw: float,
    noct_c: float,
):
    """
    PV generation model v0 (PVWatts-style):

    1) DC power scales linearly with irradiance relative to STC (1000 W/m^2)
    2) Apply temperature derate using a single coefficient
    3) Apply a single lumped system loss factor
    4) Convert DC -> AC using inverter efficiency, then clip to inverter rating
    """
    import numpy as np

    # Clip irradiance (defensive) — real irradiance should not be negative
    G = np.maximum(irradiance_w_per_m2, 0.0)

    # Estimate cell temperature and temperature factor
    T_cell = estimate_cell_temperature_c(temp_air_c, G, noct_c=noct_c)
    temp_factor = 1.0 + temp_coeff_per_c * (T_cell - T_REF_C)
    temp_factor = np.maximum(temp_factor, 0.0)  # avoid negative power

    # DC power at module/inverter input (kW)
    p_dc_kw = system_kw_dc * (G / G_STC_W_PER_M2) * temp_factor

    # Apply lumped losses (wiring/soiling/mismatch/etc.)
    p_dc_net_kw = p_dc_kw * (1.0 - system_loss_frac)

    # Convert to AC and clip to inverter rating
    p_ac_kw = p_dc_net_kw * inverter_eff
    p_ac_kw = np.minimum(p_ac_kw, inverter_ac_kw)

    # Final defensive clip
    p_ac_kw = np.maximum(p_ac_kw, 0.0)
    return p_ac_kw


def main() -> None:
    parser = argparse.ArgumentParser(description="PV model v0 (PVWatts-style) from cached PVGIS CSV.")
    parser.add_argument("--location", type=str, default="warwick_campus",
                        help="Location slug used in Day 1 filename raw_<location>.csv (default: warwick_campus).")
    parser.add_argument("--system-kw", type=float, default=4.0,
                        help="PV system DC size in kW (typical household 1–5 kW). Default: 4.0")
    parser.add_argument("--loss-frac", type=float, default=0.14,
                        help="Lumped system loss fraction (0.14 = 14%% losses). Default: 0.14")
    parser.add_argument("--inv-eff", type=float, default=0.96,
                        help="Inverter efficiency (0.96 = 96%%). Default: 0.96")
    parser.add_argument("--temp-coeff", type=float, default=-0.004,
                        help="Temperature coefficient per °C (typical -0.003 to -0.005). Default: -0.004")
    parser.add_argument("--noct", type=float, default=45.0,
                        help="Nominal Operating Cell Temperature (°C) used for cell temp estimate. Default: 45")
    parser.add_argument("--week-start", type=str, default=None,
                        help="Start date for 1-week plot (YYYY-MM-DD). Default: <data_year>-06-01")
    parser.add_argument("--week-days", type=int, default=7,
                        help="Days to plot for week timeseries. Default: 7")

    args = parser.parse_args()

    if args.system_kw <= 0:
        print("ERROR: --system-kw must be > 0")
        sys.exit(1)

    if not (0.0 <= args.loss_frac < 1.0):
        print("ERROR: --loss-frac must be in [0, 1)")
        sys.exit(1)

    if not (0.0 < args.inv_eff <= 1.0):
        print("ERROR: --inv-eff must be in (0, 1]")
        sys.exit(1)

    if args.week_days < 1 or args.week_days > 31:
        print("ERROR: --week-days must be between 1 and 31")
        sys.exit(1)

    try:
        import pandas as pd
        import numpy as np
        import matplotlib.pyplot as plt
    except Exception as e:
        print("ERROR: Missing packages (pandas/numpy/matplotlib).")
        print("Fix: Activate your venv and run: python -m pip install -r requirements.txt")
        print("Details:", repr(e))
        sys.exit(1)

    location_slug = slugify_location(args.location)
    csv_path = repo_root() / "data" / f"raw_{location_slug}.csv"

    print("\nPV model v0")
    print(f"- Loading cached CSV: {csv_path}")
    df = load_cached_csv(csv_path)

    # If poa_global missing but components exist, compute it (helps older cached files)
    poa_parts = ["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse"]
    if "poa_global" not in df.columns and all(c in df.columns for c in poa_parts):
        df["poa_global"] = df["poa_direct"] + df["poa_sky_diffuse"] + df["poa_ground_diffuse"]
        print("Computed column: poa_global = poa_direct + poa_sky_diffuse + poa_ground_diffuse")

    irr_col = pick_existing_column(list(df.columns), IRRADIANCE_CANDIDATES)
    temp_col = pick_existing_column(list(df.columns), TEMPERATURE_CANDIDATES)

    if irr_col is None or temp_col is None:
        print("\nERROR: Required columns not found in the cached CSV.")
        print("Irradiance candidates (need one):", IRRADIANCE_CANDIDATES)
        print("Temperature candidates (need one):", TEMPERATURE_CANDIDATES)
        print("Available columns:", list(df.columns))
        print("\nFix options:")
        print("1) Re-run Day 1 with --force to regenerate the CSV.")
        print("2) Check you are using the correct raw_<location>.csv file.")
        sys.exit(1)

    print("\nColumn selection:")
    print(f"- Irradiance column: {irr_col}  (expected units: W/m²)")
    print(f"- Temperature column: {temp_col} (expected units: °C)")

    G = ensure_numeric(df[irr_col], irr_col)
    T_air = ensure_numeric(df[temp_col], temp_col)

    # Inverter rating (simple v0 assumption): equal to DC size
    inverter_ac_kw = float(args.system_kw)

    p_ac_kw = pvwatts_power_ac_kw(
        irradiance_w_per_m2=G.values,
        temp_air_c=T_air.values,
        system_kw_dc=float(args.system_kw),
        temp_coeff_per_c=float(args.temp_coeff),
        system_loss_frac=float(args.loss_frac),
        inverter_eff=float(args.inv_eff),
        inverter_ac_kw=inverter_ac_kw,
        noct_c=float(args.noct),
    )

    # Build output dataframe
    out = pd.DataFrame(index=df.index.copy())
    out["pv_ac_kw"] = p_ac_kw

    # Compute timestep hours robustly (should be ~1 hour)
    dt_hours = out.index.to_series().diff().dt.total_seconds().div(3600.0)
    dt_hours = dt_hours.fillna(dt_hours.median())
    # If something weird happens (all NaN), default to 1 hour
    if not np.isfinite(dt_hours).any():
        dt_hours[:] = 1.0

    out["pv_ac_kwh"] = out["pv_ac_kw"] * dt_hours.values

    annual_kwh = float(out["pv_ac_kwh"].sum())

    # Monthly table (month start)
    monthly = out["pv_ac_kwh"].resample("MS").sum()
    monthly_kwh = pd.DataFrame({
        "month": monthly.index.strftime("%Y-%m"),
        "pv_kwh": monthly.values,
    })

    # --- Sanity checks (prints warnings, does not crash) ---
    print("\nSanity checks:")
    neg_count = int((out["pv_ac_kw"] < -1e-9).sum())
    print(f"- Negative power values: {neg_count} (expected 0)")

    # winter vs summer check (use max summer month vs min winter month)
    if len(monthly) >= 12:
        summer_max = float(monthly.loc[monthly.index.month.isin([5, 6, 7])].max())
        winter_min = float(monthly.loc[monthly.index.month.isin([11, 12, 1, 2])].min())
        print(f"- Summer month max (May/Jun/Jul): {summer_max:.1f} kWh")
        print(f"- Winter month min (Nov/Dec/Jan/Feb): {winter_min:.1f} kWh")
        print(f"- Winter < Summer? {'YES' if winter_min < summer_max else 'WARNING: check irradiance column/units'}")
    else:
        print("- Winter vs summer check skipped (dataset not a full year).")

    per_kw = annual_kwh / float(args.system_kw)
    print(f"- Annual yield per kW: {per_kw:.0f} kWh/kW-year (UK order-of-magnitude ~700–1200)")

    # --- Save outputs ---
    outputs_dir = repo_root() / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    hourly_csv = outputs_dir / f"hourly_ac_power_{location_slug}.csv"
    hourly_out = out.copy()
    hourly_out.insert(0, "timestamp", hourly_out.index)
    hourly_out.to_csv(hourly_csv, index=False)

    monthly_csv = outputs_dir / f"monthly_kwh_{location_slug}.csv"
    monthly_kwh.to_csv(monthly_csv, index=False)

    # Monthly bar chart
    monthly_png = outputs_dir / f"monthly_kwh_bar_{location_slug}.png"
    plt.figure()
    plt.bar(monthly_kwh["month"], monthly_kwh["pv_kwh"])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("PV energy (kWh)")
    plt.title(f"Monthly PV Energy (AC) — {location_slug} — {args.system_kw:.1f} kW system")
    plt.tight_layout()
    plt.savefig(monthly_png, dpi=150)
    plt.close()

    # One-week timeseries plot
    data_year = int(out.index.min().year)
    week_start_str = args.week_start or f"{data_year}-06-01"
    try:
        start = pd.Timestamp(week_start_str)
    except Exception:
        print(f"ERROR: --week-start must look like YYYY-MM-DD. Got: {week_start_str}")
        sys.exit(1)

    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")

    end = start + pd.Timedelta(days=int(args.week_days))
    week = out.loc[(out.index >= start) & (out.index < end)].copy()

    if week.empty:
        print("\nERROR: No data found in the requested week window.")
        print(f"Requested: {start} to {end}")
        print(f"Available: {out.index.min()} to {out.index.max()}")
        sys.exit(1)

    week_png = outputs_dir / f"week_ac_power_{location_slug}.png"
    plt.figure()
    plt.plot(week.index, week["pv_ac_kw"])
    plt.xlabel("Time (UTC)")
    plt.ylabel("PV AC Power (kW)")
    plt.title(f"One-week PV AC Power — {location_slug} — starting {start.date()}")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(week_png, dpi=150)
    plt.close()

    # --- Print final results clearly ---
    print("\nResults:")
    print(f"- Annual PV energy (AC): {annual_kwh:,.0f} kWh")
    print("\nMonthly kWh (AC):")
    print(monthly_kwh.to_string(index=False, formatters={"pv_kwh": lambda x: f"{x:,.1f}"}))

    print("\n✅ Saved:")
    print(f"- Hourly power+energy CSV: {hourly_csv}")
    print(f"- Monthly kWh CSV:        {monthly_csv}")
    print(f"- Monthly bar chart PNG:  {monthly_png}")
    print(f"- Week timeseries PNG:    {week_png}")


if __name__ == "__main__":
    main()
