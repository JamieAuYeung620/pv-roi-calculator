from __future__ import annotations

from pathlib import Path
import sys


# PVGIS via pvlib
DATA_SOURCE = "PVGIS via pvlib.get_pvgis_hourly"

# We will accept any ONE of these irradiance columns (preferred first)
IRRADIANCE_CANDIDATES = ["ghi", "poa_global", "G(h)", "G(i)"]

# We will accept any ONE of these temperature columns (preferred first)
TEMPERATURE_CANDIDATES = ["temp_air", "T2m"]

# Default UK location: Warwick campus (approx)
DEFAULT_LOCATION_NAME = "warwick_campus"
DEFAULT_LAT = 52.3840
DEFAULT_LON = -1.5615

# Default year for Day 1 (use a past year to avoid incomplete current-year data)
DEFAULT_YEAR = 2021


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    print("Step 1: Setup check for Day 1 data pipeline\n")

    # 1) Check required folders exist
    root = repo_root()
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    src_dir = root / "src"

    print("Folder checks:")
    print(f"- repo root: {root}")
    print(f"- data/ exists: {data_dir.exists()}")
    print(f"- outputs/ exists: {outputs_dir.exists()}")
    print(f"- src/ exists: {src_dir.exists()}")

    missing = [p for p in [data_dir, outputs_dir, src_dir] if not p.exists()]
    if missing:
        print("\nERROR: Missing folders:", [str(p) for p in missing])
        print("Create them in VS Code Explorer (or mkdir) and re-run this step.")
        sys.exit(1)

    # 2) Check imports (defensive)
    print("\nPackage import checks:")
    try:
        import pandas as pd  # noqa: F401
        import numpy as np  # noqa: F401
        import matplotlib  # noqa: F401
        import requests  # noqa: F401
        import pvlib  # noqa: F401
        from pvlib.iotools import get_pvgis_hourly  # noqa: F401
    except Exception as e:
        print("ERROR: Failed to import required packages.")
        print("Details:", repr(e))
        print("\nFix: Activate your venv, then run:")
        print("  python -m pip install -r requirements.txt")
        sys.exit(1)

    # 3) Print plan summary (this is our “contract” for Day 1)
    print("\nDay 1 plan summary:")
    print(f"- Data source: {DATA_SOURCE}")
    print(f"- Location: {DEFAULT_LOCATION_NAME} (lat={DEFAULT_LAT}, lon={DEFAULT_LON})")
    print(f"- Year: {DEFAULT_YEAR}")
    print(f"- Irradiance columns we will accept: {IRRADIANCE_CANDIDATES}")
    print(f"- Temperature columns we will accept: {TEMPERATURE_CANDIDATES}")

    # 4) Define expected output paths (no download yet)
    expected_csv = data_dir / f"raw_{DEFAULT_LOCATION_NAME}.csv"
    print("\nExpected outputs (later steps will create these):")
    print(f"- CSV: {expected_csv}")
    print("- PNGs: outputs/irradiance_<...>.png and outputs/temperature_<...>.png")

    print("\n✅ Step 1 PASS: Environment + plan look good.")


if __name__ == "__main__":
    main()
