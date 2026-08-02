"""Launch the level browser (see rendering.level_browser) on
data/shrunk_levels.json -- pure data loading, no agents/executor needed,
since scripts/shrink_top_levels.py already recorded everything a replay
needs.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from sphere_merger.game.interesting_levels import load_run
from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_browser import BrowserEntry, run_level_browser

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "shrunk_levels.json"


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
    data = load_run(path=DATA_PATH)
    entries = [_build_entry(record, data["meta"]) for record in data["levels"]]
    run_level_browser(entries)
