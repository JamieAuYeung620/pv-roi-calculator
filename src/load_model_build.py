from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:
    from load_model import (  # type: ignore
        ARCHETYPE_SCHEMA_VERSION,
        DEFAULT_TIMEZONE_NAME,
        EMPIRICAL_PROFILE_IDS,
        LEGACY_PROFILE_ALIASES,
        LOAD_MODEL_VERSION,
        PROFILE_LABELS,
    )
except ImportError:
    from src.load_model import (
        ARCHETYPE_SCHEMA_VERSION,
        DEFAULT_TIMEZONE_NAME,
        EMPIRICAL_PROFILE_IDS,
        LEGACY_PROFILE_ALIASES,
        LOAD_MODEL_VERSION,
        PROFILE_LABELS,
    )


TIMESTAMP_COLUMN_CANDIDATES = ("GMT", "DateTime", "datetime", "timestamp", "Timestamp")
HOUSEHOLD_ID_COLUMN_CANDIDATES = ("LCLid", "household_id", "household", "Household", "id")
CONSUMPTION_COLUMN_CANDIDATES = (
    "KWH/hh (per half hour)",
    "kwh_hh",
    "consumption_kwh",
    "energy_kwh",
    "kwh",
)
DAY_TYPE_ORDER = ("weekday", "weekend")
PROFILE_ASSIGNMENT_ORDER = (
    "empirical_evening_peaked",
    "empirical_balanced",
    "empirical_daytime_occupied",
)
DEFAULT_SOURCE_DATASET_NAME = "Low Carbon London smart-meter dataset"


@dataclass
class HouseholdAccumulator:
    """Accumulates per-household statistics from half-hourly smart-meter rows."""

    observed_half_hours: int = 0
    observed_complete_hours: int = 0
    min_timestamp_utc: pd.Timestamp | None = None
    max_timestamp_utc: pd.Timestamp | None = None
    total_kwh: float = 0.0
    hour_sum: np.ndarray = field(default_factory=lambda: np.zeros(24, dtype=float))
    month_daytype_hour_sum: np.ndarray = field(default_factory=lambda: np.zeros((12, 2, 24), dtype=float))
    month_daytype_hour_count: np.ndarray = field(default_factory=lambda: np.zeros((12, 2, 24), dtype=int))

    def update_observation_window(
        self,
        observed_half_hours: int,
        min_timestamp_utc: pd.Timestamp,
        max_timestamp_utc: pd.Timestamp,
    ) -> None:
        self.observed_half_hours += int(observed_half_hours)
        if self.min_timestamp_utc is None or min_timestamp_utc < self.min_timestamp_utc:
            self.min_timestamp_utc = min_timestamp_utc
        if self.max_timestamp_utc is None or max_timestamp_utc > self.max_timestamp_utc:
            self.max_timestamp_utc = max_timestamp_utc

    def completeness(self) -> float:
        if self.min_timestamp_utc is None or self.max_timestamp_utc is None:
            return 0.0
        span_half_hours = int(((self.max_timestamp_utc - self.min_timestamp_utc).total_seconds() / 1800.0) + 1)
        if span_half_hours <= 0:
            return 0.0
        return float(self.observed_half_hours) / float(span_half_hours)


def normalize_hourly_weight_vector(vector: np.ndarray) -> np.ndarray:
    """Scale a 24-hour vector so each day-type profile sums to 24 relative units."""

    vector = np.asarray(vector, dtype=float)
    total = float(vector.sum())
    if total <= 0.0 or not np.isfinite(total):
        return np.full(24, 1.0, dtype=float)
    return vector * (24.0 / total)


