from __future__ import annotations
from pathlib import Path
import re


import argparse
import sys
from typing import List, Optional, Tuple
from datetime import datetime, timezone



PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/"  # pinned PVGIS API version

# We will accept any ONE of these irradiance columns (preferred first)
IRRADIANCE_CANDIDATES = ["poa_global", "ghi", "G(h)", "G(i)"]

# We will accept any ONE of these temperature columns (preferred first)
TEMPERATURE_CANDIDATES = ["temp_air", "T2m"]

def repo_root() -> Path:
    # src/pvgis_pipeline.py -> project root is one folder up from src/
    return Path(__file__).resolve().parent.parent


def slugify_location(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("Location name becomes empty after cleaning. Use a different --location.")
    return s


def load_cached_csv(csv_path: Path):
    """
    Load cached CSV and return a DataFrame indexed by timezone-aware UTC timestamps.
    """
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "timestamp" not in df.columns:
        raise ValueError(f"Cached CSV missing 'timestamp' column: {csv_path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp")
    return df


def save_csv(df, csv_path: Path) -> None:
    """
    Save DataFrame to CSV with a 'timestamp' column (UTC).
    """
    out = df.copy()
    out.insert(0, "timestamp", df.index)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(csv_path, index=False)



def pick_existing_column(available: List[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in available:
            return c
    return None


def fetch_pvgis_hourly(
    lat: float,
    lon: float,
    year: int,
    surface_tilt_deg: float = 30.0,
    surface_azimuth_deg: float = 180.0,
):
    """
    Fetch one full year of hourly PVGIS data using pvlib.
    Returns a pandas DataFrame indexed by time.
    """
    try:
        import pandas as pd
        from pvlib.iotools import get_pvgis_hourly
    except Exception as e:
        print("ERROR: Missing required packages (pandas/pvlib).")
        print("Fix: Activate your venv, then run: python -m pip install -r requirements.txt")
        print("Details:", repr(e))
        sys.exit(1)

    try:
        result = get_pvgis_hourly(
            latitude=lat,
            longitude=lon,
            start=year,
            end=year,
            surface_tilt=surface_tilt_deg,
            # Keep UI/PVGIS convention aligned: 180° = south-facing.
            surface_azimuth=surface_azimuth_deg,
            components=True,
            pvcalculation=False,   # we want weather-like data, not PV output
            map_variables=True,    # gives nicer column names like 'ghi', 'temp_air'
            url=PVGIS_URL,
            timeout=60,
        )
    except Exception as e:
        print("ERROR: PVGIS fetch failed.")
        print("Possible causes: PVGIS temporary outage, network/VPN, wrong coordinates.")
        print("Details:", repr(e))
        sys.exit(1)

    # pvlib can return (data, meta) or (data, meta, inputs) depending on version
    data = result[0]
    meta = result[1] if len(result) > 1 else None

    if not hasattr(data, "index"):
        print("ERROR: PVGIS returned unexpected data format.")
        sys.exit(1)

    # Ensure timestamp index is timezone-aware UTC (for consistent plotting later)
    if getattr(data.index, "tz", None) is None:
        data.index = data.index.tz_localize("UTC")
    else:
        data.index = data.index.tz_convert("UTC")

    return data, meta


def fetch_pvgis_pvcalc_hourly(
    lat: float,
    lon: float,
    year: int,
    surface_tilt_deg: float,
    surface_azimuth_deg: float,
    peakpower_kw: float,
    loss_percent: float,
):
    """
    Fetch hourly PV output from PVGIS using built-in PV calculation mode.
    Returns (dataframe, metadata-like object) with UTC index.
    """
    try:
        from pvlib.iotools import get_pvgis_hourly
    except Exception as e:
        print("ERROR: Missing required packages (pvlib).")
        print("Details:", repr(e))
        sys.exit(1)

    result = get_pvgis_hourly(
        latitude=lat,
        longitude=lon,
        start=year,
        end=year,
        surface_tilt=surface_tilt_deg,
        surface_azimuth=surface_azimuth_deg,
        pvcalculation=True,
        peakpower=peakpower_kw,
        loss=loss_percent,
        map_variables=True,
        url=PVGIS_URL,
        timeout=60,
    )

    data = result[0]
    meta = result[1] if len(result) > 1 else None

    if getattr(data.index, "tz", None) is None:
        data.index = data.index.tz_localize("UTC")
    else:
        data.index = data.index.tz_convert("UTC")

    return data, meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: Fetch PVGIS hourly data and print a preview.")
    parser.add_argument("--lat", type=float, default=52.3840, help="Latitude (Warwick campus default).")
    parser.add_argument("--lon", type=float, default=-1.5615, help="Longitude (Warwick campus default).")
    parser.add_argument("--year", type=int, default=2020, help="Year to fetch (default: 2021).")
    parser.add_argument("--surface-tilt", type=float, default=0.0, help="PVGIS surface tilt in degrees (default: 0.0).")
    parser.add_argument("--surface-azimuth", type=float, default=180.0, help="PVGIS surface azimuth in degrees (default: 180.0).")
    parser.add_argument("--location", type=str, default="warwick_campus", help="Used for output filename raw_<location>.csv")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached CSV exists.")
    parser.add_argument("--window-start", type=str, default=None, help="Plot window start (YYYY-MM-DD). Default: <year>-06-01")
    parser.add_argument("--window-days", type=int, default=7, help="Number of days to plot (default: 7)")


    args = parser.parse_args()

    # Basic input validation
    if not (-90 <= args.lat <= 90):
        raise ValueError("Latitude must be between -90 and 90.")
    if not (-180 <= args.lon <= 180):
        raise ValueError("Longitude must be between -180 and 180.")
    if not (2005 <= args.year <= 2023):
        raise ValueError("Year must be between 2005 and 2023.")
    if not (0.0 <= args.surface_tilt <= 90.0):
        raise ValueError("Surface tilt must be between 0 and 90.")
    if not (0.0 <= args.surface_azimuth <= 360.0):
        raise ValueError("Surface azimuth must be between 0 and 360.")
    # ---- Step 3: define location + CSV path early (avoid scope issues) ----
    location_slug = slugify_location(args.location)
    csv_path = repo_root() / "data" / f"raw_{location_slug}.csv"

    csv_path = repo_root() / "data" / f"raw_{location_slug}.csv"

    if csv_path.exists() and not args.force:
        print(f"\nLoading cached CSV: {csv_path}")
        data = load_cached_csv(csv_path)
        meta = None
    else:
        data, meta = fetch_pvgis_hourly(
            args.lat, args.lon, args.year,
            surface_tilt_deg=args.surface_tilt,
            surface_azimuth_deg=args.surface_azimuth,
        )

        # If PVGIS returned POA components, create poa_global for Day 1 plotting
        poa_parts = ["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse"]
        if "poa_global" not in data.columns and all(c in data.columns for c in poa_parts):
            data["poa_global"] = data["poa_direct"] + data["poa_sky_diffuse"] + data["poa_ground_diffuse"]
            print("\nComputed column: poa_global = poa_direct + poa_sky_diffuse + poa_ground_diffuse")

        save_csv(data, csv_path)
        print(f"Saved cached CSV: {csv_path}")

    
        # If PVGIS returned POA components, create poa_global for Day 1 plotting
    poa_parts = ["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse"]
    if "poa_global" not in data.columns and all(c in data.columns for c in poa_parts):
        data["poa_global"] = data["poa_direct"] + data["poa_sky_diffuse"] + data["poa_ground_diffuse"]
        print("\nComputed column: poa_global = poa_direct + poa_sky_diffuse + poa_ground_diffuse")


    print("\n✅ PVGIS fetch succeeded.")
    print(f"- Rows: {len(data):,}")
    print(f"- Time range (UTC): {data.index.min()}  to  {data.index.max()}")
    print(f"- Columns ({len(list(data.columns))}): {list(data.columns)}")

    # Quick self-check: do we have usable irradiance + temperature columns?
    irr_col = pick_existing_column(list(data.columns), IRRADIANCE_CANDIDATES)
    temp_col = pick_existing_column(list(data.columns), TEMPERATURE_CANDIDATES)

    print("\nColumn check (required for Day 1):")
    print(f"- Irradiance column found: {irr_col}")
    print(f"- Temperature column found: {temp_col}")

    if irr_col is None or temp_col is None:
        print("\nERROR: Required columns not found.")
        print("Irradiance candidates:", IRRADIANCE_CANDIDATES)
        print("Temperature candidates:", TEMPERATURE_CANDIDATES)
        print("Available columns:", list(data.columns))
        sys.exit(1)

    print("\nPreview (first 5 rows of the two key columns):")
    print(data[[irr_col, temp_col]].head())
        # ---- Step 4: Plot a 7-day window and save PNGs ----
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception as e:
        print("ERROR: Missing plotting dependencies (matplotlib/pandas).")
        print("Fix: python -m pip install -r requirements.txt")
        print("Details:", repr(e))
        sys.exit(1)

    if args.window_days < 1 or args.window_days > 31:
        raise ValueError("--window-days must be between 1 and 31.")

    window_start = args.window_start or f"{args.year}-06-01"
    try:
        start = pd.Timestamp(window_start)
    except Exception as e:
        raise ValueError(f"--window-start must look like YYYY-MM-DD. Got: {window_start}") from e

    # Make start UTC to match the dataframe index
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")

    end = start + pd.Timedelta(days=args.window_days)
    end_label = (end - pd.Timedelta(days=1)).date()

    # If poa_global isn't present (e.g., older cached file), compute it
    poa_parts = ["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse"]
    if "poa_global" not in data.columns and all(c in data.columns for c in poa_parts):
        data["poa_global"] = data["poa_direct"] + data["poa_sky_diffuse"] + data["poa_ground_diffuse"]
        print("Computed column (for plotting): poa_global")

    # Pick columns again for plotting (defensive)
    irr_col = pick_existing_column(list(data.columns), IRRADIANCE_CANDIDATES)
    temp_col = pick_existing_column(list(data.columns), TEMPERATURE_CANDIDATES)
    if irr_col is None or temp_col is None:
        print("ERROR: Cannot plot because required columns are missing.")
        print("Available columns:", list(data.columns))
        sys.exit(1)

    # Slice the window
    dfw = data.loc[(data.index >= start) & (data.index < end), [irr_col, temp_col]].copy()
    if dfw.empty:
        print(f"ERROR: No data in plot window [{start} .. {end}).")
        print(f"Available range: {data.index.min()} to {data.index.max()}")
        sys.exit(1)

    outputs_dir = repo_root() / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    irr_path = outputs_dir / f"irradiance_{location_slug}_{start.date()}_{end_label}.png"
    plt.figure()
    plt.plot(dfw.index, dfw[irr_col])

    plt.xlabel("Time (UTC)")
    plt.ylabel("Irradiance (W/m²)")
    plt.title(f"Irradiance ({irr_col}) — {location_slug} — {start.date()} to {end_label}")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(irr_path, dpi=150)
    plt.close()

    temp_path = outputs_dir / f"temperature_{location_slug}_{start.date()}_{end_label}.png"
    plt.figure()
    plt.plot(dfw.index, dfw[temp_col])
    plt.xlabel("Time (UTC)")
    plt.ylabel("Air temperature (°C)")
    plt.title(f"Temperature ({temp_col}) — {location_slug} — {start.date()} to {end_label}")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(temp_path, dpi=150)
    plt.close()

    print(f"\nSaved plots:\n- {irr_path}\n- {temp_path}")
    print("Plot file exists check:", irr_path.exists(), temp_path.exists())



if __name__ == "__main__":
    main()
