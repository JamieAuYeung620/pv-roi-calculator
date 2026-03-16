from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.load_model import (
    DEFAULT_ARCHETYPE_PATH,
    EMPIRICAL_PROFILE_IDS,
    load_empirical_archetypes,
    resolve_profile_alias,
    generate_empirical_hourly_load_weights,
)
from src.roi_calculator_core import scale_load_to_annual_kwh


def test_default_archetype_asset_loads() -> None:
    archetypes = load_empirical_archetypes(DEFAULT_ARCHETYPE_PATH)

    assert archetypes["load_model_version"] == "uk_empirical_v1"
    assert set(EMPIRICAL_PROFILE_IDS).issubset(archetypes["archetypes"].keys())


@pytest.mark.parametrize("profile_name", EMPIRICAL_PROFILE_IDS)
def test_empirical_profiles_scale_exactly_to_target_annual_load(profile_name: str) -> None:
    archetypes = load_empirical_archetypes(DEFAULT_ARCHETYPE_PATH)
    index_utc = pd.date_range("2021-01-01", "2022-01-01", tz="UTC", freq="h", inclusive="left")

    weights = generate_empirical_hourly_load_weights(index_utc, profile_name, archetypes)
    load_kw, load_kwh = scale_load_to_annual_kwh(
        load_weights_kw_relative=weights,
        dt_hours=np.ones(len(index_utc), dtype=float),
        annual_load_kwh=3200.0,
    )

    assert np.isclose(load_kwh.sum(), 3200.0, atol=1e-9)
    assert np.all(load_kw >= 0.0)
    assert np.all(load_kwh >= 0.0)


def test_local_time_lookup_uses_europe_london_without_mutating_utc_index() -> None:
    archetypes = load_empirical_archetypes(DEFAULT_ARCHETYPE_PATH)
    index_utc = pd.DatetimeIndex(
        [
            pd.Timestamp("2021-01-06T08:00:00Z"),
            pd.Timestamp("2021-07-07T08:00:00Z"),
        ]
    )
    original_index = index_utc.copy()

    weights = generate_empirical_hourly_load_weights(
        index_utc=index_utc,
        profile_name="empirical_evening_peaked",
        archetypes=archetypes,
    )

    january_expected = archetypes["archetypes"]["empirical_evening_peaked"]["weights"]["1"]["weekday"][8]
    july_expected = archetypes["archetypes"]["empirical_evening_peaked"]["weights"]["7"]["weekday"][9]

    assert weights[0] == pytest.approx(january_expected)
    assert weights[1] == pytest.approx(july_expected)
    assert index_utc.equals(original_index)


def test_invalid_profile_name_fails_cleanly() -> None:
    with pytest.raises(ValueError, match="Unsupported load profile"):
        resolve_profile_alias("not_a_real_profile")
