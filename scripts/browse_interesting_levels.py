"""Launch the side-by-side level-compare view (see
rendering.level_compare) on a hand-picked list of the most interesting
seeds from data/shrunk_levels.json -- the ones that best show off what
shrinking and the greedy/lookahead gap actually do (highest gap, biggest
shrink effects, the one frozen-lookahead edge case, a typical case), not
just whichever sorts first by a single metric.

Pure data loading, no agents/executor needed -- shrink_top_levels.py
already recorded everything a replay needs.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from sphere_merger.game.interesting_levels import load_run
from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_compare import CompareEntry, run_level_compare

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "shrunk_levels.json"

CURATED_SEEDS = [38, 880, 755, 487, 214, 599, 691, 389, 568, 90]
REASONS = {
    38: "Hoechster Original-Gap (78) -- und schon 0 unbenutzte Kugeln",
    90: "Hoechste Combo-Kette im ganzen Batch: Lookahead loest 6 Merges mit einem Schuss aus",
    880: "Groesste Gap-Zunahme (0 -> 32): Greedy ueberholt nach dem Shrink sogar "
    "den eingefrorenen Lookahead-Wert, statt sich ihm nur anzunaehern",
    755: "Groesste Gap-Zunahme: Greedy wird nach dem Shrink deutlich schlechter",
    487: "Groesste Gap-Abnahme (68 -> 36)",
    214: "Der eingefrorene-Lookahead-Grenzfall (Score real 60->68, hier 60 wiederverwendet)",
    599: "Aggressivstes Shrinking: 10 -> 3 Kugeln, Gap bleibt bei 0",
    691: "Zweitgroesste Gap-Abnahme (24 -> 6)",
    389: "Grosse Abnahme (64 -> 52) durch Entfernen einer einzigen Kugel",
    568: "Typischer Fall: 4 Kugeln entfernt, Gap komplett unveraendert",
}


def _shot_tuples(raw: list[list[float]]) -> list[tuple[float, float]]:
    return [(angle, speed) for angle, speed in raw]


def _build_entry(record: dict[str, Any], meta: dict[str, Any]) -> CompareEntry:
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

    return CompareEntry(
        seed=record["seed"],
        reason=REASONS[record["seed"]],
        original_gap=record["original_gap"],
        shrunk_gap=record["shrunk_gap"],
        spheres_removed=record["spheres_removed"],
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
    by_seed = {record["seed"]: record for record in data["levels"]}
    entries = [_build_entry(by_seed[seed], data["meta"]) for seed in CURATED_SEEDS]
    run_level_compare(entries)
