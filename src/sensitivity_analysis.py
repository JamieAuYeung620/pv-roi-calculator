from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

try:
    import pandas as pd
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
except Exception as exc:
    print("ERROR: Missing required packages. Sensitivity analysis requires: pandas, matplotlib")
    print("Fix: Activate your virtual environment, then run:")
    print("  python -m pip install -r requirements.txt")
    print("Details:", repr(exc))
    sys.exit(1)

try:
    from config_schema import PVROIRunConfig, save_config_json, validate_config
    from run_manager import create_run_folder, repo_root, setup_logger, slugify
except ModuleNotFoundError:
    from src.config_schema import PVROIRunConfig, save_config_json, validate_config
    from src.run_manager import create_run_folder, repo_root, setup_logger, slugify


DEFAULT_CAPEX_VALUES = [4000.0, 5000.0, 6000.0, 7000.0, 8000.0]
DEFAULT_DISCOUNT_RATE_VALUES = [0.02, 0.03, 0.05, 0.07, 0.10]
DEFAULT_TARIFF_MULTIPLIERS = [0.80, 0.90, 1.00, 1.10, 1.20]
VALID_SENSITIVITY_TARIFF_MODES = {"A", "B", "C"}


@dataclass
class SensitivityRunResult:
    sensitivity_dir: Path
    summary_csv: Path
    capex_plot: Path
    discount_rate_plot: Path
    tariff_plot: Path
    combined_plot: Path


def _run_subprocess(cmd: list[str], cwd: Path, logger) -> int:
    logger.info("Running command:\n  %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)

    if result.stdout:
        logger.info("----- STDOUT START -----\n%s\n----- STDOUT END -----", result.stdout)
    if result.stderr:
        logger.info("----- STDERR START -----\n%s\n----- STDERR END -----", result.stderr)
    if result.returncode != 0:
        logger.error("Command failed with return code: %s", result.returncode)
    return result.returncode


def _build_fin_cmd(cfg: PVROIRunConfig, location_slug: str) -> list[str]:
    # Mirrors pipeline_runner._build_fin_cmd without importing pipeline_runner
    # to avoid a circular dependency.
    return [
        sys.executable,
        "src/roi_calculator_finance.py",
        "--location",
        location_slug,
        "--system-kw",
        str(cfg.pv.system_kw),
        "--annual-load-kwh",
        str(cfg.load.annual_load_kwh),
        "--profile",
        str(cfg.load.profile),
        "--capex",
        str(cfg.finance.capex),
        "--discount-rate",
        str(cfg.finance.discount_rate),
        "--lifetime",
        str(cfg.finance.lifetime_years),
        "--degradation",
        str(cfg.finance.degradation),
        "--om-frac",
        str(cfg.finance.om_frac),
        "--salvage-value-gbp",
        str(cfg.finance.salvage_value_gbp),
        "--tariffA-import",
        str(cfg.tariffs.tariffA_import),
        "--tariffA-export",
        str(cfg.tariffs.tariffA_export),
        "--tariffB-peak",
        str(cfg.tariffs.tariffB_peak),
        "--tariffB-offpeak",
        str(cfg.tariffs.tariffB_offpeak),
        "--tariffB-export",
        str(cfg.tariffs.tariffB_export),
        "--tariffC-export",
        str(cfg.tariffs.tariffC_export),
        "--peak-start",
        str(cfg.tariffs.peak_start),
        "--peak-end",
        str(cfg.tariffs.peak_end),
    ]


def _load_financial_summary(location_slug: str) -> pd.DataFrame:
    path = repo_root() / "outputs" / f"financial_summary_{location_slug}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing finance output: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Finance summary CSV is empty: {path}")
    return df


