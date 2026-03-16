from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from load_model import (  # type: ignore
        DEFAULT_ARCHETYPE_PATH,
        EMPIRICAL_PROFILE_IDS,
        LOAD_MODEL_VERSION,
        PROFILE_LABELS,
        load_empirical_archetypes,
    )
    from load_model_build import DAY_TYPE_ORDER, DEFAULT_SOURCE_DATASET_NAME, normalize_hourly_weight_vector
except ImportError:
    from src.load_model import (
        DEFAULT_ARCHETYPE_PATH,
        EMPIRICAL_PROFILE_IDS,
        LOAD_MODEL_VERSION,
        PROFILE_LABELS,
        load_empirical_archetypes,
    )
    from src.load_model_build import DAY_TYPE_ORDER, DEFAULT_SOURCE_DATASET_NAME, normalize_hourly_weight_vector


VALIDATION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ValidationSplit:
    """Deterministic train/validation household split."""

    training_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    counts_by_archetype: dict[str, dict[str, int]]


def load_validation_reference_asset(
    asset_path: Path = DEFAULT_ARCHETYPE_PATH,
    *,
    allow_bootstrap_asset: bool = False,
) -> dict[str, Any]:
    """Load the current runtime asset and reject bootstrap-only inputs by default."""

    payload = load_empirical_archetypes(asset_path)
    generation_mode = str(payload.get("generation_mode", "unknown")).strip().lower()
    if generation_mode == "bootstrap" and not allow_bootstrap_asset:
        raise ValueError(
            "Formal validation requires an empirical reference asset; bootstrap assets are rejected "
            "unless --allow-bootstrap-asset is supplied."
        )
    return payload


def deterministic_stratified_validation_split(
    assignments: Mapping[str, str],
    validation_fraction: float = 0.2,
) -> ValidationSplit:
    """
    Deterministically split sorted household IDs within each provisional archetype bucket.

    The selection rule uses cumulative fractional thresholds, which behaves like taking
    every n-th household for common fractions such as 0.2 while remaining deterministic
    for arbitrary fractions.
    """

    if validation_fraction <= 0.0 or validation_fraction >= 1.0:
        raise ValueError("validation_fraction must be in (0, 1).")

    training_ids: list[str] = []
    validation_ids: list[str] = []
    counts_by_archetype: dict[str, dict[str, int]] = {}

    for profile_id in EMPIRICAL_PROFILE_IDS:
        household_ids = sorted(
            household_id
            for household_id, assigned_profile in assignments.items()
            if assigned_profile == profile_id
        )

        profile_validation: list[str] = []
        if len(household_ids) > 1:
            for idx, household_id in enumerate(household_ids, start=1):
                prev_count = int(np.floor((idx - 1) * validation_fraction))
                next_count = int(np.floor(idx * validation_fraction))
                if next_count > prev_count:
                    profile_validation.append(household_id)

            if not profile_validation:
                profile_validation = [household_ids[-1]]
            if len(profile_validation) >= len(household_ids):
                profile_validation = profile_validation[:-1] or [household_ids[-1]]

        profile_validation_set = set(profile_validation)
        profile_training = [household_id for household_id in household_ids if household_id not in profile_validation_set]

        if len(household_ids) > 1 and not profile_training:
            moved = profile_validation.pop()
            profile_training = [moved]
            profile_validation_set = set(profile_validation)
            profile_training = [household_id for household_id in household_ids if household_id not in profile_validation_set]

        training_ids.extend(profile_training)
        validation_ids.extend(profile_validation)
        counts_by_archetype[profile_id] = {
            "training": len(profile_training),
            "validation": len(profile_validation),
        }

    return ValidationSplit(
        training_ids=tuple(training_ids),
        validation_ids=tuple(validation_ids),
        counts_by_archetype=counts_by_archetype,
    )


def flatten_profile_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    if arr.shape != (12, 2, 24):
        raise ValueError("Expected a 12 x 2 x 24 load-profile vector.")
    return arr.reshape(-1)


