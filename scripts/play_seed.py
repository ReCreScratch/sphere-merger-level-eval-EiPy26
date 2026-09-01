"""Manual demo: play one of a batch run's levels yourself, live, no agent
pre-simulation involved. Click-drag to aim/shoot; wait for the field to
settle before the next drag is accepted. Reset restarts the same level.

Seed and regime come from the command line, and the level itself from
`game.interesting_levels.build_level` -- the same function the batch
producer uses, so what you play here is exactly the level the agents were
evaluated on. Earlier this script carried its own hard-coded seed and
generation parameters, which meant a copy that could quietly drift away
from the runs it was supposed to reproduce.

Usage: `python scripts/play_seed.py [seed] [regime]`, e.g.
`python scripts/play_seed.py 44 6b_3s`.
"""

from __future__ import annotations

import argparse

from sphere_merger.game.interesting_levels import RUNS, build_level, select_runs
from sphere_merger.rendering.renderer import run_round

DEFAULT_SEED = 44
DEFAULT_RUN = "6b_3s"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read `seed` and `regime` off the command line.

    `regime` is restricted to the names in `RUNS`, so an unknown one is
    rejected with the list of valid names instead of silently generating
    a level no run ever recorded.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed", nargs="?", type=int, default=DEFAULT_SEED, help="Level-Seed")
    parser.add_argument(
        "regime",
        nargs="?",
        default=DEFAULT_RUN,
        choices=[run.name for run in RUNS],
        help="Lauf, dessen Parameter gelten sollen",
    )
    return parser.parse_args(argv)


def main(seed: int, regime: str) -> None:
    """Play `seed` under `regime` and print the final score."""
    run = select_runs([regime])[0]
    level = build_level(seed, run)
    final_state = run_round(level)
    print(
        f"Seed {seed} ({run.name}: {run.sphere_count} Kugeln, {run.shot_count} Schuss) "
        f"-- Score: {final_state.score} / {level.target_score}"
    )
    print("Gewonnen!" if final_state.is_won else "Verloren.")


if __name__ == "__main__":
    args = parse_args()
    main(args.seed, args.regime)
