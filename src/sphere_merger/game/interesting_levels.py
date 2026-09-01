"""Persistent store of one batch run's levels, so they can be revisited
without re-running the search that found them.

Holds one run at a time; a new run replaces it wholesale rather than
merging in. Shared generation parameters (`meta`) are stored once and
per-level records (`levels`) hold only what varies, since reproducing a
level needs nothing but its seed plus `meta` -- generation is
deterministic.

`RUNS` below is the one place that says which batch runs exist. Every
script that produces or reads a run's files (`long_run.py`,
`build_dashboard_data.py`, `browse_interesting_levels.py`) iterates it
instead of keeping its own copy of the parameters.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sphere_merger.game.level import (
    LevelDefinition,
    generate_full_mergeable_level,
    generate_random_level,
)
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "interesting_levels.json"
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
TARGET_SCORE = 999
LEVEL_RANGE = (0, 2)
"""Everything a level needs beyond its `RunConfig`, in the same place as
`RUNS`: what a seed means depends on all of it, so a script keeping its
own copy would silently describe a different level under the same seed."""


@dataclass(frozen=True)
class RunConfig:
    """One batch run's level-generation parameters and the files it owns.

    A run is a difficulty regime, not a row of a shared table: changing
    the sphere count or shot-queue length makes results incomparable to
    the previous ones, so each combination owns its own pair of files.

    `slug` names those files, defaulting to `<n>b_<s>s`. The first two
    runs predate a variable shot count and stay pinned to their original
    `<n>b` names, since renaming would buy nothing but a diff.

    `full_mergeable` switches `long_run.py` to
    `generate_full_mergeable_level`, making `merge_popcount == 1` true by
    construction rather than by chance (see
    `docs/full_merge_experiment.md`).
    """

    sphere_count: int
    shot_count: int
    slug: str | None = None
    full_mergeable: bool = False

    @property
    def name(self) -> str:
        """Filename stem of this run -- explicit `slug` or `<n>b_<s>s`.

        >>> RunConfig(sphere_count=6, shot_count=3).name
        '6b_3s'
        >>> RunConfig(sphere_count=8, shot_count=2, slug="8b").name
        '8b'
        """
        return self.slug or f"{self.sphere_count}b_{self.shot_count}s"

    @property
    def interesting_path(self) -> Path:
        """Where `long_run.py` writes this run's raw records."""
        return DATA_DIR / f"interesting_levels_{self.name}.json"

    @property
    def shrunk_path(self) -> Path:
        """Where `long_run.py` writes this run's shrink results."""
        return DATA_DIR / f"shrunk_levels_{self.name}.json"


RUNS: tuple[RunConfig, ...] = (
    RunConfig(sphere_count=8, shot_count=2, slug="8b"),
    RunConfig(sphere_count=5, shot_count=2, slug="5b"),
    RunConfig(sphere_count=6, shot_count=3),
    RunConfig(sphere_count=10, shot_count=2),
    RunConfig(sphere_count=5, shot_count=3),
    RunConfig(sphere_count=8, shot_count=3),
    RunConfig(sphere_count=10, shot_count=3),
    RunConfig(sphere_count=5, shot_count=4),
    RunConfig(sphere_count=8, shot_count=4),
    RunConfig(sphere_count=10, shot_count=4),
    RunConfig(sphere_count=4, shot_count=2, slug="4b_2s_fm", full_mergeable=True),
    RunConfig(sphere_count=3, shot_count=3, slug="3b_3s_fm", full_mergeable=True),
    RunConfig(sphere_count=2, shot_count=4, slug="2b_4s_fm", full_mergeable=True),
    RunConfig(sphere_count=3, shot_count=5, slug="3b_5s_fm", full_mergeable=True),
)


def select_runs(names: Sequence[str]) -> tuple[RunConfig, ...]:
    """The runs in `RUNS` named by `names` (all of them if `names` is empty).

    Producing scripts take these names as command-line arguments so a
    re-run can target one regime. That matters because `save_run` replaces
    its target wholesale with fresh seeds -- defaulting to all of `RUNS`
    would silently discard every other regime's results.

    >>> [run.name for run in select_runs(["6b_3s"])]
    ['6b_3s']

    Raises:
        KeyError: if a name doesn't match any run in `RUNS`.
    """
    if not names:
        return RUNS
    known = {run.name: run for run in RUNS}
    unknown = [name for name in names if name not in known]
    if unknown:
        raise KeyError(f"unbekannte Runs: {', '.join(unknown)} (bekannt: {', '.join(known)})")
    return tuple(known[name] for name in names)


def build_level(seed: int, run: RunConfig) -> LevelDefinition:
    """The level `seed` denotes under `run`, with the shared parameters above.

    The single definition of "which level is seed 44 of regime 6b_3s" --
    used by the batch producer and by the interactive `play_seed.py`, so
    what a run recorded and what a human replays cannot drift apart.
    """
    generator = generate_full_mergeable_level if run.full_mergeable else generate_random_level
    return generator(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=TARGET_SCORE,
        initial_sphere_count=run.sphere_count,
        shot_count=run.shot_count,
        level_range=LEVEL_RANGE,
    )


def load_run(path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """`{"meta": ..., "levels": ...}` currently stored at `path`
    (`{"meta": {}, "levels": []}` if it doesn't exist yet)."""
    if not path.exists():
        return {"meta": {}, "levels": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(
    meta: dict[str, Any], levels: list[dict[str, Any]], path: Path = DEFAULT_DB_PATH
) -> None:
    """Replace `path` with this run's `meta` and its per-level `levels`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "levels": levels}, indent=2) + "\n", encoding="utf-8")