def _selected_finance_row(fin_df: pd.DataFrame, tariff_mode: str) -> dict[str, Any]:
    row = fin_df.iloc[0].to_dict()

    if tariff_mode == "A":
        return {
            "tariff_mode": "A",
            "annual_savings_gbp": float(row.get("annual_savings_tariffA_gbp", float("nan"))),
            "payback_year": float(row.get("payback_year_tariffA", float("nan"))),
            "npv": float(row.get("npv_tariffA", float("nan"))),
            "roi": float(row.get("roi_tariffA", float("nan"))),
        }
    if tariff_mode == "B":
        return {
            "tariff_mode": "B",
            "annual_savings_gbp": float(row.get("annual_savings_tariffB_gbp", float("nan"))),
            "payback_year": float(row.get("payback_year_tariffB", float("nan"))),
            "npv": float(row.get("npv_tariffB", float("nan"))),
            "roi": float(row.get("roi_tariffB", float("nan"))),
        }
    if tariff_mode == "C":
        return {
            "tariff_mode": "C",
            "annual_savings_gbp": float(row.get("annual_savings_tariffC_gbp", float("nan"))),
            "payback_year": float(row.get("payback_year_tariffC", float("nan"))),
            "npv": float(row.get("npv_tariffC", float("nan"))),
            "roi": float(row.get("roi_tariffC", float("nan"))),
        }
    raise ValueError(f"Unsupported sensitivity tariff mode: {tariff_mode}")


def _resolve_values(values: list[float] | None, defaults: list[float]) -> list[float]:
    if values is None:
        return [float(v) for v in defaults]
    return [float(v) for v in values]


def _copy_if_exists(src: Path, dst: Path, logger) -> bool:
    if not src.exists():
        logger.warning("Skip copy (missing): %s", src)
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    logger.info("Copied: %s -> %s", src, dst)
    return True


def _parameter_slug(value: float) -> str:
    s = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return s.replace(".", "p").replace("-", "m")


def _clone_cfg(cfg: PVROIRunConfig) -> PVROIRunConfig:
    return PVROIRunConfig.from_dict(cfg.to_dict())


def _finance_plot_paths(location_slug: str, tariff_mode: str) -> dict[str, Path]:
    root_outputs = repo_root() / "outputs"
    selected_mode = tariff_mode if tariff_mode in VALID_SENSITIVITY_TARIFF_MODES else "A"
    return {
        "financial_summary_raw.csv": root_outputs / f"financial_summary_{location_slug}.csv",
        "annual_cashflow_bars.png": root_outputs / f"annual_cashflow_bars_{location_slug}.png",
        "cumulative_cashflow.png": root_outputs / f"cumulative_cashflow_tariff{selected_mode}_{location_slug}.png",
    }


def _baseline_finance_root_artifacts(location_slug: str) -> dict[str, Path]:
    root_outputs = repo_root() / "outputs"
    return {
        "financial_summary.csv": root_outputs / f"financial_summary_{location_slug}.csv",
        "annual_cashflow_bars.png": root_outputs / f"annual_cashflow_bars_{location_slug}.png",
        "cumulative_cashflow_comparison.png": root_outputs / f"cumulative_cashflow_comparison_{location_slug}.png",
        "cumulative_cashflow_comparison_all.png": root_outputs / f"cumulative_cashflow_comparison_all_{location_slug}.png",
        "cumulative_cashflow_tariffA.png": root_outputs / f"cumulative_cashflow_tariffA_{location_slug}.png",
        "cumulative_cashflow_tariffB.png": root_outputs / f"cumulative_cashflow_tariffB_{location_slug}.png",
        "cumulative_cashflow_tariffC.png": root_outputs / f"cumulative_cashflow_tariffC_{location_slug}.png",
    }


def _save_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _configure_plot_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#444444",
            "axes.grid": True,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.7,
            "grid.alpha": 0.8,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
        }
    )


def _format_currency_axis(axis) -> None:
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"£{value:,.0f}"))


