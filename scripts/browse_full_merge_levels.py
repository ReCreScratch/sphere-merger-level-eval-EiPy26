"""Level-compare view for the full_mergeable regimes (see
docs/full_merge_experiment.md). Curates by whether a playthrough actually
collapsed the level to one sphere, not by greedy/lookahead score gap like
`browse_interesting_levels.py` -- every level here already has
`merge_popcount == 1` by construction, so the open question is whether an
agent's shot choices (not the level's arithmetic) get it there.

Usage: `python scripts/browse_full_merge_levels.py [regime ...]` --
without arguments, every regime in `RUNS` with `full_mergeable=True` that
has data on disk.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from browse_interesting_levels import _build_entry  # noqa: E402

from sphere_merger.game.interesting_levels import (  # noqa: E402
    RUNS,
    RunConfig,
    load_run,
    select_runs,
)
from sphere_merger.rendering.level_compare import CompareEntry, run_level_compare  # noqa: E402

COUNT = 6
FULL_MERGE_RUNS = tuple(run for run in RUNS if run.full_mergeable)

LevelRecord = dict[str, Any]


def _final_count(states: list[list[list[float]]]) -> int:
    """How many spheres a recorded playthrough ends with."""
    return len(states[-1])


def _top(
    levels: list[LevelRecord],
    predicate: Callable[[LevelRecord], bool],
    key: Callable[[LevelRecord], float],
    reason: Callable[[LevelRecord], str],
    count: int,
) -> list[tuple[int, str]]:
    """The best `count` levels matching `predicate`, ranked by `key`
    (highest wins), each paired with its sidebar reason string."""
    matches = sorted((level for level in levels if predicate(level)), key=key, reverse=True)
    return [(level["seed"], reason(level)) for level in matches[:count]]


def curated_entries(run: RunConfig, count: int = COUNT) -> list[CompareEntry]:
    """The most telling levels of `run` for the full-merge question --
    does an agent actually reach one sphere, and where do greedy and
    lookahead visibly diverge on that -- rather than the general gap/combo
    categories `browse_interesting_levels.py` curates."""
    try:
        source = load_run(path=run.interesting_path)
        shrunk_run = load_run(path=run.shrunk_path)
    except FileNotFoundError:
        return []
    if not source["levels"]:
        return []

    shrunk_by_seed = {entry["seed"]: entry for entry in shrunk_run["levels"]}
    levels: list[LevelRecord] = source["levels"]

    groups = [
        _top(
            levels,
            predicate=lambda level: _final_count(level["lookahead_states"]) == 1,
            key=lambda level: level["lookahead_score"],
            reason=lambda level: (
                f"[{run.name}] Lookahead schafft Vollmerge (Score {level['lookahead_score']})"
            ),
            count=count,
        ),
        _top(
            levels,
            predicate=lambda level: (
                _final_count(level["greedy_states"]) == 1
                and _final_count(level["lookahead_states"]) > 1
            ),
            key=lambda level: _final_count(level["lookahead_states"]),
            reason=lambda level: (
                f"[{run.name}] Greedy schafft Vollmerge, Lookahead nicht "
                f"({_final_count(level['lookahead_states'])} Kugeln uebrig)"
            ),
            count=count,
        ),
        _top(
            levels,
            predicate=lambda level: _final_count(level["lookahead_states"]) == 2,
            key=lambda level: level["lookahead_score"],
            reason=lambda level: (
                f"[{run.name}] Lookahead knapp verfehlt (2 Kugeln uebrig, "
                f"Score {level['lookahead_score']})"
            ),
            count=count,
        ),
    ]

    ordered: list[tuple[int, str]] = []
    seen: set[int] = set()
    for group in groups:
        for seed, reason in group:
            if seed not in seen:
                seen.add(seed)
                ordered.append((seed, reason))

    return [
        _build_entry(shrunk_by_seed[seed], shrunk_run["meta"], reason)
        for seed, reason in ordered
        if seed in shrunk_by_seed
    ]


if __name__ == "__main__":
    selected = select_runs(sys.argv[1:]) if sys.argv[1:] else FULL_MERGE_RUNS
    combined: list[CompareEntry] = []
    for run in selected:
        entries = curated_entries(run)
        if entries:
            print(f"{run.name}: {len(entries)} Level")
            combined.extend(entries)

    print(f"\n{len(combined)} Level insgesamt im Compare-View")
    run_level_compare(combined)