def build_bootstrap_payload() -> dict[str, Any]:
    """Return the bundled bootstrap asset used before an empirical rebuild."""

    base_profiles: dict[str, dict[str, np.ndarray]] = {
        "empirical_evening_peaked": {
            "weekday": np.array([
                0.34, 0.30, 0.28, 0.28, 0.31, 0.40,
                0.58, 0.74, 0.70, 0.52, 0.42, 0.36,
                0.32, 0.32, 0.35, 0.42, 0.54, 0.80,
                0.98, 1.04, 0.98, 0.82, 0.64, 0.44,
            ], dtype=float),
            "weekend": np.array([
                0.36, 0.32, 0.30, 0.30, 0.33, 0.40,
                0.48, 0.58, 0.62, 0.60, 0.56, 0.52,
                0.50, 0.50, 0.52, 0.58, 0.68, 0.86,
                0.98, 1.02, 0.96, 0.82, 0.66, 0.48,
            ], dtype=float),
        },
        "empirical_daytime_occupied": {
            "weekday": np.array([
                0.30, 0.27, 0.25, 0.25, 0.28, 0.34,
                0.44, 0.54, 0.62, 0.70, 0.76, 0.80,
                0.82, 0.82, 0.78, 0.72, 0.66, 0.70,
                0.80, 0.86, 0.80, 0.70, 0.54, 0.40,
            ], dtype=float),
            "weekend": np.array([
                0.32, 0.29, 0.27, 0.27, 0.29, 0.34,
                0.42, 0.50, 0.58, 0.66, 0.72, 0.76,
                0.78, 0.80, 0.78, 0.74, 0.70, 0.74,
                0.82, 0.88, 0.84, 0.74, 0.58, 0.44,
            ], dtype=float),
        },
        "empirical_balanced": {
            "weekday": np.array([
                0.32, 0.29, 0.27, 0.27, 0.29, 0.36,
                0.48, 0.60, 0.66, 0.62, 0.58, 0.56,
                0.56, 0.56, 0.58, 0.62, 0.68, 0.78,
                0.86, 0.90, 0.84, 0.72, 0.58, 0.42,
            ], dtype=float),
            "weekend": np.array([
                0.34, 0.30, 0.28, 0.28, 0.30, 0.36,
                0.46, 0.54, 0.58, 0.60, 0.60, 0.58,
                0.58, 0.58, 0.60, 0.62, 0.70, 0.78,
                0.84, 0.88, 0.82, 0.72, 0.60, 0.46,
            ], dtype=float),
        },
    }

    winter_months = {11, 12, 1, 2}
    shoulder_months = {3, 4, 9, 10}
    month_segment_multipliers: dict[int, dict[str, float]] = {}
    for month in range(1, 13):
        if month in winter_months:
            month_segment_multipliers[month] = {
                "overnight": 1.06,
                "morning": 1.10,
                "daytime": 0.96,
                "evening": 1.12,
                "late_evening": 1.06,
            }
        elif month in shoulder_months:
            month_segment_multipliers[month] = {
                "overnight": 1.02,
                "morning": 1.04,
                "daytime": 0.99,
                "evening": 1.03,
                "late_evening": 1.01,
            }
        else:
            month_segment_multipliers[month] = {
                "overnight": 0.96,
                "morning": 0.95,
                "daytime": 1.06,
                "evening": 0.94,
                "late_evening": 0.97,
            }

    def seasonally_adjust(base_vector: np.ndarray, month: int, day_type: str) -> np.ndarray:
        vec = np.asarray(base_vector, dtype=float).copy()
        multipliers = month_segment_multipliers[month]
        vec[[0, 1, 2, 3, 4, 23]] *= multipliers["overnight"]
        vec[[5, 6, 7, 8]] *= multipliers["morning"]
        vec[[9, 10, 11, 12, 13, 14, 15, 16]] *= multipliers["daytime"]
        vec[[17, 18, 19, 20]] *= multipliers["evening"]
        vec[[21, 22]] *= multipliers["late_evening"]
        if day_type == "weekend":
            vec[[8, 9, 10, 11, 12, 13, 14, 15]] *= 1.04
            vec[[17, 18, 19, 20]] *= 0.98
        return normalize_hourly_weight_vector(vec)

    archetypes: dict[str, dict[str, Any]] = {}
    synthetic_household_counts = {
        "empirical_evening_peaked": 4,
        "empirical_daytime_occupied": 4,
        "empirical_balanced": 4,
    }

    for profile_id, base in base_profiles.items():
        weights: dict[str, dict[str, list[float]]] = {}
        for month in range(1, 13):
            weights[str(month)] = {
                day_type: seasonally_adjust(base[day_type], month, day_type).round(6).tolist()
                for day_type in DAY_TYPE_ORDER
            }

        archetypes[profile_id] = {
            "label": PROFILE_LABELS[profile_id],
            "description": (
                "Bundled bootstrap archetype. Rebuild with the official Low Carbon London smart-meter dataset "
                "for dissertation-grade empirical centroids."
            ),
            "households_retained": synthetic_household_counts[profile_id],
            "weights": weights,
            "fallback": {
                day_type: normalize_hourly_weight_vector(base[day_type]).round(6).tolist()
                for day_type in DAY_TYPE_ORDER
            },
        }

    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": ARCHETYPE_SCHEMA_VERSION,
        "load_model_version": LOAD_MODEL_VERSION,
        "generation_mode": "bootstrap",
        "source_name": "bootstrap_seed_profiles",
        "source_target_dataset": DEFAULT_SOURCE_DATASET_NAME,
        "generated_at_utc": now_utc,
        "timezone_name": DEFAULT_TIMEZONE_NAME,
        "filtering": {
            "note": "Bootstrap asset bundled for runtime safety; rebuild with --input for empirical archetypes.",
        },
        "profile_aliases": LEGACY_PROFILE_ALIASES,
        "profile_order": list(EMPIRICAL_PROFILE_IDS),
        "retained_households_total": int(sum(synthetic_household_counts.values())),
        "archetypes": archetypes,
    }