def aggregate_weekday_weekend_profile(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    if arr.shape != (12, 2, 24):
        raise ValueError("Expected a 12 x 2 x 24 load-profile vector.")
    aggregated = np.zeros((2, 24), dtype=float)
    for day_type_idx, _ in enumerate(DAY_TYPE_ORDER):
        aggregated[day_type_idx] = normalize_hourly_weight_vector(np.mean(arr[:, day_type_idx, :], axis=0))
    return aggregated


def _pearson_correlation(observed: np.ndarray, reference: np.ndarray) -> float:
    observed = np.asarray(observed, dtype=float).reshape(-1)
    reference = np.asarray(reference, dtype=float).reshape(-1)
    if observed.shape != reference.shape:
        raise ValueError("Observed and reference arrays must have the same shape.")
    obs_std = float(np.std(observed))
    ref_std = float(np.std(reference))
    if obs_std <= 0.0 or ref_std <= 0.0:
        return 1.0 if np.allclose(observed, reference) else 0.0
    corr = float(np.corrcoef(observed, reference)[0, 1])
    if not np.isfinite(corr):
        return 0.0
    return corr


def compute_profile_metrics(observed: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    observed = np.asarray(observed, dtype=float).reshape(-1)
    reference = np.asarray(reference, dtype=float).reshape(-1)
    if observed.shape != reference.shape:
        raise ValueError("Observed and reference arrays must have the same shape.")

    delta = observed - reference
    mae = float(np.mean(np.abs(delta)))
    rmse = float(np.sqrt(np.mean(np.square(delta))))
    euclidean_distance = float(np.linalg.norm(delta))
    pearson_correlation = _pearson_correlation(observed, reference)

    return {
        "mae": mae,
        "rmse": rmse,
        "euclidean_distance": euclidean_distance,
        "pearson_correlation": pearson_correlation,
    }


def assign_nearest_archetype(
    observed_vector: np.ndarray,
    centroids: Mapping[str, np.ndarray],
) -> tuple[str, dict[str, float]]:
    observed_flat = flatten_profile_vector(observed_vector)
    distances: dict[str, float] = {}
    for profile_id in EMPIRICAL_PROFILE_IDS:
        centroid_vector = np.asarray(centroids[profile_id], dtype=float)
        distances[profile_id] = float(np.linalg.norm(observed_flat - flatten_profile_vector(centroid_vector)))
    assigned_profile = min(distances, key=lambda profile_id: (distances[profile_id], profile_id))
    return assigned_profile, distances


def evaluate_validation_households(
    validation_vectors: Mapping[str, np.ndarray],
    provisional_assignments: Mapping[str, str],
    centroids: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for household_id in sorted(validation_vectors):
        observed_vector = np.asarray(validation_vectors[household_id], dtype=float)
        assigned_archetype, distances = assign_nearest_archetype(observed_vector, centroids)
        centroid_vector = np.asarray(centroids[assigned_archetype], dtype=float)

        full_metrics = compute_profile_metrics(
            flatten_profile_vector(observed_vector),
            flatten_profile_vector(centroid_vector),
        )
        weekday_weekend_metrics = compute_profile_metrics(
            aggregate_weekday_weekend_profile(observed_vector),
            aggregate_weekday_weekend_profile(centroid_vector),
        )

        rows.append(
            {
                "household_id": household_id,
                "provisional_archetype": provisional_assignments[household_id],
                "assigned_archetype": assigned_archetype,
                "assignment_matches_provisional": bool(assigned_archetype == provisional_assignments[household_id]),
                "distance_to_assigned_centroid": float(distances[assigned_archetype]),
                "full_mae": float(full_metrics["mae"]),
                "full_rmse": float(full_metrics["rmse"]),
                "full_pearson_correlation": float(full_metrics["pearson_correlation"]),
                "weekday_weekend_mae": float(weekday_weekend_metrics["mae"]),
                "weekday_weekend_rmse": float(weekday_weekend_metrics["rmse"]),
                "weekday_weekend_pearson_correlation": float(weekday_weekend_metrics["pearson_correlation"]),
            }
        )

    return pd.DataFrame(rows)


def summarize_validation_results(
    results_df: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    if results_df.empty:
        raise ValueError("Validation results are empty; cannot summarize.")

    def _metric_block(frame: pd.DataFrame, mae_col: str, rmse_col: str, corr_col: str) -> dict[str, float]:
        return {
            "count": int(len(frame)),
            "mean_mae": float(frame[mae_col].mean()),
            "median_mae": float(frame[mae_col].median()),
            "mean_rmse": float(frame[rmse_col].mean()),
            "median_rmse": float(frame[rmse_col].median()),
            "mean_pearson_correlation": float(frame[corr_col].mean()),
            "median_pearson_correlation": float(frame[corr_col].median()),
        }

    overall_metrics = {
        "flattened_12x2x24": _metric_block(results_df, "full_mae", "full_rmse", "full_pearson_correlation"),
        "weekday_weekend_24h": _metric_block(
            results_df,
            "weekday_weekend_mae",
            "weekday_weekend_rmse",
            "weekday_weekend_pearson_correlation",
        ),
    }

    per_archetype_metrics: dict[str, dict[str, Any]] = {}
    for profile_id in EMPIRICAL_PROFILE_IDS:
        subset = results_df[results_df["provisional_archetype"] == profile_id]
        if subset.empty:
            per_archetype_metrics[profile_id] = {
                "count": 0,
                "mean_mae": None,
                "mean_rmse": None,
                "mean_pearson_correlation": None,
            }
            continue
        per_archetype_metrics[profile_id] = {
            "count": int(len(subset)),
            "mean_mae": float(subset["full_mae"].mean()),
            "mean_rmse": float(subset["full_rmse"].mean()),
            "mean_pearson_correlation": float(subset["full_pearson_correlation"].mean()),
        }

    assignment_counts = {
        profile_id: int((results_df["assigned_archetype"] == profile_id).sum())
        for profile_id in EMPIRICAL_PROFILE_IDS
    }
    assignment_summary = {
        "matches_provisional_count": int(results_df["assignment_matches_provisional"].sum()),
        "matches_provisional_fraction": float(results_df["assignment_matches_provisional"].mean()),
        "assigned_counts": assignment_counts,
    }
    return overall_metrics, per_archetype_metrics, assignment_summary


def build_centroid_profile_comparisons(
    validation_vectors: Mapping[str, np.ndarray],
    provisional_assignments: Mapping[str, str],
    centroids: Mapping[str, np.ndarray],
) -> dict[str, dict[str, list[float]]]:
    """Compare training centroids against mean held-out weekday/weekend profiles."""

    comparisons: dict[str, dict[str, list[float]]] = {}
    for profile_id in EMPIRICAL_PROFILE_IDS:
        member_vectors = [
            np.asarray(validation_vectors[household_id], dtype=float)
            for household_id in sorted(validation_vectors)
            if provisional_assignments[household_id] == profile_id
        ]
        if member_vectors:
            validation_mean = np.mean(np.stack(member_vectors), axis=0)
        else:
            validation_mean = np.asarray(centroids[profile_id], dtype=float)

        centroid_weekday_weekend = aggregate_weekday_weekend_profile(np.asarray(centroids[profile_id], dtype=float))
        validation_weekday_weekend = aggregate_weekday_weekend_profile(validation_mean)
        comparisons[profile_id] = {
            "training_centroid_weekday": centroid_weekday_weekend[0].round(6).tolist(),
            "training_centroid_weekend": centroid_weekday_weekend[1].round(6).tolist(),
            "validation_mean_weekday": validation_weekday_weekend[0].round(6).tolist(),
            "validation_mean_weekend": validation_weekday_weekend[1].round(6).tolist(),
        }
    return comparisons


def build_validation_payload(
    *,
    reference_asset: Mapping[str, Any],
    validation_fraction: float,
    filtering: Mapping[str, Any],
    retained_households_total: int,
    training_households_total: int,
    validation_households_total: int,
    split_counts_by_archetype: Mapping[str, Mapping[str, int]],
    overall_metrics: Mapping[str, Any],
    per_archetype_metrics: Mapping[str, Mapping[str, Any]],
    centroid_profile_comparisons: Mapping[str, Mapping[str, list[float]]],
    assignment_summary: Mapping[str, Any],
) -> dict[str, Any]:
    generated_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "validation_schema_version": VALIDATION_SCHEMA_VERSION,
        "load_model_version": reference_asset.get("load_model_version", LOAD_MODEL_VERSION),
        "generated_at_utc": generated_at_utc,
        "source_dataset_name": reference_asset.get("source_target_dataset", DEFAULT_SOURCE_DATASET_NAME),
        "reference_asset_generation_mode": reference_asset.get("generation_mode"),
        "reference_asset_source_name": reference_asset.get("source_name"),
        "validation_fraction": float(validation_fraction),
        "split_method": (
            "Deterministic stratified hold-out by provisional archetype label. "
            "Within each sorted household-ID bucket, cumulative fractional thresholds assign validation members."
        ),
        "filtering": dict(filtering),
        "retained_households_total": int(retained_households_total),
        "training_households_total": int(training_households_total),
        "validation_households_total": int(validation_households_total),
        "split_counts_by_provisional_archetype": {
            profile_id: {
                "training": int(split_counts_by_archetype.get(profile_id, {}).get("training", 0)),
                "validation": int(split_counts_by_archetype.get(profile_id, {}).get("validation", 0)),
            }
            for profile_id in EMPIRICAL_PROFILE_IDS
        },
        "overall_metrics": json.loads(json.dumps(overall_metrics)),
        "per_archetype_metrics": json.loads(json.dumps(per_archetype_metrics)),
        "assignment_summary": json.loads(json.dumps(assignment_summary)),
        "centroid_validation_profile_comparisons": json.loads(json.dumps(centroid_profile_comparisons)),
    }


def write_validation_summary_markdown(payload: Mapping[str, Any], output_path: Path) -> None:
    overall_full = payload["overall_metrics"]["flattened_12x2x24"]
    overall_weekday_weekend = payload["overall_metrics"]["weekday_weekend_24h"]
    lines = [
        "# Empirical Load Archetype Validation Summary",
        "",
        f"- Load model version: `{payload.get('load_model_version')}`",
        f"- Validation schema version: `{payload.get('validation_schema_version')}`",
        f"- Source dataset: `{payload.get('source_dataset_name')}`",
        f"- Reference asset generation mode: `{payload.get('reference_asset_generation_mode')}`",
        f"- Reference asset source name: `{payload.get('reference_asset_source_name')}`",
        f"- Generated at (UTC): `{payload.get('generated_at_utc')}`",
        f"- Validation split fraction: `{payload.get('validation_fraction')}`",
        "",
        "## Retained / split counts",
        "",
        f"- Retained households: `{payload.get('retained_households_total')}`",
        f"- Training households: `{payload.get('training_households_total')}`",
        f"- Validation households: `{payload.get('validation_households_total')}`",
        "",
        "### Split counts by provisional archetype",
        "",
        "| Archetype | Training | Validation |",
        "|---|---:|---:|",
    ]

    for profile_id in EMPIRICAL_PROFILE_IDS:
        counts = payload["split_counts_by_provisional_archetype"][profile_id]
        lines.append(f"| {PROFILE_LABELS[profile_id]} | {counts['training']} | {counts['validation']} |")

    lines.extend(
        [
            "",
            "## Overall validation metrics",
            "",
            "### Flattened 12 x 2 x 24 profile",
            "",
            f"- Mean MAE: `{overall_full['mean_mae']:.6f}`",
            f"- Median MAE: `{overall_full['median_mae']:.6f}`",
            f"- Mean RMSE: `{overall_full['mean_rmse']:.6f}`",
            f"- Median RMSE: `{overall_full['median_rmse']:.6f}`",
            f"- Mean Pearson correlation: `{overall_full['mean_pearson_correlation']:.6f}`",
            "",
            "### Weekday / weekend 24 h fallback profile",
            "",
            f"- Mean MAE: `{overall_weekday_weekend['mean_mae']:.6f}`",
            f"- Median MAE: `{overall_weekday_weekend['median_mae']:.6f}`",
            f"- Mean RMSE: `{overall_weekday_weekend['mean_rmse']:.6f}`",
            f"- Median RMSE: `{overall_weekday_weekend['median_rmse']:.6f}`",
            f"- Mean Pearson correlation: `{overall_weekday_weekend['mean_pearson_correlation']:.6f}`",
            "",
            "## Per-archetype validation metrics",
            "",
            "| Archetype | Validation households | Mean MAE | Mean RMSE | Mean Pearson correlation |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for profile_id in EMPIRICAL_PROFILE_IDS:
        metrics = payload["per_archetype_metrics"][profile_id]
        if metrics["count"] == 0:
            lines.append(f"| {PROFILE_LABELS[profile_id]} | 0 | n/a | n/a | n/a |")
        else:
            lines.append(
                f"| {PROFILE_LABELS[profile_id]} | {metrics['count']} | {metrics['mean_mae']:.6f} | "
                f"{metrics['mean_rmse']:.6f} | {metrics['mean_pearson_correlation']:.6f} |"
            )

    assignment_summary = payload["assignment_summary"]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                f"The held-out validation suggests that the training-only archetypes capture broad demand-timing patterns "
                f"in unseen households with a mean flattened-profile RMSE of {overall_full['mean_rmse']:.6f} and a mean "
                f"Pearson correlation of {overall_full['mean_pearson_correlation']:.6f}. "
                f"The nearest-centroid assignment matched the provisional held-out archetype label for "
                f"{100.0 * assignment_summary['matches_provisional_fraction']:.1f}% of validation households. "
                "This supports the use of the archetypes as a low-dimensional behavioural approximation for PV self-consumption studies, "
                "but it should still be interpreted as archetype-level validation rather than property-specific load forecasting."
            ),
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_validation_weekday_weekend(
    centroid_profile_comparisons: Mapping[str, Mapping[str, list[float]]],
    output_path: Path,
) -> None:
    colors = {
        "empirical_evening_peaked": "#4C78A8",
        "empirical_balanced": "#7F7F7F",
        "empirical_daytime_occupied": "#72B7B2",
    }
    hours = np.arange(24)
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 7.0), sharex=True, constrained_layout=True)
    panel_map = (
        ("weekday", axes[0], "Weekday 24 h comparison"),
        ("weekend", axes[1], "Weekend 24 h comparison"),
    )

    for day_type, axis, title in panel_map:
        for profile_id in EMPIRICAL_PROFILE_IDS:
            comparison = centroid_profile_comparisons[profile_id]
            axis.plot(
                hours,
                comparison[f"training_centroid_{day_type}"],
                color=colors[profile_id],
                linewidth=2.0,
                linestyle="-",
                label=f"{PROFILE_LABELS[profile_id]} — training centroid",
            )
            axis.plot(
                hours,
                comparison[f"validation_mean_{day_type}"],
                color=colors[profile_id],
                linewidth=1.8,
                linestyle="--",
                label=f"{PROFILE_LABELS[profile_id]} — validation mean",
            )
        axis.set_title(title)
        axis.set_ylabel("Relative hourly weight")
        axis.grid(True, axis="y", alpha=0.25)

    axes[1].set_xlabel("Hour of day (local time)")
    axes[0].legend(loc="upper left", fontsize=8, ncol=1, frameon=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_validation_error_by_archetype(results_df: pd.DataFrame, output_path: Path) -> None:
    ordered_labels = [PROFILE_LABELS[profile_id] for profile_id in EMPIRICAL_PROFILE_IDS]
    ordered_values = [
        results_df.loc[results_df["provisional_archetype"] == profile_id, "full_rmse"].to_numpy(dtype=float)
        for profile_id in EMPIRICAL_PROFILE_IDS
    ]

    fig, ax = plt.subplots(figsize=(8.0, 4.8), constrained_layout=True)
    box = ax.boxplot(
        ordered_values,
        labels=ordered_labels,
        patch_artist=True,
        widths=0.55,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "#333333", "markeredgecolor": "#333333", "markersize": 4},
    )

    for patch in box["boxes"]:
        patch.set(facecolor="#F0F0F0", edgecolor="#4C4C4C", linewidth=1.0)
    for median in box["medians"]:
        median.set(color="#222222", linewidth=1.5)
    for whisker in box["whiskers"]:
        whisker.set(color="#4C4C4C", linewidth=1.0)
    for cap in box["caps"]:
        cap.set(color="#4C4C4C", linewidth=1.0)

    ax.set_ylabel("Flattened-profile RMSE")
    ax.set_title("Held-out profile error by provisional archetype")
    ax.grid(True, axis="y", alpha=0.25)
    ax.tick_params(axis="x", labelrotation=10)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
