# src/pipeline_runner.py
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from config_schema import PVROIRunConfig, load_config_json, make_default_config, save_config_json, validate_config
from run_manager import init_run, slugify, float_to_slug, repo_root


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


def ensure_pvgis_data(cfg: PVROIRunConfig, run_dir: Path, logger) -> Tuple[Path, str]:
    """
    Ensure data/raw_<location>.csv exists (for compatibility with roi_calculator_core.py),
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
    cache_path = cache_dir / f"raw_{location_slug}_{cfg.location.year}_lat{lat_slug}_lon{lon_slug}.csv"

    # 1) Prefer cache if it exists
    if cache_path.exists() and not cfg.location.force_download:
        logger.info("PVGIS: Using cache file: %s", cache_path)
        shutil.copy2(cache_path, raw_path)
        source = f"cache:{cache_path.name}"

    # 2) If no cache, but raw_path exists (from your older workflow), bootstrap cache
    elif raw_path.exists() and not cfg.location.force_download:
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
            "--location", location_slug,
        ]
        if cfg.location.force_download:
            cmd.append("--force")

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


def copy_outputs_into_run(cfg: PVROIRunConfig, run_dir: Path, logger) -> Dict[str, Path]:
    """
    Copy + rename outputs into the run folder using the NON-NEGOTIABLE spec.

    Returns a dict of key output paths in the run folder.
    """
    root = repo_root()
    location_slug = slugify(cfg.location.name)

    src_outputs = root / "outputs"

    # Files produced by roi_calculator_core.py :contentReference[oaicite:3]{index=3}
    core_hourly = src_outputs / f"hourly_energy_{location_slug}.csv"
    core_monthly = src_outputs / f"monthly_summary_{location_slug}.csv"
    plot_monthly = src_outputs / f"monthly_pv_vs_load_{location_slug}.png"
    plot_week = src_outputs / f"week_timeseries_{location_slug}.png"
    plot_split = src_outputs / f"energy_split_{location_slug}.png"

    # Files produced by roi_calculator_finance.py :contentReference[oaicite:4]{index=4}
    fin_summary = src_outputs / f"financial_summary_{location_slug}.csv"
    plot_cum = src_outputs / f"cumulative_cashflow_comparison_{location_slug}.png"
    plot_bars = src_outputs / f"annual_cashflow_bars_{location_slug}.png"

    # Destination paths (run folder spec)
    dst_hourly = run_dir / "outputs" / "hourly_energy.csv"
    dst_monthly = run_dir / "outputs" / "monthly_summary.csv"
    dst_fin = run_dir / "outputs" / "financial_summary.csv"

    dst_plots_dir = run_dir / "outputs" / "plots"
    dst_plots_dir.mkdir(parents=True, exist_ok=True)

    dst_plot_monthly = dst_plots_dir / "monthly_pv_vs_load.png"
    dst_plot_week = dst_plots_dir / "week_timeseries.png"
    dst_plot_split = dst_plots_dir / "energy_split.png"
    dst_plot_cum = dst_plots_dir / "cumulative_cashflow.png"
    dst_plot_bars = dst_plots_dir / "annual_cashflow_bars.png"

    # Copy helper
    def must_copy(src: Path, dst: Path) -> None:
        if not src.exists():
            raise FileNotFoundError(
                f"Expected output not found:\n  {src}\n"
                "Fix: check logs.txt to see why the step failed, and confirm you're running from project_root/."
            )
        shutil.copy2(src, dst)
        logger.info("Copied: %s -> %s", src, dst)

    must_copy(core_hourly, dst_hourly)
    must_copy(core_monthly, dst_monthly)
    must_copy(fin_summary, dst_fin)

    must_copy(plot_monthly, dst_plot_monthly)
    must_copy(plot_week, dst_plot_week)
    must_copy(plot_split, dst_plot_split)
    must_copy(plot_cum, dst_plot_cum)
    must_copy(plot_bars, dst_plot_bars)

    return {
        "hourly_energy_csv": dst_hourly,
        "monthly_summary_csv": dst_monthly,
        "financial_summary_csv": dst_fin,
        "plot_monthly": dst_plot_monthly,
        "plot_week": dst_plot_week,
        "plot_split": dst_plot_split,
        "plot_cumulative": dst_plot_cum,
        "plot_cashflow_bars": dst_plot_bars,
    }


def write_summary_md(cfg: PVROIRunConfig, run_dir: Path, outputs: Dict[str, Path], pvgis_source: str, logger) -> Path:
    """
    Write runs/<run_id>/report/summary.md listing key metrics + file paths.
    """
    hourly_path = outputs["hourly_energy_csv"]
    fin_path = outputs["financial_summary_csv"]

    hourly = pd.read_csv(hourly_path)

    # Totals (kWh)
    total_pv = float(hourly["pv_kwh"].sum())
    total_load = float(hourly["load_kwh"].sum())
    total_self = float(hourly["self_consumed_kwh"].sum())
    total_export = float(hourly["exported_kwh"].sum())
    total_import = float(hourly["grid_import_kwh"].sum())

    self_consumption_pct = (100.0 * total_self / total_pv) if total_pv > 0 else 0.0
    self_sufficiency_pct = (100.0 * total_self / total_load) if total_load > 0 else 0.0

    # Tariff A annual bill math (recomputed from energy totals)
    import_price = float(cfg.tariffs.tariffA_import)
    export_price = float(cfg.tariffs.tariffA_export)

    baseline_bill = total_load * import_price
    bill_with_pv = total_import * import_price - total_export * export_price
    savings_a = baseline_bill - bill_with_pv

    # Finance summary (Tariff A vs B)
    fin = pd.read_csv(fin_path).iloc[0].to_dict()

    def money(x: Any) -> str:
        try:
            return f"£{float(x):,.2f}"
        except Exception:
            return str(x)

    def pct(x: Any) -> str:
        try:
            return f"{100.0 * float(x):.1f}%"
        except Exception:
            return str(x)

    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "summary.md"

    # Relative-ish paths for readability
    rel = lambda p: str(p.relative_to(run_dir))

    lines = []
    lines.append("# PV ROI Demo Summary\n")
    lines.append(f"- **Run ID:** `{cfg.meta.run_id}`")
    lines.append(f"- **Created (local):** `{cfg.meta.created_at_local}`")
    lines.append(f"- **PVGIS source:** `{pvgis_source}`\n")

    lines.append("## Inputs\n")
    lines.append(f"- **Location name:** {cfg.location.name}")
    lines.append(f"- **Lat/Lon:** {cfg.location.lat}, {cfg.location.lon}")
    lines.append(f"- **Year:** {cfg.location.year}")
    lines.append(f"- **PV system size:** {cfg.pv.system_kw} kW")
    lines.append(f"- **Annual load target:** {cfg.load.annual_load_kwh} kWh/year")
    lines.append(f"- **Load profile:** {cfg.load.profile}\n")

    lines.append("## Key results (energy)\n")
    lines.append(f"- **PV generation:** {total_pv:,.1f} kWh")
    lines.append(f"- **Household load:** {total_load:,.1f} kWh")
    lines.append(f"- **Self-consumed PV:** {total_self:,.1f} kWh ({self_consumption_pct:.1f}% of PV)")
    lines.append(f"- **Exported PV:** {total_export:,.1f} kWh")
    lines.append(f"- **Grid import with PV:** {total_import:,.1f} kWh")
    lines.append(f"- **Self-sufficiency:** {self_sufficiency_pct:.1f}% of load met by PV\n")

    lines.append("## Key results (Tariff A quick check)\n")
    lines.append(f"- **Tariff A import/export:** {import_price:.3f} / {export_price:.3f} £/kWh")
    lines.append(f"- **Baseline bill (no PV):** {money(baseline_bill)}")
    lines.append(f"- **Bill with PV:** {money(bill_with_pv)}")
    lines.append(f"- **Annual savings (recomputed):** {money(savings_a)}\n")

    lines.append("## Key results (Finance model: Tariff A vs B)\n")
    lines.append(f"- **Annual savings (Tariff A):** {money(fin.get('annual_savings_tariffA_gbp'))}")
    lines.append(f"- **Annual savings (Tariff B):** {money(fin.get('annual_savings_tariffB_gbp'))}")
    lines.append(f"- **Payback (Tariff A):** {fin.get('payback_year_tariffA')}")
    lines.append(f"- **Payback (Tariff B):** {fin.get('payback_year_tariffB')}")
    lines.append(f"- **NPV (Tariff A):** {money(fin.get('npv_tariffA'))}")
    lines.append(f"- **NPV (Tariff B):** {money(fin.get('npv_tariffB'))}")
    lines.append(f"- **ROI (Tariff A):** {pct(fin.get('roi_tariffA'))}")
    lines.append(f"- **ROI (Tariff B):** {pct(fin.get('roi_tariffB'))}\n")

    lines.append("## Output files in this run folder\n")
    lines.append(f"- `{rel(outputs['hourly_energy_csv'])}`")
    lines.append(f"- `{rel(outputs['monthly_summary_csv'])}`")
    lines.append(f"- `{rel(outputs['financial_summary_csv'])}`")
    lines.append(f"- `{rel(outputs['plot_monthly'])}`")
    lines.append(f"- `{rel(outputs['plot_week'])}`")
    lines.append(f"- `{rel(outputs['plot_split'])}`")
    lines.append(f"- `{rel(outputs['plot_cumulative'])}`")
    lines.append(f"- `{rel(outputs['plot_cashflow_bars'])}`")
    lines.append(f"- `logs.txt`")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote summary: %s", summary_path)

    return summary_path


def run_pipeline(cfg: PVROIRunConfig) -> Path:
    """
    Main entry point required by the project:
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

    # 2) Core step (uses data/raw_<location>.csv and writes to outputs/) :contentReference[oaicite:5]{index=5}
    location_slug = slugify(cfg.location.name)

    core_cmd = [
        sys.executable, "src/roi_calculator_core.py",
        "--location", location_slug,
        "--system-kw", str(cfg.pv.system_kw),
        "--annual-load-kwh", str(cfg.load.annual_load_kwh),
        "--profile", str(cfg.load.profile),
        "--import-tariff", str(cfg.tariffs.tariffA_import),
        "--export-tariff", str(cfg.tariffs.tariffA_export),
        "--temp-coeff", str(cfg.pv.temp_coeff),
        "--loss-frac", str(cfg.pv.loss_frac),
        "--inverter-eff", str(cfg.pv.inverter_eff),
        "--noct", str(cfg.pv.noct),
        "--week-days", str(cfg.load.week_days),
    ]
    if cfg.pv.inverter_ac_kw is not None:
        core_cmd += ["--inverter-ac-kw", str(cfg.pv.inverter_ac_kw)]
    if cfg.load.week_start is not None:
        core_cmd += ["--week-start", str(cfg.load.week_start)]

    rc = run_subprocess(core_cmd, cwd=root, logger=logger)
    if rc != 0:
        raise RuntimeError(f"Core step failed. See logs: {run_dir / 'logs.txt'}")

    # 3) Finance step (reads outputs/hourly_energy_<location>.csv) :contentReference[oaicite:6]{index=6}
    fin_cmd = [
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

        "--tariffA-import", str(cfg.tariffs.tariffA_import),
        "--tariffA-export", str(cfg.tariffs.tariffA_export),

        "--tariffB-peak", str(cfg.tariffs.tariffB_peak),
        "--tariffB-offpeak", str(cfg.tariffs.tariffB_offpeak),
        "--tariffB-export", str(cfg.tariffs.tariffB_export),

        "--peak-start", str(cfg.tariffs.peak_start),
        "--peak-end", str(cfg.tariffs.peak_end),
    ]

    rc = run_subprocess(fin_cmd, cwd=root, logger=logger)
    if rc != 0:
        raise RuntimeError(f"Finance step failed. See logs: {run_dir / 'logs.txt'}")

    # 4) Copy/rename outputs into the run folder spec
    outputs = copy_outputs_into_run(cfg, run_dir, logger)

    # 5) Write summary.md into runs/<run_id>/report/
    write_summary_md(cfg, run_dir, outputs, pvgis_source=pvgis_source, logger=logger)

    logger.info("✅ Pipeline complete. Run folder: %s", run_dir)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo backbone runner (creates runs/<run_id>/...).")
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