def write_archetype_summary_markdown(payload: dict[str, Any], summary_path: Path) -> None:
    """Write the compact markdown summary shipped beside the runtime asset."""

    generation_mode = payload.get("generation_mode", "unknown")
    lines = [
        "# UK Load Archetypes Summary",
        "",
        f"- Load model version: `{payload.get('load_model_version')}`",
        f"- Schema version: `{payload.get('schema_version')}`",
        f"- Generation mode: `{generation_mode}`",
        f"- Source name: `{payload.get('source_name')}`",
        f"- Generated at (UTC): `{payload.get('generated_at_utc')}`",
        f"- Timezone used for behaviour lookup: `{payload.get('timezone_name')}`",
        "",
        "## Retained households",
        "",
    ]

    retained_total = payload.get("retained_households_total")
    if retained_total is None:
        lines.append("- Total retained households: not recorded in this asset.")
    else:
        lines.append(f"- Total retained households: `{retained_total}`")

    for profile_id in EMPIRICAL_PROFILE_IDS:
        profile_payload = payload["archetypes"][profile_id]
        lines.append(f"- `{profile_id}`: `{profile_payload.get('households_retained', 'not recorded')}` households")

    lines.extend(["", "## Derivation notes", ""])
    filtering = payload.get("filtering", {})
    if generation_mode == "bootstrap":
        lines.append(
            "- This bundled asset is a lightweight bootstrap so the app can run before the official smart-meter data is supplied locally."
        )
        lines.append(
            "- Rebuild with `python3 scripts/build_empirical_load_archetypes.py --input /path/to/london-smart-meter-dataset` to replace it with empirical centroids."
        )
    else:
        lines.append(
            "- Household timestamps are parsed as UTC/GMT, shifted back 30 minutes to represent the start of each half-hour measurement period, then converted to `Europe/London` for behavioural lookups."
        )
        lines.append(
            "- Rows with missing timestamps, missing household IDs, negative kWh values, or half-hour demand above the configured outlier threshold are dropped before aggregation."
        )
        lines.append(
            "- Households are retained only if they meet the configured completeness threshold and minimum number of complete hourly observations."
        )
        lines.append(
            "- Retained households are ranked by daytime-minus-evening demand share and split deterministically into evening-peaked, balanced, and daytime-occupied terciles."
        )
        if filtering:
            lines.extend(["", "## Filtering parameters", ""])
            for key, value in filtering.items():
                lines.append(f"- `{key}`: `{value}`")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_first_matching(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    columns_list = list(columns)
    columns_lower = {col.lower(): col for col in columns_list}
    columns_normalized = {col.strip().lower(): col for col in columns_list}
    for candidate in candidates:
        if candidate in columns_list:
            return candidate
        lowered = candidate.lower()
        if lowered in columns_lower:
            return columns_lower[lowered]
        normalized = candidate.strip().lower()
        if normalized in columns_normalized:
            return columns_normalized[normalized]
    return None


def natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def iter_csv_sources(input_path: Path) -> list[tuple[Path, str | None]]:
    """Return deterministic CSV inputs from a zip archive, CSV file, or directory tree."""

    if input_path.is_file():
        if input_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(input_path) as archive:
                members = sorted(
                    [
                        member
                        for member in archive.namelist()
                        if member.lower().endswith(".csv") and not member.startswith("__MACOSX/")
                    ],
                    key=natural_sort_key,
                )
            return [(input_path, member) for member in members]
        return [(input_path, None)]
    return [
        (path, None)
        for path in sorted(input_path.rglob("*.csv"), key=lambda path: natural_sort_key(str(path)))
        if path.is_file()
    ]


def source_label(source: tuple[Path, str | None]) -> str:
    path, member = source
    if member is None:
        return str(path)
    return f"{path}!{member}"


def standardize_chunk_long(chunk: pd.DataFrame) -> pd.DataFrame:
    timestamp_col = find_first_matching(chunk.columns, TIMESTAMP_COLUMN_CANDIDATES)
    household_id_col = find_first_matching(chunk.columns, HOUSEHOLD_ID_COLUMN_CANDIDATES)
    consumption_col = find_first_matching(chunk.columns, CONSUMPTION_COLUMN_CANDIDATES)
    if not timestamp_col or not household_id_col or not consumption_col:
        return pd.DataFrame(columns=["household_id", "timestamp_utc", "kwh_halfhour"])

    return pd.DataFrame(
        {
            "household_id": chunk[household_id_col].astype(str),
            "timestamp_utc": pd.to_datetime(chunk[timestamp_col], utc=True, errors="coerce"),
            "kwh_halfhour": pd.to_numeric(chunk[consumption_col], errors="coerce"),
        }
    )


def standardize_chunk_wide(chunk: pd.DataFrame) -> pd.DataFrame:
    timestamp_col = find_first_matching(chunk.columns, TIMESTAMP_COLUMN_CANDIDATES)
    if not timestamp_col:
        return pd.DataFrame(columns=["household_id", "timestamp_utc", "kwh_halfhour"])

    value_columns = [col for col in chunk.columns if col != timestamp_col]
    if not value_columns:
        return pd.DataFrame(columns=["household_id", "timestamp_utc", "kwh_halfhour"])

    melted = chunk.melt(
        id_vars=[timestamp_col],
        value_vars=value_columns,
        var_name="household_id",
        value_name="kwh_halfhour",
    )
    melted["timestamp_utc"] = pd.to_datetime(melted[timestamp_col], utc=True, errors="coerce")
    melted["kwh_halfhour"] = pd.to_numeric(melted["kwh_halfhour"], errors="coerce")
    return melted[["household_id", "timestamp_utc", "kwh_halfhour"]]


def read_csv_header(source: tuple[Path, str | None]) -> pd.DataFrame:
    csv_path, member = source
    if member is None:
        return pd.read_csv(csv_path, nrows=5)
    with zipfile.ZipFile(csv_path) as archive:
        with archive.open(member) as handle:
            return pd.read_csv(handle, nrows=5)


def iter_csv_chunks(source: tuple[Path, str | None], chunksize: int) -> Iterable[pd.DataFrame]:
    csv_path, member = source
    if member is None:
        for chunk in pd.read_csv(csv_path, chunksize=chunksize):
            yield chunk
        return

    with zipfile.ZipFile(csv_path) as archive:
        with archive.open(member) as handle:
            for chunk in pd.read_csv(handle, chunksize=chunksize):
                yield chunk


def iter_standardized_chunks(
    source: tuple[Path, str | None],
    long_rows_per_chunk: int,
    wide_rows_per_chunk: int,
) -> Iterable[pd.DataFrame]:
    header = read_csv_header(source)
    timestamp_col = find_first_matching(header.columns, TIMESTAMP_COLUMN_CANDIDATES)
    household_id_col = find_first_matching(header.columns, HOUSEHOLD_ID_COLUMN_CANDIDATES)
    consumption_col = find_first_matching(header.columns, CONSUMPTION_COLUMN_CANDIDATES)

    is_long = bool(timestamp_col and household_id_col and consumption_col)
    chunksize = long_rows_per_chunk if is_long else wide_rows_per_chunk

    for chunk in iter_csv_chunks(source, chunksize=chunksize):
        standardized = standardize_chunk_long(chunk) if is_long else standardize_chunk_wide(chunk)
        if not standardized.empty:
            yield standardized


def clean_standardized_chunk(
    chunk: pd.DataFrame,
    max_halfhour_kwh: float,
) -> pd.DataFrame:
    cleaned = chunk.dropna(subset=["household_id", "timestamp_utc", "kwh_halfhour"]).copy()
    cleaned["household_id"] = cleaned["household_id"].astype(str).str.strip()
    cleaned = cleaned[cleaned["household_id"] != ""]
    cleaned = cleaned[cleaned["kwh_halfhour"] >= 0.0]
    # Values above ~8 kWh in 30 minutes imply a sustained domestic demand above 16 kW.
    cleaned = cleaned[cleaned["kwh_halfhour"] <= float(max_halfhour_kwh)]
    if cleaned.empty:
        return cleaned

    cleaned["period_start_utc"] = cleaned["timestamp_utc"] - pd.Timedelta(minutes=30)
    local_wall_time = cleaned["period_start_utc"].dt.tz_convert(DEFAULT_TIMEZONE_NAME).dt.tz_localize(None)
    cleaned["hour_start_local"] = pd.to_datetime(local_wall_time).dt.floor("h")
    return cleaned


def accumulate_household_stats(
    sources: list[tuple[Path, str | None]],
    min_complete_half_hours_per_hour: int,
    long_rows_per_chunk: int,
    wide_rows_per_chunk: int,
    max_halfhour_kwh: float,
) -> dict[str, HouseholdAccumulator]:
    """Stream the dataset and accumulate per-household hourly/seasonal statistics."""

    households: dict[str, HouseholdAccumulator] = {}

    for source in sources:
        print(f"Processing source: {source_label(source)}")
        for chunk in iter_standardized_chunks(source, long_rows_per_chunk, wide_rows_per_chunk):
            cleaned = clean_standardized_chunk(chunk, max_halfhour_kwh=max_halfhour_kwh)
            if cleaned.empty:
                continue

            raw_windows = (
                cleaned.groupby("household_id", observed=True)
                .agg(
                    observed_half_hours=("kwh_halfhour", "size"),
                    min_timestamp_utc=("timestamp_utc", "min"),
                    max_timestamp_utc=("timestamp_utc", "max"),
                )
                .reset_index()
            )
            for row in raw_windows.itertuples(index=False):
                acc = households.setdefault(row.household_id, HouseholdAccumulator())
                acc.update_observation_window(
                    observed_half_hours=int(row.observed_half_hours),
                    min_timestamp_utc=row.min_timestamp_utc,
                    max_timestamp_utc=row.max_timestamp_utc,
                )

            hourly = (
                cleaned.groupby(["household_id", "hour_start_local"], observed=True)
                .agg(
                    hourly_kwh=("kwh_halfhour", "sum"),
                    halfhour_count=("kwh_halfhour", "size"),
                )
                .reset_index()
            )
            hourly = hourly[hourly["halfhour_count"] >= int(min_complete_half_hours_per_hour)]
            if hourly.empty:
                continue

            hourly["month"] = hourly["hour_start_local"].dt.month.astype(int)
            hourly["day_type_idx"] = (hourly["hour_start_local"].dt.weekday >= 5).astype(int)
            hourly["hour"] = hourly["hour_start_local"].dt.hour.astype(int)

            for row in hourly.itertuples(index=False):
                acc = households.setdefault(row.household_id, HouseholdAccumulator())
                acc.observed_complete_hours += 1
                acc.total_kwh += float(row.hourly_kwh)
                acc.hour_sum[int(row.hour)] += float(row.hourly_kwh)
                acc.month_daytype_hour_sum[int(row.month) - 1, int(row.day_type_idx), int(row.hour)] += float(row.hourly_kwh)
                acc.month_daytype_hour_count[int(row.month) - 1, int(row.day_type_idx), int(row.hour)] += 1

    return households


def retained_households(
    households: dict[str, HouseholdAccumulator],
    min_completeness: float,
    min_complete_hours: int,
) -> dict[str, HouseholdAccumulator]:
    retained: dict[str, HouseholdAccumulator] = {}
    for household_id, acc in households.items():
        if acc.total_kwh <= 0.0:
            continue
        if acc.observed_complete_hours < int(min_complete_hours):
            continue
        if acc.completeness() < float(min_completeness):
            continue
        retained[household_id] = acc
    return retained


def compute_global_fallbacks(retained: dict[str, HouseholdAccumulator]) -> dict[str, np.ndarray]:
    daytype_sum = np.zeros((2, 24), dtype=float)
    daytype_count = np.zeros((2, 24), dtype=float)

    for acc in retained.values():
        daytype_sum += acc.month_daytype_hour_sum.sum(axis=0)
        daytype_count += acc.month_daytype_hour_count.sum(axis=0)

    fallback: dict[str, np.ndarray] = {}
    for day_type_idx, day_type in enumerate(DAY_TYPE_ORDER):
        mean_vector = np.divide(
            daytype_sum[day_type_idx],
            daytype_count[day_type_idx],
            out=np.zeros(24, dtype=float),
            where=daytype_count[day_type_idx] > 0,
        )
        if not np.isfinite(mean_vector).all() or mean_vector.sum() <= 0.0:
            mean_vector = np.full(24, 1.0, dtype=float)
        fallback[day_type] = normalize_hourly_weight_vector(mean_vector)
    return fallback


def assign_provisional_archetypes(retained: dict[str, HouseholdAccumulator]) -> dict[str, str]:
    """Assign households into deterministic daytime/evening terciles."""

    metrics: list[tuple[str, float]] = []
    for household_id, acc in retained.items():
        normalized_hour_share = acc.hour_sum / float(acc.total_kwh)
        daytime_share = float(normalized_hour_share[9:17].sum())
        evening_share = float(normalized_hour_share[17:23].sum())
        metrics.append((household_id, daytime_share - evening_share))

    metrics.sort(key=lambda item: (item[1], item[0]))
    if not metrics:
        return {}

    assignments: dict[str, str] = {}
    lower_cut = len(metrics) // 3
    upper_cut = len(metrics) - (len(metrics) // 3)
    for idx, (household_id, _) in enumerate(metrics):
        if idx < lower_cut:
            assignments[household_id] = "empirical_evening_peaked"
        elif idx >= upper_cut:
            assignments[household_id] = "empirical_daytime_occupied"
        else:
            assignments[household_id] = "empirical_balanced"
    return assignments


def normalized_household_vector(
    acc: HouseholdAccumulator,
    global_fallbacks: dict[str, np.ndarray],
) -> np.ndarray:
    """Return a household's filled 12 x 2 x 24 normalized representation."""

    daytype_sum = acc.month_daytype_hour_sum.sum(axis=0)
    daytype_count = acc.month_daytype_hour_count.sum(axis=0)
    annual_mean = np.divide(
        acc.month_daytype_hour_sum.sum(axis=(0, 1)),
        acc.month_daytype_hour_count.sum(axis=(0, 1)),
        out=np.zeros(24, dtype=float),
        where=acc.month_daytype_hour_count.sum(axis=(0, 1)) > 0,
    )
    if annual_mean.sum() <= 0.0:
        annual_mean = np.mean(np.stack(list(global_fallbacks.values())), axis=0)

    out = np.zeros((12, 2, 24), dtype=float)
    for month_idx in range(12):
        for day_type_idx, day_type in enumerate(DAY_TYPE_ORDER):
            mean_vector = np.divide(
                acc.month_daytype_hour_sum[month_idx, day_type_idx],
                acc.month_daytype_hour_count[month_idx, day_type_idx],
                out=np.full(24, np.nan, dtype=float),
                where=acc.month_daytype_hour_count[month_idx, day_type_idx] > 0,
            )
            daytype_fallback = np.divide(
                daytype_sum[day_type_idx],
                daytype_count[day_type_idx],
                out=np.full(24, np.nan, dtype=float),
                where=daytype_count[day_type_idx] > 0,
            )
            filled = np.where(np.isfinite(mean_vector), mean_vector, daytype_fallback)
            filled = np.where(np.isfinite(filled), filled, annual_mean)
            filled = np.where(np.isfinite(filled), filled, global_fallbacks[day_type])
            out[month_idx, day_type_idx] = normalize_hourly_weight_vector(filled)
    return out


def normalized_household_vectors(
    retained: dict[str, HouseholdAccumulator],
    global_fallbacks: dict[str, np.ndarray] | None = None,
) -> dict[str, np.ndarray]:
    if global_fallbacks is None:
        global_fallbacks = compute_global_fallbacks(retained)
    return {
        household_id: normalized_household_vector(acc, global_fallbacks)
        for household_id, acc in retained.items()
    }


def build_archetype_centroids(
    normalized_vectors: dict[str, np.ndarray],
    assignments: dict[str, str],
    global_fallbacks: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Compute month/day-type/hour centroids for the fixed runtime profile IDs."""

    fallback_centroid = np.broadcast_to(
        np.stack([global_fallbacks["weekday"], global_fallbacks["weekend"]], axis=0),
        (12, 2, 24),
    ).astype(float).copy()

    centroids: dict[str, np.ndarray] = {}
    for profile_id in EMPIRICAL_PROFILE_IDS:
        member_ids = [
            household_id
            for household_id, assigned in assignments.items()
            if assigned == profile_id and household_id in normalized_vectors
        ]
        if member_ids:
            centroid = np.mean(np.stack([normalized_vectors[household_id] for household_id in member_ids]), axis=0)
        else:
            centroid = fallback_centroid.copy()

        for month_idx in range(12):
            for day_type_idx in range(2):
                centroid[month_idx, day_type_idx] = normalize_hourly_weight_vector(centroid[month_idx, day_type_idx])

        centroids[profile_id] = centroid
    return centroids


def build_empirical_payload(
    retained: dict[str, HouseholdAccumulator],
    assignments: dict[str, str],
    min_completeness: float,
    min_complete_hours: int,
    max_halfhour_kwh: float,
    sources: list[tuple[Path, str | None]],
    max_sources: int | None,
) -> dict[str, Any]:
    global_fallbacks = compute_global_fallbacks(retained)
    normalized_vectors = normalized_household_vectors(retained, global_fallbacks)
    centroids = build_archetype_centroids(normalized_vectors, assignments, global_fallbacks)

    archetypes: dict[str, dict[str, Any]] = {}
    for profile_id in EMPIRICAL_PROFILE_IDS:
        member_ids = [household_id for household_id, assigned in assignments.items() if assigned == profile_id]
        centroid = centroids[profile_id]

        weights: dict[str, dict[str, list[float]]] = {}
        for month in range(1, 13):
            weights[str(month)] = {}
            for day_type_idx, day_type in enumerate(DAY_TYPE_ORDER):
                weights[str(month)][day_type] = normalize_hourly_weight_vector(
                    centroid[month - 1, day_type_idx]
                ).round(6).tolist()

        archetypes[profile_id] = {
            "label": PROFILE_LABELS[profile_id],
            "description": "Empirical archetype derived from retained households in the official smart-meter dataset.",
            "households_retained": len(member_ids),
            "weights": weights,
            "fallback": {
                day_type: normalize_hourly_weight_vector(np.mean(centroid[:, day_type_idx, :], axis=0)).round(6).tolist()
                for day_type_idx, day_type in enumerate(DAY_TYPE_ORDER)
            },
        }

    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": ARCHETYPE_SCHEMA_VERSION,
        "load_model_version": LOAD_MODEL_VERSION,
        "generation_mode": "empirical_from_input",
        "source_name": DEFAULT_SOURCE_DATASET_NAME,
        "generated_at_utc": now_utc,
        "timezone_name": DEFAULT_TIMEZONE_NAME,
        "filtering": {
            "min_completeness": float(min_completeness),
            "min_complete_hours": int(min_complete_hours),
            "max_halfhour_kwh": float(max_halfhour_kwh),
            "files_processed": len(sources),
            "max_sources_requested": None if max_sources is None else int(max_sources),
        },
        "profile_aliases": LEGACY_PROFILE_ALIASES,
        "profile_order": list(EMPIRICAL_PROFILE_IDS),
        "retained_households_total": len(retained),
        "archetypes": archetypes,
    }


def build_archetype_asset(
    input_path: Path | None,
    output_path: Path,
    summary_path: Path,
    min_completeness: float,
    min_complete_hours: int,
    min_complete_half_hours_per_hour: int,
    long_rows_per_chunk: int,
    wide_rows_per_chunk: int,
    max_halfhour_kwh: float,
    max_sources: int | None,
    bootstrap: bool,
) -> None:
    """Build the runtime archetype asset from bootstrap seeds or empirical input data."""

    if bootstrap:
        payload = build_bootstrap_payload()
    else:
        if input_path is None:
            raise ValueError("--input is required unless --bootstrap is set.")
        sources = iter_csv_sources(input_path)
        if max_sources is not None:
            sources = sources[: max(1, int(max_sources))]
        if not sources:
            raise FileNotFoundError(f"No CSV files found under: {input_path}")
        households = accumulate_household_stats(
            sources=sources,
            min_complete_half_hours_per_hour=min_complete_half_hours_per_hour,
            long_rows_per_chunk=long_rows_per_chunk,
            wide_rows_per_chunk=wide_rows_per_chunk,
            max_halfhour_kwh=max_halfhour_kwh,
        )
        retained = retained_households(
            households,
            min_completeness=min_completeness,
            min_complete_hours=min_complete_hours,
        )
        if len(retained) < 3:
            raise ValueError(
                "Too few households were retained after filtering to build three archetypes. "
                "Relax the thresholds or check the input dataset path."
            )
        assignments = assign_provisional_archetypes(retained)
        payload = build_empirical_payload(
            retained=retained,
            assignments=assignments,
            min_completeness=min_completeness,
            min_complete_hours=min_complete_hours,
            max_halfhour_kwh=max_halfhour_kwh,
            sources=sources,
            max_sources=max_sources,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_archetype_summary_markdown(payload, summary_path)
    print(f"Wrote archetype asset: {output_path}")
    print(f"Wrote summary:        {summary_path}")
