"""Shrink the seeds with the biggest greedy/lookahead score gap (read from
data/interesting_levels.json, see agent_batch_timing.py) by dropping every
initial sphere neither agent ever touches (see
agents.runner.shrink_to_used_spheres), and save the before/after results
to their own dataset -- a shrunk level's sphere counts and gap are a
different kind of record (before vs. after) than the plain per-seed
scores there, not just another column on the same table.

TOP_N controls how many of the highest-gap seeds to shrink (set it to
len(candidates) to shrink the whole batch instead of just the top slice)
-- shrink_to_used_spheres is cheap enough (a few agent-pair runs per
level, not one per single-sphere trial) that this is practical even at
that scale.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import (
    prepare_native_batch_worker,
    record_playthrough,
    shrink_to_used_spheres,
)
from sphere_merger.game.interesting_levels import load_run, save_run
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2

TOP_N = 50
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "shrunk_levels.json"

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
INITIAL_SPHERE_COUNT = 10


def _build_level(seed: int) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=INITIAL_SPHERE_COUNT,
        shot_count=2,
        level_range=(0, 2),
    )


if __name__ == "__main__":
    source = load_run()
    candidates = sorted(source["levels"], key=lambda entry: entry["gap"], reverse=True)[:TOP_N]

    with (
        ProcessPoolExecutor(initializer=prepare_native_batch_worker) as executor,
        native_backend(),
    ):
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        results = []
        total_start = time.perf_counter()
        for entry in candidates:
            seed = entry["seed"]
            original = _build_level(seed)

            start = time.perf_counter()
            shrunk = shrink_to_used_spheres(original, [greedy, lookahead])
            elapsed = time.perf_counter() - start

            # Which of the original level's spheres survived, by identity --
            # shrink_to_used_spheres only ever drops spheres (never mutates
            # or reorders the survivors), so this is an exact, cheap way to
            # rebuild the shrunk layout from the seed alone later, instead
            # of re-running the shrink.
            kept_ids = {id(sphere) for sphere in shrunk.initial_spheres}
            kept_sphere_indices = [
                i for i, sphere in enumerate(original.initial_spheres) if id(sphere) in kept_ids
            ]

            original_greedy_shots, original_greedy_score, _ogc = record_playthrough(
                original, greedy
            )
            original_lookahead_shots, original_lookahead_score, _olc = record_playthrough(
                original, lookahead
            )
            shrunk_greedy_shots, shrunk_greedy_score, _sgc = record_playthrough(shrunk, greedy)
            shrunk_lookahead_shots, shrunk_lookahead_score, _slc = record_playthrough(
                shrunk, lookahead
            )
            baseline_gap = abs(original_greedy_score - original_lookahead_score)
            shrunk_gap = abs(shrunk_greedy_score - shrunk_lookahead_score)

            print(
                f"seed {seed:>4}: {len(original.initial_spheres):>2} -> "
                f"{len(shrunk.initial_spheres):>2} spheres, "
                f"gap {baseline_gap:>3} -> {shrunk_gap:>3}  ({elapsed:.2f}s)"
            )
            results.append(
                {
                    "seed": seed,
                    "original_sphere_count": len(original.initial_spheres),
                    "original_gap": baseline_gap,
                    "shrunk_sphere_count": len(shrunk.initial_spheres),
                    "shrunk_gap": shrunk_gap,
                    "spheres_removed": len(original.initial_spheres) - len(shrunk.initial_spheres),
                    "gap_increase": shrunk_gap - baseline_gap,
                    "shrink_seconds": elapsed,
                    "kept_sphere_indices": kept_sphere_indices,
                    "original_greedy_score": original_greedy_score,
                    "original_lookahead_score": original_lookahead_score,
                    "shrunk_greedy_score": shrunk_greedy_score,
                    "shrunk_lookahead_score": shrunk_lookahead_score,
                    "original_greedy_shots": original_greedy_shots,
                    "original_lookahead_shots": original_lookahead_shots,
                    "shrunk_greedy_shots": shrunk_greedy_shots,
                    "shrunk_lookahead_shots": shrunk_lookahead_shots,
                }
            )

        total_elapsed = time.perf_counter() - total_start

    print(
        f"\n{len(candidates)} Level geshrinkt in {total_elapsed:.1f}s "
        f"({total_elapsed / len(candidates):.2f}s/Level)"
    )

    save_run(
        meta={
            "source_script": "shrink_top_levels.py",
            "shrunk_from": "data/interesting_levels.json",
            "top_n": TOP_N,
            "field": {
                "x_min": FIELD.x_min,
                "x_max": FIELD.x_max,
                "y_min": FIELD.y_min,
                "y_max": FIELD.y_max,
            },
            "spawn_margin": SPAWN_MARGIN,
            "target_score": 999,
            "initial_sphere_count": INITIAL_SPHERE_COUNT,
            "shot_count": 2,
            "level_range": [0, 2],
            "shot_speed": SHOT_SPEED,
        },
        levels=results,
        path=OUTPUT_PATH,
    )
