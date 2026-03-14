from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

import src.sensitivity_analysis as sensitivity_analysis
from src.config_schema import PVROIRunConfig


def _write_baseline_root_outputs(root: Path, location_slug: str, savings: float) -> None:
    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    hourly = pd.DataFrame(
        {
            "timestamp": ["2020-01-01T00:00:00Z", "2020-01-01T01:00:00Z"],
            "pv_kwh": [1.0, 0.5],
            "load_kwh": [0.8, 0.9],
            "self_consumed_kwh": [0.8, 0.5],
            "exported_kwh": [0.2, 0.0],
            "grid_import_kwh": [0.0, 0.4],
        }
    )
    hourly.to_csv(outputs_dir / f"hourly_energy_{location_slug}.csv", index=False)

    raw_summary = pd.DataFrame(
        [
            {
                "location": location_slug,
                "system_kw": 4.0,
                "annual_load_kwh": 3200.0,
                "profile": "away_daytime",
                "tariffA_import": 0.28,
                "tariffA_export": 0.15,
                "tariffB_peak": 0.35,
                "tariffB_offpeak": 0.22,
                "tariffB_export": 0.15,
                "tariffC_export": 0.05,
                "annual_pv_kwh": 3750.0,
                "annual_self_consumed_kwh": 1200.0,
                "annual_exported_kwh": 2550.0,
                "annual_savings_tariffA_gbp": savings,
                "annual_savings_tariffB_gbp": savings - 10.0,
                "annual_savings_tariffC_gbp": savings - 20.0,
                "payback_year_tariffA": 9.0,
                "payback_year_tariffB": 10.0,
                "payback_year_tariffC": 11.0,
                "npv_tariffA": 500.0,
                "npv_tariffB": 400.0,
                "npv_tariffC": 300.0,
                "roi_tariffA": 0.5,
                "roi_tariffB": 0.4,
                "roi_tariffC": 0.3,
            }
        ]
    )
    raw_summary.to_csv(outputs_dir / f"financial_summary_{location_slug}.csv", index=False)

    for name in [
        f"annual_cashflow_bars_{location_slug}.png",
        f"cumulative_cashflow_comparison_{location_slug}.png",
        f"cumulative_cashflow_comparison_all_{location_slug}.png",
        f"cumulative_cashflow_tariffA_{location_slug}.png",
        f"cumulative_cashflow_tariffB_{location_slug}.png",
        f"cumulative_cashflow_tariffC_{location_slug}.png",
    ]:
        (outputs_dir / name).write_bytes(b"baseline")