def _plot_single_group(
    df: pd.DataFrame,
    group: str,
    out_png: Path,
    baseline_value: float,
) -> Path:
    _configure_plot_style()
    plot_df = df[df["scenario_group"] == group].sort_values("parameter_value").copy()
    if plot_df.empty:
        raise ValueError(f"No sensitivity rows available for group: {group}")

    title_map = {
        "capex": "Sensitivity of NPV to capital cost",
        "discount_rate": "Sensitivity of NPV to discount rate",
        "tariff_multiplier": "Sensitivity of NPV to Tariff A multiplier",
    }
    x_label_map = {
        "capex": "Capital expenditure (£)",
        "discount_rate": "Discount rate",
        "tariff_multiplier": "Tariff A import/export multiplier",
    }

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(
        plot_df["parameter_value"],
        plot_df["npv"],
        color="#1f3a5f",
        marker="o",
        linewidth=1.8,
        markersize=5.5,
        label="NPV",
    )
    ax.axhline(0.0, color="#666666", linewidth=0.9, alpha=0.9)
    ax.axvline(baseline_value, color="#8c8c8c", linewidth=1.0, linestyle="--", label="Baseline")
    ax.set_title(title_map.get(group, "Sensitivity of NPV"))
    ax.set_xlabel(x_label_map.get(group, "Parameter value"))
    ax.set_ylabel("Net present value (£)")
    _format_currency_axis(ax)

    if group == "discount_rate":
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{100.0 * value:.0f}%"))
    elif group == "tariff_multiplier":
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:.2f}x"))
    else:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"£{value:,.0f}"))

    ax.legend(loc="best", frameon=False)
    fig.tight_layout()
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_png


