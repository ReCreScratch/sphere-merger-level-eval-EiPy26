"""Manual demo: play a hand-picked seed from one of the full-mergeable
regimes (4.4 im Bericht) yourself, live. Same controls as `play_seed.py`.

Every entry below is just a (regime, seed) pair -- `build_level`
reconstructs the level deterministically, so nothing here depends on the
raw batch-run data files (`data/interesting_levels_*_fm.json`), which are
too large for the repository and stay local-only (see `.gitignore`).
Picking these seeds *did* use that local data (highest gap among levels
where `LookaheadAgent` actually reached the full merge), but this script
itself only needs the seed.

Usage: `python scripts/play_curated.py [level]`, e.g.
`python scripts/play_curated.py 3b_5s_fm_full_merge`.
"""

from __future__ import annotations

import argparse

from sphere_merger.game.interesting_levels import build_level, select_runs
from sphere_merger.rendering.renderer import run_round

# name -> (regime, seed, reason). Each is the highest-gap level, among all
# seeds of its regime, where LookaheadAgent's own playthrough happened to
# fully merge the field to one sphere -- picked from a local
# `interesting_levels_<regime>.json`, verified by replaying its recorded
# `lookahead_shots` and comparing to `lookahead_score` (see docs/ki_log.md).
CURATED: dict[str, tuple[str, int, str]] = {
    "4b_2s_fm_full_merge": (
        "4b_2s_fm",
        455490515,
        "Vollstaendiger Merge in 2 Schuessen, Gap 36 (greedy 20 / lookahead 56)",
    ),
    "3b_3s_fm_full_merge": (
        "3b_3s_fm",
        856215386,
        "Vollstaendiger Merge in 3 Schuessen, Gap 88 (greedy 18 / lookahead 106)",
    ),
    "2b_4s_fm_full_merge": (
        "2b_4s_fm",
        791709722,
        "Vollstaendiger Merge in 4 Schuessen, Gap 84 (greedy 22 / lookahead 106)",
    ),
    "3b_5s_fm_full_merge": (
        "3b_5s_fm",
        969685452,
        "Vollstaendiger Merge in 5 Schuessen, Gap 160 -- der groesste hier",
    ),
}

DEFAULT_LEVEL = "3b_5s_fm_full_merge"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read which curated level to play off the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "level",
        nargs="?",
        default=DEFAULT_LEVEL,
        choices=sorted(CURATED),
        help="Name aus CURATED",
    )
    return parser.parse_args(argv)


def main(name: str) -> None:
    """Play the curated entry `name` and print the final score."""
    regime, seed, reason = CURATED[name]
    run = select_runs([regime])[0]
    level = build_level(seed, run)
    print(f"{name}: {reason}")
    final_state = run_round(level)
    merged = len(final_state.spheres) == 1
    print(
        f"Seed {seed} ({regime}) -- Score: {final_state.score}"
        + (
            " -- vollstaendig verschmolzen!"
            if merged
            else f" -- {len(final_state.spheres)} Kugeln uebrig"
        )
    )


if __name__ == "__main__":
    args = parse_args()
    main(args.level)