def test_run_sensitivity_analysis_writes_summary_and_restores_root_outputs(tmp_path, monkeypatch):
    location_slug = "warwick_campus"
    baseline_run_dir = tmp_path / "runs" / "baseline_case"
    (baseline_run_dir / "data").mkdir(parents=True, exist_ok=True)
    (baseline_run_dir / "outputs" / "plots").mkdir(parents=True, exist_ok=True)
    (baseline_run_dir / "data" / "raw_pvgis.csv").write_text("timestamp,pv\n2020-01-01T00:00:00Z,1\n", encoding="utf-8")
    (baseline_run_dir / "data" / "pvgis_request.txt").write_text("baseline provenance\n", encoding="utf-8")

    _write_baseline_root_outputs(tmp_path, location_slug, savings=999.0)

    monkeypatch.setattr(sensitivity_analysis, "repo_root", lambda: tmp_path)

    def fake_run_subprocess(cmd: list[str], cwd: Path, logger) -> int:
        args: dict[str, str] = {}
        index = 0
        while index < len(cmd):
            token = cmd[index]
            if token.startswith("--") and index + 1 < len(cmd):
                args[token] = cmd[index + 1]
                index += 2
                continue
            index += 1
        capex = float(args["--capex"])
        discount_rate = float(args["--discount-rate"])
        tariff_a_import = float(args["--tariffA-import"])
        tariff_a_export = float(args["--tariffA-export"])
        location = args["--location"]
        multiplier = tariff_a_import / 0.28

        annual_savings = 700.0 * multiplier
        npv = annual_savings * 12.0 - capex - discount_rate * 1000.0
        payback = capex / annual_savings
        roi = npv / capex

        summary = pd.DataFrame(
            [
                {
                    "location": location,
                    "system_kw": 4.0,
                    "annual_load_kwh": 3200.0,
                    "profile": "away_daytime",
                    "tariffA_import": tariff_a_import,
                    "tariffA_export": tariff_a_export,
                    "tariffB_peak": 0.35,
                    "tariffB_offpeak": 0.22,
                    "tariffB_export": 0.15,
                    "tariffC_export": 0.05,
                    "annual_pv_kwh": 3750.0,
                    "annual_self_consumed_kwh": 1200.0,
                    "annual_exported_kwh": 2550.0,
                    "annual_savings_tariffA_gbp": annual_savings,
                    "annual_savings_tariffB_gbp": annual_savings - 10.0,
                    "annual_savings_tariffC_gbp": annual_savings - 20.0,
                    "payback_year_tariffA": payback,
                    "payback_year_tariffB": payback + 1.0,
                    "payback_year_tariffC": payback + 2.0,
                    "npv_tariffA": npv,
                    "npv_tariffB": npv - 50.0,
                    "npv_tariffC": npv - 100.0,
                    "roi_tariffA": roi,
                    "roi_tariffB": roi - 0.05,
                    "roi_tariffC": roi - 0.10,
                }
            ]
        )
        outputs_dir = tmp_path / "outputs"
        summary.to_csv(outputs_dir / f"financial_summary_{location}.csv", index=False)

        for name in [
            f"annual_cashflow_bars_{location}.png",
            f"cumulative_cashflow_comparison_{location}.png",
            f"cumulative_cashflow_comparison_all_{location}.png",
            f"cumulative_cashflow_tariffA_{location}.png",
            f"cumulative_cashflow_tariffB_{location}.png",
            f"cumulative_cashflow_tariffC_{location}.png",
        ]:
            (outputs_dir / name).write_bytes(b"scenario")
        return 0

    monkeypatch.setattr(sensitivity_analysis, "_run_subprocess", fake_run_subprocess)

    cfg = PVROIRunConfig.from_dict(
        {
            "location": {"name": location_slug},
            "sensitivity": {
                "enabled": True,
                "capex_values": [5000, 6000],
                "discount_rate_values": [0.03, 0.05],
                "tariff_multipliers": [0.9, 1.0],
            },
        }
    )

    logger = logging.getLogger("test.sensitivity")
    logger.handlers = []
    logger.addHandler(logging.NullHandler())

    result = sensitivity_analysis.run_sensitivity_analysis(cfg, baseline_run_dir, logger)

    assert result.summary_csv.exists()
    assert result.capex_plot.exists()
    assert result.discount_rate_plot.exists()
    assert result.tariff_plot.exists()
    assert result.combined_plot.exists()

    summary_df = pd.read_csv(result.summary_csv)
    assert list(summary_df["scenario_group"].unique()) == ["capex", "discount_rate", "tariff_multiplier"]
    assert len(summary_df) == 6
    assert {
        "scenario_group",
        "scenario_label",
        "varied_parameter",
        "parameter_value",
        "capex",
        "discount_rate",
        "tariffA_import",
        "tariffA_export",
        "annual_savings_gbp",
        "payback_year",
        "npv",
        "roi",
        "run_dir",
    }.issubset(summary_df.columns)
    assert summary_df["run_dir"].map(lambda value: Path(value).exists()).all()

    sweep_values = json.loads((result.sensitivity_dir / "sweep_values_used.json").read_text(encoding="utf-8"))
    assert sweep_values["capex_values"] == [5000.0, 6000.0]
    assert sweep_values["discount_rate_values"] == [0.03, 0.05]
    assert sweep_values["tariff_multipliers"] == [0.9, 1.0]

    restored_root_summary = pd.read_csv(tmp_path / "outputs" / f"financial_summary_{location_slug}.csv")
    assert float(restored_root_summary.iloc[0]["annual_savings_tariffA_gbp"]) == 999.0
