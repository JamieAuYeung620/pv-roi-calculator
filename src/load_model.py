from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOAD_MODEL_VERSION = "uk_empirical_v1"
ARCHETYPE_SCHEMA_VERSION = "1.0"
DEFAULT_TIMEZONE_NAME = "Europe/London"
DEFAULT_PROFILE = "empirical_evening_peaked"

EMPIRICAL_PROFILE_IDS: tuple[str, ...] = (
    "empirical_evening_peaked",
    "empirical_daytime_occupied",
    "empirical_balanced",
)

LEGACY_PROFILE_ALIASES: dict[str, str] = {
    "away_daytime": "empirical_evening_peaked",
    "home_daytime": "empirical_daytime_occupied",
}

PROFILE_LABELS: dict[str, str] = {
    "empirical_evening_peaked": "Evening-peaked household",
    "empirical_daytime_occupied": "Daytime-occupied household",
    "empirical_balanced": "Balanced household",
}

ALL_ALLOWED_PROFILE_IDS: tuple[str, ...] = EMPIRICAL_PROFILE_IDS + tuple(LEGACY_PROFILE_ALIASES.keys())
DAY_TYPE_ORDER: tuple[str, str] = ("weekday", "weekend")
DAY_TYPE_TO_INDEX = {"weekday": 0, "weekend": 1}

DEFAULT_ARCHETYPE_PATH = Path(__file__).resolve().parent.parent / "data" / "load_archetypes_uk_v1.json"


def allowed_profile_ids() -> tuple[str, ...]:
    return ALL_ALLOWED_PROFILE_IDS


def canonical_profile_ids() -> tuple[str, ...]:
    return EMPIRICAL_PROFILE_IDS


def format_allowed_profiles() -> str:
    return ", ".join(ALL_ALLOWED_PROFILE_IDS)


def is_supported_profile(profile_name: str) -> bool:
    try:
        resolve_profile_alias(profile_name)
    except ValueError:
        return False
    return True


def resolve_profile_alias(profile_name: str) -> str:
    normalized = str(profile_name).strip()
    if normalized in EMPIRICAL_PROFILE_IDS:
        return normalized
    if normalized in LEGACY_PROFILE_ALIASES:
        return LEGACY_PROFILE_ALIASES[normalized]
    raise ValueError(
        f"Unsupported load profile '{profile_name}'. Allowed values: {format_allowed_profiles()}"
    )


def profile_label(profile_name: str) -> str:
    return PROFILE_LABELS[resolve_profile_alias(profile_name)]


def _validate_vector(raw_vector: Any, context: str) -> np.ndarray:
    vector = np.asarray(raw_vector, dtype=float)
    if vector.shape != (24,):
        raise ValueError(f"{context} must contain exactly 24 hourly weights.")
    if not np.isfinite(vector).all():
        raise ValueError(f"{context} contains non-finite values.")
    if (vector <= 0.0).any():
        raise ValueError(f"{context} must contain strictly positive weights.")
    return vector.astype(float)


@lru_cache(maxsize=4)
def load_empirical_archetypes(path: Path = DEFAULT_ARCHETYPE_PATH) -> dict[str, Any]:
    asset_path = Path(path)
    if not asset_path.exists():
        raise FileNotFoundError(
            "Missing load archetype asset: "
            f"{asset_path}\n"
            "Build it with: python3 scripts/build_empirical_load_archetypes.py "
            "--input /path/to/london-smart-meter-dataset"
        )

    payload = json.loads(asset_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != ARCHETYPE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported load archetype schema_version '{payload.get('schema_version')}'. "
            f"Expected {ARCHETYPE_SCHEMA_VERSION}."
        )

    archetypes = payload.get("archetypes")
    if not isinstance(archetypes, dict):
        raise ValueError("Load archetype asset is missing the 'archetypes' mapping.")

    for profile_id in EMPIRICAL_PROFILE_IDS:
        profile_payload = archetypes.get(profile_id)
        if not isinstance(profile_payload, dict):
            raise ValueError(f"Load archetype asset is missing profile '{profile_id}'.")

        fallback = profile_payload.get("fallback", {})
        for day_type in DAY_TYPE_ORDER:
            if day_type not in fallback:
                raise ValueError(f"Profile '{profile_id}' is missing fallback '{day_type}'.")
            _validate_vector(fallback[day_type], f"{profile_id}.fallback.{day_type}")

        weights = profile_payload.get("weights")
        if not isinstance(weights, dict):
            raise ValueError(f"Profile '{profile_id}' is missing the 'weights' section.")

        for month in range(1, 13):
            month_payload = weights.get(str(month))
            if not isinstance(month_payload, dict):
                raise ValueError(f"Profile '{profile_id}' is missing month '{month}'.")
            for day_type in DAY_TYPE_ORDER:
                if day_type not in month_payload:
                    raise ValueError(f"Profile '{profile_id}' month '{month}' is missing '{day_type}'.")
                _validate_vector(
                    month_payload[day_type],
                    f"{profile_id}.weights.{month}.{day_type}",
                )

    return payload


def _build_profile_lookup(profile_payload: dict[str, Any]) -> np.ndarray:
    lookup = np.zeros((12, 2, 24), dtype=float)
    fallback = profile_payload["fallback"]
    fallback_weekday = _validate_vector(fallback["weekday"], "fallback.weekday")
    fallback_weekend = _validate_vector(fallback["weekend"], "fallback.weekend")
    month_weights = profile_payload["weights"]

    for month_idx in range(12):
        month_payload = month_weights.get(str(month_idx + 1), {})
        weekday_vector = month_payload.get("weekday", fallback_weekday)
        weekend_vector = month_payload.get("weekend", fallback_weekend)
        lookup[month_idx, 0, :] = _validate_vector(
            weekday_vector,
            f"weights.{month_idx + 1}.weekday",
        )
        lookup[month_idx, 1, :] = _validate_vector(
            weekend_vector,
            f"weights.{month_idx + 1}.weekend",
        )

    return lookup


def _ensure_utc_index(index_utc: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if not isinstance(index_utc, pd.DatetimeIndex):
        index_utc = pd.DatetimeIndex(index_utc)
    if index_utc.tz is None:
        return index_utc.tz_localize("UTC")
    return index_utc.tz_convert("UTC")


def generate_empirical_hourly_load_weights(
    index_utc: pd.DatetimeIndex,
    profile_name: str,
    archetypes: dict[str, Any],
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> np.ndarray:
    canonical_profile = resolve_profile_alias(profile_name)
    index_utc = _ensure_utc_index(index_utc)
    local_index = index_utc.tz_convert(timezone_name)

    lookup = _build_profile_lookup(archetypes["archetypes"][canonical_profile])

    month_idx = local_index.month.values.astype(int) - 1
    day_type_idx = (local_index.weekday.values.astype(int) >= 5).astype(int)
    hour_idx = local_index.hour.values.astype(int)

    weights = lookup[month_idx, day_type_idx, hour_idx]
    return np.maximum(weights.astype(float), 1e-6)
