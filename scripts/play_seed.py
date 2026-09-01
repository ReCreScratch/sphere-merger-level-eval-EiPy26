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
`python scripts/play_seed.py 44 6b_3s`. A regime nobody has added to
`RUNS` yet can be tried with `--sphere-count`/`--shot-count` instead of a
name, e.g. `python scripts/play_seed.py 44 --sphere-count 7 --shot-count 5`
-- the same two flags `scripts/long_run.py` uses to explore one ad-hoc
regime without touching `RUNS`.
"""

from __future__ import annotations

import argparse

from sphere_merger.game.interesting_levels import RUNS, RunConfig, build_level, select_runs
from sphere_merger.rendering.renderer import run_round

DEFAULT_SEED = 44
DEFAULT_RUN = "6b_3s"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Read `seed`, `regime`, and `--sphere-count`/`--shot-count` off the
    command line.

    `regime` and the `--sphere-count`/`--shot-count` pair are alternatives
    (see `resolve_run`), so `regime` carries no `choices` restriction here
    -- `resolve_run` gives the combined error message once it knows which
    of the two was actually meant.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("seed", nargs="?", type=int, default=DEFAULT_SEED, help="Level-Seed")
    parser.add_argument(
        "regime",
        nargs="?",
        default=None,
        help=f"Lauf aus RUNS, dessen Parameter gelten sollen (Default: {DEFAULT_RUN})",
    )
    parser.add_argument(
        "--sphere-count",
        type=int,
        help="Kugelanzahl fuer ein Regime, das (noch) nicht in RUNS steht",
    )
    parser.add_argument(
        "--shot-count", type=int, help="Schusszahl fuer ein Regime, das (noch) nicht in RUNS steht"
    )
    return parser.parse_args(argv)


def resolve_run(regime: str | None, sphere_count: int | None, shot_count: int | None) -> RunConfig:
    """The `RunConfig` `regime` names in `RUNS`, or an ad-hoc one built
    from `sphere_count`/`shot_count` for a regime nobody has named yet.

    Exactly one of `regime` or the (`sphere_count`, `shot_count`) pair is
    meant to be given; mixing them, or giving only one of the pair, is
    rejected rather than guessed at.

    Raises:
        SystemExit: on any of the above, or an unknown `regime` name.
    """
    if sphere_count is not None or shot_count is not None:
        if regime is not None:
            raise SystemExit(
                "regime laesst sich nicht mit --sphere-count/--shot-count kombinieren."
            )
        if sphere_count is None or shot_count is None:
            raise SystemExit("--sphere-count und --shot-count muessen zusammen angegeben werden.")
        return RunConfig(sphere_count=sphere_count, shot_count=shot_count)

    name = regime or DEFAULT_RUN
    known = {run.name for run in RUNS}
    if name not in known:
        raise SystemExit(
            f"unbekanntes Regime '{name}' (bekannt: {', '.join(sorted(known))}; "
            "oder --sphere-count/--shot-count fuer ein neues)"
        )
    return select_runs([name])[0]


def main(seed: int, run: RunConfig) -> None:
    """Play `seed` under `run` and print the final score."""
    level = build_level(seed, run)
    final_state = run_round(level)
    print(
        f"Seed {seed} ({run.name}: {run.sphere_count} Kugeln, {run.shot_count} Schuss) "
        f"-- Score: {final_state.score} / {level.target_score}"
    )
    print("Gewonnen!" if final_state.is_won else "Verloren.")


if __name__ == "__main__":
    args = parse_args()
    main(args.seed, resolve_run(args.regime, args.sphere_count, args.shot_count))