def _plot_combined_payback_npv(
    df: pd.DataFrame,
    baseline_cfg: PVROIRunConfig,
    out_png: Path,
) -> Path:
    _configure_plot_style()
    groups = [
        ("capex", "Capital expenditure (£)", baseline_cfg.finance.capex),
        ("discount_rate", "Discount rate", baseline_cfg.finance.discount_rate),
        ("tariff_multiplier", "Tariff A multiplier", 1.0),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    npv_color = "#1f3a5f"
    payback_color = "#7a7a7a"

    for ax, (group, xlabel, baseline_value) in zip(axes, groups):
        plot_df = df[df["scenario_group"] == group].sort_values("parameter_value").copy()
        if plot_df.empty:
            raise ValueError(f"No sensitivity rows available for group: {group}")

        ax2 = ax.twinx()
        ax.plot(
            plot_df["parameter_value"],
            plot_df["npv"],
            color=npv_color,
            marker="o",
            linewidth=1.8,
            markersize=5,
            label="NPV",
        )
        ax2.plot(
            plot_df["parameter_value"],
            plot_df["payback_year"],
            color=payback_color,
            marker="s",
            linewidth=1.5,
            markersize=4.5,
            linestyle="--",
            label="Simple payback",
        )
        ax.axhline(0.0, color="#666666", linewidth=0.9, alpha=0.9)
        ax.axvline(baseline_value, color="#8c8c8c", linewidth=1.0, linestyle=":")

        ax.set_xlabel(xlabel)
        ax.set_ylabel("NPV (£)", color=npv_color)
        ax2.set_ylabel("Payback (years)", color=payback_color)
        ax.tick_params(axis="y", colors=npv_color)
        ax2.tick_params(axis="y", colors=payback_color)
        _format_currency_axis(ax)

        if group == "discount_rate":
            ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{100.0 * value:.0f}%"))
        elif group == "tariff_multiplier":
            ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value:.2f}x"))
        else:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"£{value:,.0f}"))

        title_map = {
            "capex": "CAPEX",
            "discount_rate": "Discount rate",
            "tariff_multiplier": "Tariff A",
        }
        ax.set_title(title_map[group])

        lines = ax.get_lines() + ax2.get_lines()
        labels = [line.get_label() for line in lines]
        ax.legend(lines, labels, loc="best", frameon=False)

    fig.suptitle("One-at-a-time sensitivity of NPV and simple payback", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_png


def _build_scenarios(
    cfg: PVROIRunConfig,
    tariff_mode: str,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    capex_values = _resolve_values(cfg.sensitivity.capex_values, DEFAULT_CAPEX_VALUES)
    discount_rate_values = _resolve_values(cfg.sensitivity.discount_rate_values, DEFAULT_DISCOUNT_RATE_VALUES)
    tariff_multipliers = _resolve_values(cfg.sensitivity.tariff_multipliers, DEFAULT_TARIFF_MULTIPLIERS)

    for value in capex_values:
        scenarios.append(
            {
                "scenario_group": "capex",
                "scenario_label": f"capex={value:.0f}",
                "varied_parameter": "capex",
                "parameter_value": float(value),
                "apply": lambda cfg_copy, selected=float(value): setattr(cfg_copy.finance, "capex", selected),
            }
        )
    for value in discount_rate_values:
        scenarios.append(
            {
                "scenario_group": "discount_rate",
                "scenario_label": f"discount_rate={value:.4f}",
                "varied_parameter": "discount_rate",
                "parameter_value": float(value),
                "apply": lambda cfg_copy, selected=float(value): setattr(cfg_copy.finance, "discount_rate", selected),
            }
        )
    for value in tariff_multipliers:
        scenarios.append(
            {
                "scenario_group": "tariff_multiplier",
                "scenario_label": f"tariff_multiplier={value:.2f}",
                "varied_parameter": "tariff_multiplier",
                "parameter_value": float(value),
                "apply": lambda cfg_copy, selected=float(value): _apply_tariff_multiplier(cfg_copy, selected),
            }
        )

    for scenario in scenarios:
        scenario["tariff_mode"] = tariff_mode
    return scenarios


def _apply_tariff_multiplier(cfg: PVROIRunConfig, multiplier: float) -> None:
    cfg.tariffs.tariffA_import = float(cfg.tariffs.tariffA_import) * float(multiplier)
    cfg.tariffs.tariffA_export = float(cfg.tariffs.tariffA_export) * float(multiplier)


def _copy_baseline_snapshot_artifacts(
    baseline_run_dir: Path,
    sensitivity_dir: Path,
    location_slug: str,
    logger,
) -> dict[str, Path]:
    artifacts: dict[str, Path] = {}
    baseline_hourly_src = repo_root() / "outputs" / f"hourly_energy_{location_slug}.csv"
    baseline_raw_src = baseline_run_dir / "data" / "raw_pvgis.csv"
    baseline_req_src = baseline_run_dir / "data" / "pvgis_request.txt"

    hourly_dst = sensitivity_dir / "baseline_hourly_energy.csv"
    if _copy_if_exists(baseline_hourly_src, hourly_dst, logger):
        artifacts["baseline_hourly_energy.csv"] = hourly_dst

    raw_dst = sensitivity_dir / "baseline_raw_pvgis.csv"
    if _copy_if_exists(baseline_raw_src, raw_dst, logger):
        artifacts["baseline_raw_pvgis.csv"] = raw_dst

    req_dst = sensitivity_dir / "baseline_pvgis_request.txt"
    if _copy_if_exists(baseline_req_src, req_dst, logger):
        artifacts["baseline_pvgis_request.txt"] = req_dst

    return artifacts


def _backup_root_finance_outputs(location_slug: str, sensitivity_dir: Path, logger) -> Path:
    backup_dir = sensitivity_dir / "baseline_root_outputs"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name, src in _baseline_finance_root_artifacts(location_slug).items():
        _copy_if_exists(src, backup_dir / name, logger)
    return backup_dir


def _restore_root_finance_outputs(location_slug: str, backup_dir: Path, logger) -> None:
    for name, dst in _baseline_finance_root_artifacts(location_slug).items():
        _copy_if_exists(backup_dir / name, dst, logger)


def run_sensitivity_analysis(
    baseline_cfg: PVROIRunConfig | dict[str, Any],
    baseline_run_dir: Path,
    logger,
    tariff_mode_override: str | None = None,
) -> SensitivityRunResult:
    cfg = baseline_cfg if isinstance(baseline_cfg, PVROIRunConfig) else PVROIRunConfig.from_dict(baseline_cfg)
    validate_config(cfg)

    tariff_mode = tariff_mode_override or "A"
    if tariff_mode not in VALID_SENSITIVITY_TARIFF_MODES:
        raise ValueError(
            f"Sensitivity analysis only supports tariff modes {sorted(VALID_SENSITIVITY_TARIFF_MODES)}. Got: {tariff_mode}"
        )

    baseline_run_dir = Path(baseline_run_dir)
    sensitivity_dir = baseline_run_dir / "sensitivity"
    sensitivity_dir.mkdir(parents=True, exist_ok=True)
    scenarios_root = sensitivity_dir / "scenarios"
    scenarios_root.mkdir(parents=True, exist_ok=True)

    location_slug = slugify(cfg.location.name)
    baseline_hourly_path = repo_root() / "outputs" / f"hourly_energy_{location_slug}.csv"
    if not baseline_hourly_path.exists():
        raise FileNotFoundError(
            "Baseline hourly energy file is missing for sensitivity analysis.\n"
            f"Expected: {baseline_hourly_path}"
        )

    baseline_snapshot = sensitivity_dir / "baseline_config_snapshot.json"
    save_config_json(cfg, baseline_snapshot)
    logger.info("Sensitivity baseline config snapshot: %s", baseline_snapshot)

    sweep_values_path = _save_json(
        sensitivity_dir / "sweep_values_used.json",
        {
            "tariff_mode_used": tariff_mode,
            "capex_values": _resolve_values(cfg.sensitivity.capex_values, DEFAULT_CAPEX_VALUES),
            "discount_rate_values": _resolve_values(cfg.sensitivity.discount_rate_values, DEFAULT_DISCOUNT_RATE_VALUES),
            "tariff_multipliers": _resolve_values(cfg.sensitivity.tariff_multipliers, DEFAULT_TARIFF_MULTIPLIERS),
            "baseline_finance": {
                "capex": float(cfg.finance.capex),
                "discount_rate": float(cfg.finance.discount_rate),
            },
            "baseline_tariffA": {
                "tariffA_import": float(cfg.tariffs.tariffA_import),
                "tariffA_export": float(cfg.tariffs.tariffA_export),
            },
            "baseline_run_dir": str(baseline_run_dir),
        },
    )
    logger.info("Sensitivity sweep values: %s", sweep_values_path)

    _copy_baseline_snapshot_artifacts(baseline_run_dir, sensitivity_dir, location_slug, logger)
    baseline_root_backup_dir = _backup_root_finance_outputs(location_slug, sensitivity_dir, logger)

    scenarios = _build_scenarios(cfg, tariff_mode=tariff_mode)
    rows: list[dict[str, Any]] = []

    try:
        for index, scenario in enumerate(scenarios, start=1):
            scenario_dir = create_run_folder(
                run_id=f"scenario_{index:02d}_{scenario['scenario_group']}_{_parameter_slug(scenario['parameter_value'])}",
                base_dir=scenarios_root,
            )
            scenario_cfg = _clone_cfg(cfg)
            scenario_cfg.tariff_mode = str(scenario["tariff_mode"])  # type: ignore[assignment]
            scenario_cfg.sensitivity.enabled = False
            scenario["apply"](scenario_cfg)
            validate_config(scenario_cfg)

            scenario_cfg.meta.run_id = scenario_dir.name
            scenario_cfg.meta.created_at_local = datetime.now().isoformat(timespec="seconds")
            scenario_cfg.meta.notes = (
                f"{scenario_cfg.meta.notes}\nSensitivity scenario: {scenario['scenario_label']}".strip()
                if scenario_cfg.meta.notes
                else f"Sensitivity scenario: {scenario['scenario_label']}"
            )
            save_config_json(scenario_cfg, scenario_dir / "config.json")

            scenario_logger = setup_logger(
                scenario_dir,
                logger_name=f"{getattr(logger, 'name', 'pv_roi')}.sensitivity.{scenario_dir.name}",
            )
            scenario_logger.info("Sensitivity scenario started: %s", scenario["scenario_label"])
            scenario_logger.info("Baseline run dir: %s", baseline_run_dir)

            _copy_if_exists(baseline_hourly_path, scenario_dir / "outputs" / "hourly_energy.csv", scenario_logger)
            _copy_if_exists(baseline_run_dir / "data" / "raw_pvgis.csv", scenario_dir / "data" / "raw_pvgis.csv", scenario_logger)
            _copy_if_exists(
                baseline_run_dir / "data" / "pvgis_request.txt",
                scenario_dir / "data" / "pvgis_request.txt",
                scenario_logger,
            )

            rc = _run_subprocess(_build_fin_cmd(scenario_cfg, location_slug), cwd=repo_root(), logger=scenario_logger)
            if rc != 0:
                raise RuntimeError(
                    f"Finance step failed in sensitivity mode for scenario {scenario['scenario_label']}."
                )

            raw_fin_df = _load_financial_summary(location_slug)
            raw_fin_path = scenario_dir / "outputs" / "financial_summary_raw.csv"
            raw_fin_df.to_csv(raw_fin_path, index=False)

            selected_fin = _selected_finance_row(raw_fin_df, tariff_mode=str(scenario_cfg.tariff_mode))
            scenario_fin_row = {
                "location": location_slug,
                "system_kw": float(scenario_cfg.pv.system_kw),
                "annual_load_kwh": float(scenario_cfg.load.annual_load_kwh),
                "profile": str(scenario_cfg.load.profile),
                "tariff_mode": selected_fin["tariff_mode"],
                "tariffA_import": float(scenario_cfg.tariffs.tariffA_import),
                "tariffA_export": float(scenario_cfg.tariffs.tariffA_export),
                "annual_pv_kwh": float(raw_fin_df.iloc[0].get("annual_pv_kwh", float("nan"))),
                "annual_self_consumed_kwh": float(raw_fin_df.iloc[0].get("annual_self_consumed_kwh", float("nan"))),
                "annual_exported_kwh": float(raw_fin_df.iloc[0].get("annual_exported_kwh", float("nan"))),
                "annual_savings_gbp": float(selected_fin["annual_savings_gbp"]),
                "payback_year": float(selected_fin["payback_year"]),
                "npv": float(selected_fin["npv"]),
                "roi": float(selected_fin["roi"]),
            }
            scenario_fin_df = pd.DataFrame([scenario_fin_row])
            scenario_fin_path = scenario_dir / "outputs" / "financial_summary.csv"
            scenario_fin_df.to_csv(scenario_fin_path, index=False)

            finance_artifacts = _finance_plot_paths(location_slug, tariff_mode=str(scenario_cfg.tariff_mode))
            _copy_if_exists(
                finance_artifacts["annual_cashflow_bars.png"],
                scenario_dir / "outputs" / "plots" / "annual_cashflow_bars.png",
                scenario_logger,
            )
            _copy_if_exists(
                finance_artifacts["cumulative_cashflow.png"],
                scenario_dir / "outputs" / "plots" / "cumulative_cashflow.png",
                scenario_logger,
            )

            rows.append(
                {
                    "scenario_group": scenario["scenario_group"],
                    "scenario_label": scenario["scenario_label"],
                    "varied_parameter": scenario["varied_parameter"],
                    "parameter_value": float(scenario["parameter_value"]),
                    "capex": float(scenario_cfg.finance.capex),
                    "discount_rate": float(scenario_cfg.finance.discount_rate),
                    "tariffA_import": float(scenario_cfg.tariffs.tariffA_import),
                    "tariffA_export": float(scenario_cfg.tariffs.tariffA_export),
                    "annual_savings_gbp": float(selected_fin["annual_savings_gbp"]),
                    "payback_year": float(selected_fin["payback_year"]),
                    "npv": float(selected_fin["npv"]),
                    "roi": float(selected_fin["roi"]),
                    "run_dir": str(scenario_dir),
                }
            )
            logger.info("Sensitivity scenario complete: %s -> %s", scenario["scenario_label"], scenario_dir)
    finally:
        _restore_root_finance_outputs(location_slug, baseline_root_backup_dir, logger)

    summary_df = pd.DataFrame(rows).sort_values(["scenario_group", "parameter_value", "scenario_label"]).reset_index(drop=True)
    summary_csv = sensitivity_dir / "sensitivity_summary.csv"
    summary_df.to_csv(summary_csv, index=False)
    logger.info("Sensitivity summary written: %s", summary_csv)

    capex_plot = _plot_single_group(summary_df, "capex", sensitivity_dir / "sensitivity_capex.png", cfg.finance.capex)
    discount_rate_plot = _plot_single_group(
        summary_df,
        "discount_rate",
        sensitivity_dir / "sensitivity_discount_rate.png",
        cfg.finance.discount_rate,
    )
    tariff_plot = _plot_single_group(summary_df, "tariff_multiplier", sensitivity_dir / "sensitivity_tariff.png", 1.0)
    combined_plot = _plot_combined_payback_npv(
        summary_df,
        baseline_cfg=cfg,
        out_png=sensitivity_dir / "sensitivity_payback_npv.png",
    )

    return SensitivityRunResult(
        sensitivity_dir=sensitivity_dir,
        summary_csv=summary_csv,
        capex_plot=capex_plot,
        discount_rate_plot=discount_rate_plot,
        tariff_plot=tariff_plot,
        combined_plot=combined_plot,
    )
