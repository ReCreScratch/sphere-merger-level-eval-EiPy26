"""Manual demo: play one of the three hand-designed baseline levels
(`random_friendly`, `greedy_optimal`, `lookahead_trap`, see 6.1 im
Bericht) yourself, live. Same controls as `play_seed.py`.

Usage: `python scripts/play_baseline.py [level]`, e.g.
`python scripts/play_baseline.py lookahead_trap`.
"""

from __future__ import annotations

import argparse

from sphere_merger.game.baseline_levels import BASELINE_LEVELS
from sphere_merger.rendering.renderer import run_round

DEFAULT_LEVEL = "lookahead_trap"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read which baseline level to play off the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "level",
        nargs="?",
        default=DEFAULT_LEVEL,
        choices=sorted(BASELINE_LEVELS),
        help="Name aus BASELINE_LEVELS",
    )
    return parser.parse_args(argv)


def main(name: str) -> None:
    """Play the baseline level `name` and print the final score."""
    level = BASELINE_LEVELS[name]
    final_state = run_round(level)
    print(f"{name} -- Score: {final_state.score} / {level.target_score}")
    print("Gewonnen!" if final_state.is_won else "Verloren.")


if __name__ == "__main__":
    args = parse_args()
    main(args.level)
