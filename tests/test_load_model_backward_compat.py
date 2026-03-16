from __future__ import annotations

import argparse

from src.config_schema import PVROIRunConfig, validate_config
from src.load_model import resolve_profile_alias
from src.roi_calculator_finance import validate_inputs as validate_finance_inputs


def test_legacy_aliases_resolve_to_empirical_profiles() -> None:
    assert resolve_profile_alias("away_daytime") == "empirical_evening_peaked"
    assert resolve_profile_alias("home_daytime") == "empirical_daytime_occupied"


def test_config_schema_accepts_legacy_aliases_and_ignored_seasonal_field() -> None:
    cfg = PVROIRunConfig.from_dict(
        {
            "load": {
                "profile": "away_daytime",
                "seasonal_variance_pct": 5,
            }
        }
    )

    validate_config(cfg)


def test_finance_validation_accepts_new_profile_ids_and_legacy_aliases() -> None:
    common_kwargs = {
        "system_kw": 4.0,
        "annual_load_kwh": 3200.0,
        "capex": 6000.0,
        "lifetime": 15,
        "discount_rate": 0.05,
        "degradation": 0.005,
        "om_frac": 0.01,
        "tariffA_import": 0.28,
        "tariffA_export": 0.15,
        "tariffB_peak": 0.35,
        "tariffB_offpeak": 0.22,
        "tariffB_export": 0.15,
        "tariffC_export": 0.05,
        "peak_start": 16,
        "peak_end": 19,
    }

    validate_finance_inputs(argparse.Namespace(profile="empirical_balanced", **common_kwargs))
    validate_finance_inputs(argparse.Namespace(profile="away_daytime", **common_kwargs))
