from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from load_model import DEFAULT_ARCHETYPE_PATH, EMPIRICAL_PROFILE_IDS, PROFILE_LABELS, load_empirical_archetypes


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot the bundled 24-hour household load archetypes for a chosen month and day type."
    )
    parser.add_argument("--month", type=int, default=1, help="Month number 1-12 (default: 1).")
    parser.add_argument(
        "--day-type",
        choices=["weekday", "weekend"],
        default="weekday",
        help="Day type to plot (default: weekday).",
    )
    parser.add_argument(
        "--asset",
        type=Path,
        default=DEFAULT_ARCHETYPE_PATH,
        help="Path to the load archetype JSON asset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "empirical_load_shape_24h_archetypes.png",
        help="Output PNG path.",
    )
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    if args.month < 1 or args.month > 12:
        raise SystemExit("--month must be between 1 and 12.")

    archetypes = load_empirical_archetypes(args.asset)

    plt.figure(figsize=(8.5, 4.5))
    for profile_id in EMPIRICAL_PROFILE_IDS:
        vector = np.asarray(
            archetypes["archetypes"][profile_id]["weights"][str(args.month)][args.day_type],
            dtype=float,
        )
        plt.plot(range(24), vector, linewidth=2, label=PROFILE_LABELS[profile_id])

    plt.xlabel("Local hour of day")
    plt.ylabel("Relative load weight")
    plt.title(f"Household load archetypes — month {args.month}, {args.day_type}")
    plt.xticks(range(0, 24, 2))
    plt.xlim(0, 23)
    plt.legend()
    plt.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
