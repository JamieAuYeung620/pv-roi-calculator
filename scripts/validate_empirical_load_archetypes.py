from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from load_model import DEFAULT_ARCHETYPE_PATH  # noqa: E402
from load_model_build import (  # noqa: E402
    accumulate_household_stats,
    assign_provisional_archetypes,
    build_archetype_centroids,
    compute_global_fallbacks,
    iter_csv_sources,
    normalized_household_vectors,
    retained_households,
)
from load_model_validation import (  # noqa: E402
    build_centroid_profile_comparisons,
    build_validation_payload,
    deterministic_stratified_validation_split,
    evaluate_validation_households,
    load_validation_reference_asset,
    plot_validation_error_by_archetype,
    plot_validation_weekday_weekend,
    summarize_validation_results,
    write_validation_summary_markdown,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic held-out validation for the empirical household load archetypes "
            "using the Low Carbon London smart-meter dataset."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the official London smart-meter dataset ZIP, a CSV, or a folder containing the CSV files.",
    )
    parser.add_argument(
        "--asset",
        type=Path,
        default=DEFAULT_ARCHETYPE_PATH,
        help="Reference runtime archetype asset path (default: data/load_archetypes_uk_v1.json).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "data" / "load_archetypes_validation_v1.json",
        help="Machine-readable validation summary output.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ROOT / "data" / "load_archetypes_validation_households.csv",
        help="Per-household validation results CSV output.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=ROOT / "docs" / "load_archetypes_validation_summary.md",
        help="Human-readable markdown validation summary output.",
    )
    parser.add_argument(
        "--figure-weekday-weekend",
        type=Path,
        default=ROOT / "docs" / "figures" / "load_archetype_validation_weekday_weekend.png",
        help="Output plot comparing training centroids vs held-out mean weekday/weekend profiles.",
    )
    parser.add_argument(
        "--figure-error-by-archetype",
        type=Path,
        default=ROOT / "docs" / "figures" / "load_archetype_validation_profile_error_by_archetype.png",
        help="Output plot showing held-out profile RMSE by archetype.",
    )
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.2,
        help="Held-out validation fraction within each provisional archetype bucket (default: 0.2).",
    )
    parser.add_argument(
        "--min-completeness",
        type=float,
        default=0.85,
        help="Minimum half-hour completeness ratio required to retain a household (default: 0.85).",
    )
    parser.add_argument(
        "--min-complete-hours",
        type=int,
        default=24 * 120,
        help="Minimum number of complete hourly observations required to retain a household (default: 2880).",
    )
    parser.add_argument(
        "--min-complete-half-hours-per-hour",
        type=int,
        default=2,
        help="Minimum number of half-hour observations needed to count an hourly total as complete (default: 2).",
    )
    parser.add_argument(
        "--long-rows-per-chunk",
        type=int,
        default=250_000,
        help="Chunk size for long-format CSV input (default: 250000 rows).",
    )
    parser.add_argument(
        "--wide-rows-per-chunk",
        type=int,
        default=168,
        help="Chunk size for wide-format CSV input with one column per household (default: 168 rows).",
    )
    parser.add_argument(
        "--max-halfhour-kwh",
        type=float,
        default=8.0,
        help="Drop half-hour rows above this kWh threshold as obvious household outliers (default: 8.0).",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=None,
        help="Optional deterministic cap on how many CSV sources from the input archive/folder are processed.",
    )
    parser.add_argument(
        "--allow-bootstrap-asset",
        action="store_true",
        help="Allow formal validation to proceed even if the reference asset is still bootstrap-only.",
    )
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.validation_fraction <= 0.0 or args.validation_fraction >= 1.0:
        parser.error("--validation-fraction must be in (0, 1).")
    if args.min_completeness <= 0.0 or args.min_completeness > 1.0:
        parser.error("--min-completeness must be in (0, 1].")
    if args.min_complete_hours < 24:
        parser.error("--min-complete-hours must be at least 24.")
    if args.min_complete_half_hours_per_hour < 1 or args.min_complete_half_hours_per_hour > 2:
        parser.error("--min-complete-half-hours-per-hour must be 1 or 2.")
    if args.max_halfhour_kwh <= 0.0:
        parser.error("--max-halfhour-kwh must be > 0.")
    if args.max_sources is not None and args.max_sources < 1:
        parser.error("--max-sources must be at least 1 when provided.")


