from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from load_model_build import build_archetype_asset  # noqa: E402


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build month/day-type/hour household load archetypes from the Low Carbon London "
            "smart-meter dataset. This is an offline preprocessing step."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to the official London smart-meter dataset ZIP, a CSV, or a folder containing the CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "load_archetypes_uk_v1.json",
        help="Output JSON asset path.",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=ROOT / "docs" / "load_archetypes_uk_v1_summary.md",
        help="Output markdown summary path.",
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
        "--bootstrap",
        action="store_true",
        help="Write the bundled bootstrap asset instead of processing the official dataset.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if not args.bootstrap and args.input is None:
        parser.error("--input is required unless --bootstrap is set.")
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

    build_archetype_asset(
        input_path=args.input,
        output_path=args.output,
        summary_path=args.summary_output,
        min_completeness=args.min_completeness,
        min_complete_hours=args.min_complete_hours,
        min_complete_half_hours_per_hour=args.min_complete_half_hours_per_hour,
        long_rows_per_chunk=args.long_rows_per_chunk,
        wide_rows_per_chunk=args.wide_rows_per_chunk,
        max_halfhour_kwh=args.max_halfhour_kwh,
        max_sources=args.max_sources,
        bootstrap=bool(args.bootstrap),
    )


if __name__ == "__main__":
    main()
