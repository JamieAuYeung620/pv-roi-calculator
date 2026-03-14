from __future__ import annotations

import pytest

from src.config_schema import PVROIRunConfig, validate_config


def test_sensitivity_block_is_backwards_compatible_by_default():
    cfg = PVROIRunConfig.from_dict({})

    assert cfg.sensitivity.enabled is False
    assert cfg.sensitivity.capex_values is None
    assert cfg.sensitivity.discount_rate_values is None
    assert cfg.sensitivity.tariff_multipliers is None

    validate_config(cfg)


def test_sensitivity_block_validates_numeric_ranges():
    cfg = PVROIRunConfig.from_dict(
        {
            "sensitivity": {
                "enabled": True,
                "capex_values": [4500, 6000],
                "discount_rate_values": [0.02, 0.05],
                "tariff_multipliers": [0.9, 1.1],
            }
        }
    )

    validate_config(cfg)

    cfg_bad = PVROIRunConfig.from_dict(
        {
            "sensitivity": {
                "enabled": True,
                "capex_values": [4500, -1],
            }
        }
    )

    with pytest.raises(ValueError, match="sensitivity.capex_values"):
        validate_config(cfg_bad)