def run_validation(args: argparse.Namespace) -> dict[str, object]:
    reference_asset = load_validation_reference_asset(
        args.asset,
        allow_bootstrap_asset=bool(args.allow_bootstrap_asset),
    )

    sources = iter_csv_sources(args.input)
    if args.max_sources is not None:
        sources = sources[: max(1, int(args.max_sources))]
    if not sources:
        raise FileNotFoundError(f"No CSV files found under: {args.input}")

    households = accumulate_household_stats(
        sources=sources,
        min_complete_half_hours_per_hour=args.min_complete_half_hours_per_hour,
        long_rows_per_chunk=args.long_rows_per_chunk,
        wide_rows_per_chunk=args.wide_rows_per_chunk,
        max_halfhour_kwh=args.max_halfhour_kwh,
    )
    retained = retained_households(
        households,
        min_completeness=args.min_completeness,
        min_complete_hours=args.min_complete_hours,
    )
    if len(retained) < 6:
        raise ValueError(
            "Too few households were retained after filtering for a meaningful held-out validation run. "
            "Relax the thresholds or check the input dataset path."
        )

    provisional_assignments = assign_provisional_archetypes(retained)
    split = deterministic_stratified_validation_split(
        provisional_assignments,
        validation_fraction=float(args.validation_fraction),
    )

    insufficient_profiles = [
        profile_id
        for profile_id, counts in split.counts_by_archetype.items()
        if counts["training"] < 1 or counts["validation"] < 1
    ]
    if insufficient_profiles:
        joined = ", ".join(insufficient_profiles)
        raise ValueError(
            "Formal validation requires at least one training and one validation household in each provisional "
            f"archetype bucket. Insufficient buckets: {joined}"
        )

    training_households = {household_id: retained[household_id] for household_id in split.training_ids}
    validation_households = {household_id: retained[household_id] for household_id in split.validation_ids}

    global_fallbacks = compute_global_fallbacks(training_households)
    training_vectors = normalized_household_vectors(training_households, global_fallbacks)
    validation_vectors = normalized_household_vectors(validation_households, global_fallbacks)
    training_assignments = {household_id: provisional_assignments[household_id] for household_id in split.training_ids}

    centroids = build_archetype_centroids(training_vectors, training_assignments, global_fallbacks)
    results_df = evaluate_validation_households(validation_vectors, provisional_assignments, centroids)
    overall_metrics, per_archetype_metrics, assignment_summary = summarize_validation_results(results_df)
    centroid_profile_comparisons = build_centroid_profile_comparisons(validation_vectors, provisional_assignments, centroids)

    filtering = {
        "min_completeness": float(args.min_completeness),
        "min_complete_hours": int(args.min_complete_hours),
        "min_complete_half_hours_per_hour": int(args.min_complete_half_hours_per_hour),
        "max_halfhour_kwh": float(args.max_halfhour_kwh),
        "files_processed": len(sources),
        "max_sources_requested": None if args.max_sources is None else int(args.max_sources),
    }
    payload = build_validation_payload(
        reference_asset=reference_asset,
        validation_fraction=float(args.validation_fraction),
        filtering=filtering,
        retained_households_total=len(retained),
        training_households_total=len(split.training_ids),
        validation_households_total=len(split.validation_ids),
        split_counts_by_archetype=split.counts_by_archetype,
        overall_metrics=overall_metrics,
        per_archetype_metrics=per_archetype_metrics,
        centroid_profile_comparisons=centroid_profile_comparisons,
        assignment_summary=assignment_summary,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(args.output_csv, index=False)

    write_validation_summary_markdown(payload, args.summary_output)
    plot_validation_weekday_weekend(centroid_profile_comparisons, args.figure_weekday_weekend)
    plot_validation_error_by_archetype(results_df, args.figure_error_by_archetype)

    print(f"Wrote validation JSON:     {args.output_json}")
    print(f"Wrote household CSV:       {args.output_csv}")
    print(f"Wrote markdown summary:    {args.summary_output}")
    print(f"Wrote weekday/weekend fig: {args.figure_weekday_weekend}")
    print(f"Wrote error figure:        {args.figure_error_by_archetype}")
    return payload


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    run_validation(args)


if __name__ == "__main__":
    main()
