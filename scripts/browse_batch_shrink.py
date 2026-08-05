"""Browse every shrunk level of every run (see shrink_top_levels.py) in
the interactive level browser (rendering.level_browser): pick a ranking
(gap increase / most shrunk / least changed), step through it or jump
straight to a rank, and replay original vs. shrunk / greedy vs. lookahead
for exactly the level wanted -- instead of a fixed top-N grid.

Command-line arguments limit it to single runs (`... 6b_3s`); without any,
every run's browser opens in turn.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any

from sphere_merger.game.interesting_levels import load_run, select_runs
from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_browser import BrowserEntry, run_level_browser


def _shot_tuples(raw: list[list[float]]) -> list[tuple[float, float]]:
    return [(angle, speed) for angle, speed in raw]


def _build_entry(record: dict[str, Any], meta: dict[str, Any]) -> BrowserEntry:
    field = meta["field"]
    boundary = Boundary(
        x_min=field["x_min"], x_max=field["x_max"], y_min=field["y_min"], y_max=field["y_max"]
    )
    spawn_position = Vector2(
        boundary.x_min + meta["spawn_margin"], boundary.y_min + meta["spawn_margin"]
    )
    original_level = generate_random_level(
        seed=record["seed"],
        boundary=boundary,
        spawn_position=spawn_position,
        target_score=meta["target_score"],
        initial_sphere_count=meta["initial_sphere_count"],
        shot_count=meta["shot_count"],
        level_range=tuple(meta["level_range"]),
    )
    kept = record["kept_sphere_indices"]
    shrunk_spheres = [original_level.initial_spheres[i] for i in kept]
    shrunk_level = replace(original_level, initial_spheres=shrunk_spheres)

    return BrowserEntry(
        seed=record["seed"],
        original_gap=record["original_gap"],
        shrunk_gap=record["shrunk_gap"],
        spheres_removed=record["spheres_removed"],
        gap_increase=record["gap_increase"],
        original_level=original_level,
        shrunk_level=shrunk_level,
        original_greedy_shots=_shot_tuples(record["original_greedy_shots"]),
        original_lookahead_shots=_shot_tuples(record["original_lookahead_shots"]),
        shrunk_greedy_shots=_shot_tuples(record["shrunk_greedy_shots"]),
        shrunk_lookahead_shots=_shot_tuples(record["shrunk_lookahead_shots"]),
        original_greedy_score=record["original_greedy_score"],
        original_lookahead_score=record["original_lookahead_score"],
        shrunk_greedy_score=record["shrunk_greedy_score"],
        shrunk_lookahead_score=record["shrunk_lookahead_score"],
    )


if __name__ == "__main__":
    for run in select_runs(sys.argv[1:]):
        data = load_run(path=run.shrunk_path)
        entries = [_build_entry(record, data["meta"]) for record in data["levels"]]
        print(f"\n{run.name}: {len(entries)} Level im Browser")
        run_level_browser(entries)
