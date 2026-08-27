"""Persistent store of one batch run's levels -- e.g. ones where different
agents' scores diverge notably -- found while batch-testing agents, so
they can be revisited without re-running the search that found them.

Holds a single run's worth of data at a time (a new run replaces it
wholesale, not merged in) -- shared generation parameters (`meta`) are
stored once, per-level records (`levels`) hold only what actually varies
(seed + whatever scores the caller wants alongside it). Reproducing a
level needs only its seed plus `meta`: `generate_random_level` is
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

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "interesting_levels.json"
DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@dataclass(frozen=True)
class RunConfig:
    """One batch run's level-generation parameters and the files it owns.

    A run is a difficulty regime, not a row of a shared table: changing an
    initial sphere count or the shot-queue length makes the results
    incomparable to the previous ones, so each combination gets its own
    pair of files rather than overwriting the last run's.

    `slug` names those files. It defaults to `<n>b_<s>s`, but the first two
    runs below predate the shot count being variable and are pinned to
    their original `<n>b` names -- renaming their files would have bought
    nothing but a diff.

    `full_mergeable` switches `long_run.py`'s generator from
    `generate_random_level` to `generate_full_mergeable_level` (see
    `docs/full_merge_experiment.md`) -- every sphere the level will ever
    show, start plus shot queue, is then guaranteed constructible down to
    one single sphere, `merge_popcount == 1` by construction rather than by
    chance.
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

    Producing scripts take these names as command-line arguments, so a
    re-run can target a single regime: `save_run` replaces its target file
    wholesale and draws fresh seeds, so iterating all of `RUNS` by default
    would silently discard the other regimes' existing results.

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


def load_run(path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """`{"meta": ..., "levels": ...}` currently stored at `path`
    (`{"meta": {}, "levels": []}` if it doesn't exist yet)."""
    if not path.exists():
        return {"meta": {}, "levels": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(
    meta: dict[str, Any], levels: list[dict[str, Any]], path: Path = DEFAULT_DB_PATH
) -> None:
    """Replace `path`'s contents with `meta` (shared generation parameters
    for this run) and `levels` (one record per level, minimal per-level
    fields only -- e.g. seed + scores)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "levels": levels}, indent=2) + "\n", encoding="utf-8")
