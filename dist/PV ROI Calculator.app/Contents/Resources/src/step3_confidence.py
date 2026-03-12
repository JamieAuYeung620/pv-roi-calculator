from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ENERGY_COLS = ["pv_kwh", "load_kwh", "self_consumed_kwh", "exported_kwh", "grid_import_kwh"]


def _fmt(v: Any) -> str:
    try:
        return f"{float(v):.6g}"
    except Exception:
        return str(v)


def compute_verification_checks(hourly_df: pd.DataFrame, system_kw: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    missing = [c for c in ENERGY_COLS if c not in hourly_df.columns]
    if missing:
        return pd.DataFrame(
            [
                {
                    "check_id": "required_columns",
                    "description": "Required hourly energy columns exist",
                    "status": "FAIL",
                    "value": ", ".join(missing),
                    "threshold": "all ENERGY_COLS present",
                    "notes": "Cannot run verification checks without required columns.",
                }
            ]
        )

    tol = 1e-9
    min_val = float(hourly_df[ENERGY_COLS].min().min())
    non_negative_ok = min_val >= -tol
    rows.append(
        {
            "check_id": "non_negative",
            "description": "All energy series are non-negative",
            "status": "PASS" if non_negative_ok else "FAIL",
            "value": _fmt(min_val),
            "threshold": ">= -1e-9 kWh",
            "notes": "Minimum across pv/load/self/export/import columns.",
        }
    )

    pv_split_exceed = (hourly_df["self_consumed_kwh"] + hourly_df["exported_kwh"] - hourly_df["pv_kwh"]).max()
    pv_split_exceed = float(pv_split_exceed)
    pv_split_ok = pv_split_exceed <= 1e-6
    rows.append(
        {
            "check_id": "pv_split",
            "description": "PV split consistency: self-consumed + exported does not exceed PV generation",
            "status": "PASS" if pv_split_ok else "FAIL",
            "value": _fmt(pv_split_exceed),
            "threshold": "max exceedance <= 1e-6 kWh",
            "notes": "Computed row-wise exceedance: (self + export - pv).",
        }
    )

    load_balance_err = (hourly_df["self_consumed_kwh"] + hourly_df["grid_import_kwh"] - hourly_df["load_kwh"]).abs().max()
    load_balance_err = float(load_balance_err)
    load_balance_ok = load_balance_err <= 1e-6
    rows.append(
        {
            "check_id": "load_balance",
            "description": "Load balance: self-consumed + grid import matches load",
            "status": "PASS" if load_balance_ok else "FAIL",
            "value": _fmt(load_balance_err),
            "threshold": "max abs error <= 1e-6 kWh",
            "notes": "Absolute row-wise mismatch.",
        }
    )

    total_pv_kwh = float(hourly_df["pv_kwh"].sum())
    denom = float(system_kw) * 8760.0
    capacity_factor = total_pv_kwh / denom if denom > 0 else np.nan
    cf_ok = np.isfinite(capacity_factor) and (0.0 <= capacity_factor <= 0.35)
    rows.append(
        {
            "check_id": "capacity_factor",
            "description": "Capacity factor is in a reasonable range",
            "status": "PASS" if cf_ok else "FAIL",
            "value": _fmt(capacity_factor),
            "threshold": "0.0 <= CF <= 0.35",
            "notes": "CF = annual PV kWh / (system kW * 8760).",
        }
    )

    return pd.DataFrame(rows, columns=["check_id", "description", "status", "value", "threshold", "notes"])


def write_verification_csv(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)


def summarize_distribution(values: list[float], label: str) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {
            "metric": label,
            "p10": np.nan,
            "p50": np.nan,
            "p90": np.nan,
            "mean": np.nan,
            "std": np.nan,
            "cv": np.nan,
            "n_years": 0,
        }

    p10 = float(np.percentile(arr, 10))
    p50 = float(np.percentile(arr, 50))
    p90 = float(np.percentile(arr, 90))
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=0))
    cv = float(std / mean) if mean != 0 else float("nan")
    return {
        "metric": label,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "mean": mean,
        "std": std,
        "cv": cv,
        "n_years": int(arr.size),
    }


def plot_annual_savings_vs_year(years: list[int], savings: list[float], out_png: Path, title: str) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 4))
    plt.plot(years, savings, marker="o")
    plt.xlabel("Year")
    plt.ylabel("Annual savings (£)")
    plt.title(title)
    plt.figtext(0.01, 0.01, "Historical weather variability (PVGIS year-by-year)", fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(out_png, dpi=150)
    plt.close()


def plot_histogram(
    values: list[float],
    out_png: Path,
    title: str,
    p10: float,
    p50: float,
    p90: float,
    years: list[int] | None = None,
) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    n = int(vals.size)

    plt.figure(figsize=(9, 4))
    if n == 0:
        plt.text(0.5, 0.5, "No data available", ha="center", va="center", transform=plt.gca().transAxes)
    else:
        # Always use a dot view (not bars) so each year's position is visible.
        if years is not None and len(years) == n:
            year_arr = np.asarray(years, dtype=int)
            order = np.argsort(year_arr)
            vals_plot = vals[order]
            years_plot = year_arr[order]
        else:
            vals_plot = np.sort(vals)
            years_plot = None

        band_levels = np.array([-0.075, -0.04, 0.0, 0.04, 0.075], dtype=float)
        y = np.resize(band_levels, n)
        plt.scatter(vals_plot, y, alpha=0.95, s=48)
        plt.ylim(-0.14, 0.14)
        plt.yticks([])
        plt.ylabel("Each dot = one year")
        plt.gca().text(
            0.01,
            0.95,
            "Each dot is one historical weather year.",
            transform=plt.gca().transAxes,
            va="top",
            fontsize=9,
        )

        if years_plot is not None:
            for x, yy, yr in zip(vals_plot, y, years_plot):
                plt.annotate(
                    str(int(yr)),
                    xy=(x, yy),
                    xytext=(0, 7),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )

        plt.axvline(p10, linestyle="--", linewidth=1.2, label=f"10th percentile (cloudier year): £{p10:,.0f}")
        plt.axvline(p50, linestyle="-", linewidth=1.2, label=f"50th percentile (typical year): £{p50:,.0f}")
        plt.axvline(p90, linestyle="--", linewidth=1.2, label=f"90th percentile (very sunny year): £{p90:,.0f}")
        plt.legend(fontsize=8, loc="upper right")
    plt.xlabel("Annual savings (£/year)")
    plt.title(f"{title} (n={n} years)")
    plt.grid(axis="x", alpha=0.2)
    plt.figtext(0.01, 0.01, "Historical weather variability (PVGIS year-by-year)", fontsize=8)
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(out_png, dpi=150)
    plt.close()
