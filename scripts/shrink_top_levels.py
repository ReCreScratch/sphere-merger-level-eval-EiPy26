"""Shrink the seeds with the biggest greedy/lookahead score gap (read from
data/interesting_levels.json, see agent_batch_timing.py) and save the
before/after results to their own dataset -- a shrunk level's sphere/shot
counts and gap are a different kind of record (before vs. after) than the
plain per-seed scores there, not just another column on the same table.

TOP_N controls how many of the highest-gap seeds to shrink (set it to
len(levels) to shrink the whole batch instead of just the top slice) --
run with a small TOP_N first to gauge per-level shrink time before
committing to a full run.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import prepare_native_batch_worker, record_playthrough
from sphere_merger.game.interesting_levels import load_run, save_run
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.game.shrink import shrink_level
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

        def _gap(level: LevelDefinition) -> int:
            _gs, greedy_score, _gc = record_playthrough(level, greedy)
            _ls, lookahead_score, _lc = record_playthrough(level, lookahead)
            return abs(greedy_score - lookahead_score)

        def _at_least_as_divergent(baseline_gap: int) -> Callable[[LevelDefinition], bool]:
            return lambda lvl: _gap(lvl) >= baseline_gap

        results = []
        total_start = time.perf_counter()
        for entry in candidates:
            seed = entry["seed"]
            baseline_gap = entry["gap"]
            original = _build_level(seed)

            start = time.perf_counter()
            shrunk = shrink_level(original, is_interesting=_at_least_as_divergent(baseline_gap))
            elapsed = time.perf_counter() - start
            shrunk_gap = _gap(shrunk)

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
        },
        levels=results,
        path=OUTPUT_PATH,
    )
