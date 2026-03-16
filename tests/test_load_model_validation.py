from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.load_model import ARCHETYPE_SCHEMA_VERSION
from src.load_model_build import build_bootstrap_payload, normalize_hourly_weight_vector
from src.load_model_validation import (
    VALIDATION_SCHEMA_VERSION,
    build_centroid_profile_comparisons,
    build_validation_payload,
    compute_profile_metrics,
    deterministic_stratified_validation_split,
    evaluate_validation_households,
    load_validation_reference_asset,
    summarize_validation_results,
)


def _profile_vector(profile_id: str) -> np.ndarray:
    vector = np.zeros((12, 2, 24), dtype=float)
    for month_idx in range(12):
        for day_type_idx in range(2):
            base = np.ones(24, dtype=float)
            if profile_id == "empirical_evening_peaked":
                base[17:23] += 1.4
                base[9:17] += 0.2
            elif profile_id == "empirical_daytime_occupied":
                base[9:17] += 1.4
                base[17:23] += 0.2
            else:
                base[9:17] += 0.8
                base[17:23] += 0.8
            base += 0.01 * month_idx
            base += 0.02 * day_type_idx
            vector[month_idx, day_type_idx] = normalize_hourly_weight_vector(base)
    return vector


def _synthetic_validation_vectors() -> tuple[dict[str, np.ndarray], dict[str, str], dict[str, np.ndarray]]:
    centroids = {
        "empirical_evening_peaked": _profile_vector("empirical_evening_peaked"),
        "empirical_balanced": _profile_vector("empirical_balanced"),
        "empirical_daytime_occupied": _profile_vector("empirical_daytime_occupied"),
    }
    validation_vectors: dict[str, np.ndarray] = {}
    provisional_assignments: dict[str, str] = {}
    for idx, profile_id in enumerate(centroids, start=1):
        perturbation = np.zeros((12, 2, 24), dtype=float)
        perturbation[:, :, (idx + 6) % 24] = 0.03
        perturbation[:, :, (idx + 18) % 24] = -0.015
        vector = centroids[profile_id] + perturbation
        for month_idx in range(12):
            for day_type_idx in range(2):
                vector[month_idx, day_type_idx] = normalize_hourly_weight_vector(vector[month_idx, day_type_idx])
        household_id = f"{profile_id}_household"
        validation_vectors[household_id] = vector
        provisional_assignments[household_id] = profile_id
    return validation_vectors, provisional_assignments, centroids


def test_deterministic_split_is_reproducible_and_disjoint() -> None:
    assignments = {
        **{f"eve_{idx:02d}": "empirical_evening_peaked" for idx in range(10)},
        **{f"bal_{idx:02d}": "empirical_balanced" for idx in range(10)},
        **{f"day_{idx:02d}": "empirical_daytime_occupied" for idx in range(10)},
    }

    split_one = deterministic_stratified_validation_split(assignments, validation_fraction=0.2)
    split_two = deterministic_stratified_validation_split(assignments, validation_fraction=0.2)

    assert split_one == split_two
    assert set(split_one.training_ids).isdisjoint(split_one.validation_ids)
    assert len(split_one.training_ids) + len(split_one.validation_ids) == len(assignments)
    assert sum(counts["validation"] for counts in split_one.counts_by_archetype.values()) == len(split_one.validation_ids)


def test_compute_profile_metrics_returns_finite_non_negative_values() -> None:
    observed = np.linspace(1.0, 2.0, 24 * 2, dtype=float)
    reference = observed + 0.1

    metrics = compute_profile_metrics(observed, reference)

    assert metrics["mae"] >= 0.0
    assert metrics["rmse"] >= 0.0
    assert metrics["euclidean_distance"] >= 0.0
    assert np.isfinite(metrics["mae"])
    assert np.isfinite(metrics["rmse"])
    assert np.isfinite(metrics["euclidean_distance"])
    assert np.isfinite(metrics["pearson_correlation"])


def test_validation_payload_schema_and_counts_from_synthetic_results() -> None:
    validation_vectors, provisional_assignments, centroids = _synthetic_validation_vectors()

    results_df = evaluate_validation_households(validation_vectors, provisional_assignments, centroids)
    overall_metrics, per_archetype_metrics, assignment_summary = summarize_validation_results(results_df)
    centroid_profile_comparisons = build_centroid_profile_comparisons(
        validation_vectors,
        provisional_assignments,
        centroids,
    )
    payload = build_validation_payload(
        reference_asset={
            "schema_version": ARCHETYPE_SCHEMA_VERSION,
            "load_model_version": "uk_empirical_v1",
            "generation_mode": "empirical_from_input",
            "source_name": "Low Carbon London smart-meter dataset",
            "source_target_dataset": "Low Carbon London smart-meter dataset",
        },
        validation_fraction=0.2,
        filtering={"min_completeness": 0.85, "files_processed": 1},
        retained_households_total=15,
        training_households_total=12,
        validation_households_total=len(results_df),
        split_counts_by_archetype={
            "empirical_evening_peaked": {"training": 4, "validation": 1},
            "empirical_balanced": {"training": 4, "validation": 1},
            "empirical_daytime_occupied": {"training": 4, "validation": 1},
        },
        overall_metrics=overall_metrics,
        per_archetype_metrics=per_archetype_metrics,
        centroid_profile_comparisons=centroid_profile_comparisons,
        assignment_summary=assignment_summary,
    )

    assert payload["validation_schema_version"] == VALIDATION_SCHEMA_VERSION
    assert payload["overall_metrics"]["flattened_12x2x24"]["count"] == len(results_df)
    assert payload["overall_metrics"]["weekday_weekend_24h"]["count"] == len(results_df)
    assert set(payload["per_archetype_metrics"].keys()) == {
        "empirical_evening_peaked",
        "empirical_balanced",
        "empirical_daytime_occupied",
    }
    assert (
        sum(item["count"] for item in payload["per_archetype_metrics"].values())
        == payload["validation_households_total"]
    )


def test_bootstrap_reference_asset_is_rejected_without_override(tmp_path) -> None:
    asset_path = tmp_path / "bootstrap_asset.json"
    asset_path.write_text(json.dumps(build_bootstrap_payload()), encoding="utf-8")

    with pytest.raises(ValueError, match="Formal validation requires an empirical reference asset"):
        load_validation_reference_asset(asset_path)

    payload = load_validation_reference_asset(asset_path, allow_bootstrap_asset=True)
    assert payload["generation_mode"] == "bootstrap"
