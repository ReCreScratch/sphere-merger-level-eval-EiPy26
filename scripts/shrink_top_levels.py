"""Shrink every level in the interesting-levels stores (see
agent_batch_timing.py) by dropping every initial sphere neither greedy nor
lookahead ever touches (see agents.runner.shrink_to_used_spheres), and save
the before/after results to their own dataset -- a shrunk level's sphere
counts and gap are a different kind of record (before vs. after) than the
plain per-seed scores there, not just another column on the same table.

Runs once per entry in SPHERE_COUNTS, reading data/interesting_levels_<n>b
.json and writing data/shrunk_levels_<n>b.json -- matches
agent_batch_timing.py's per-sphere-count output files.

Lookahead's touched set on the *original* level comes straight from the
lookahead_shots agent_batch_timing.py already recorded for every level --
no need to re-run its expensive 2-ply search here, it already answered
"what does lookahead touch on this level" once, for free, as a side
effect of scoring it. Only greedy gets re-simulated, once per removal
pass (a removal can change which shots it picks, revealing further
spheres neither agent needs; lookahead's touched set is carried forward
across those passes instead of being recomputed).

Lookahead never runs again after that, not even on the shrunk level: its
original shots are reused as-is for the shrunk score too. That's exact,
not an approximation -- the shrunk level only ever drops spheres this
exact shot sequence never touched or moved, so replaying it on the
smaller field is deterministically identical. What's lost is lookahead
getting a chance to find a *different*, possibly better sequence now
that the field is smaller (the same effect greedy's re-simulation is
allowed to benefit from) -- checked against real data (49/50 top seeds
unaffected, one seed's lookahead score changed 60 -> 68) and accepted
anyway, on user request, to avoid a second full 2-ply sweep per level.

Every candidate from the source file gets shrunk (not just a top slice)
-- shrink_to_used_spheres is cheap enough that this is practical at the
full 1000-level scale.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.runner import prepare_native_batch_worker, shrink_to_used_spheres
from sphere_merger.game.interesting_levels import load_run, save_run
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2

SPHERE_COUNTS = (8, 5)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0


def _source_path(sphere_count: int) -> Path:
    return DATA_DIR / f"interesting_levels_{sphere_count}b.json"


def _output_path(sphere_count: int) -> Path:
    return DATA_DIR / f"shrunk_levels_{sphere_count}b.json"


def _build_level(seed: int, sphere_count: int) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=sphere_count,
        shot_count=2,
        level_range=(0, 2),
    )


def run_shrink(sphere_count: int, greedy: GreedyAgent) -> None:
    """Shrink every level recorded for `sphere_count` and save the results."""
    source = load_run(path=_source_path(sphere_count))
    candidates = source["levels"]

    results = []
    total_start = time.perf_counter()
    for entry in candidates:
        seed = entry["seed"]
        original = _build_level(seed, sphere_count)

        # Already known from agent_batch_timing.py's run -- no need to
        # re-simulate lookahead's expensive 2-ply search just to learn
        # what it touches on the unmodified level.
        original_lookahead_shots = entry["lookahead_shots"]
        original_lookahead_score = entry["lookahead_score"]

        original_lookahead_playthrough = (
            original_lookahead_shots,
            original_lookahead_score,
            entry["lookahead_max_combo"],
        )
        start = time.perf_counter()
        shrink_result = shrink_to_used_spheres(
            original,
            iterated_agents=[greedy],
            fixed_playthroughs=[original_lookahead_playthrough],
        )
        elapsed = time.perf_counter() - start
        shrunk = shrink_result.level

        # Which of the original level's spheres survived, by identity --
        # shrink_to_used_spheres only ever drops spheres (never mutates
        # or reorders the survivors), so this is an exact, cheap way to
        # rebuild the shrunk layout from the seed alone later, instead
        # of re-running the shrink.
        kept_ids = {id(sphere) for sphere in shrunk.initial_spheres}
        kept_sphere_indices = [
            i for i, sphere in enumerate(original.initial_spheres) if id(sphere) in kept_ids
        ]

        # original_greedy/shrunk_greedy were already simulated inside
        # shrink_to_used_spheres (first and final iterated pass).
        original_greedy_shots, original_greedy_score, _ogc = (
            shrink_result.original_iterated_playthroughs[0]
        )
        shrunk_greedy_shots, shrunk_greedy_score, _sgc = shrink_result.final_iterated_playthroughs[
            0
        ]
        # Reused as-is, not re-simulated -- see module docstring for why
        # this is exact rather than an approximation, and what it gives
        # up in exchange for skipping a second full lookahead sweep.
        shrunk_lookahead_shots, shrunk_lookahead_score = (
            original_lookahead_shots,
            original_lookahead_score,
        )
        baseline_gap = abs(original_greedy_score - original_lookahead_score)
        shrunk_gap = abs(shrunk_greedy_score - shrunk_lookahead_score)

        print(
            f"seed {seed:>10}: {len(original.initial_spheres):>2} -> "
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
        f"\n{sphere_count} Kugeln: {len(candidates)} Level geshrinkt in {total_elapsed:.1f}s "
        f"({total_elapsed / len(candidates):.2f}s/Level)"
    )

    save_run(
        meta={
            "source_script": "shrink_top_levels.py",
            "shrunk_from": str(_source_path(sphere_count)),
            "field": {
                "x_min": FIELD.x_min,
                "x_max": FIELD.x_max,
                "y_min": FIELD.y_min,
                "y_max": FIELD.y_max,
            },
            "spawn_margin": SPAWN_MARGIN,
            "target_score": 999,
            "initial_sphere_count": sphere_count,
            "shot_count": 2,
            "level_range": [0, 2],
            "shot_speed": SHOT_SPEED,
        },
        levels=results,
        path=_output_path(sphere_count),
    )


if __name__ == "__main__":
    with (
        ProcessPoolExecutor(initializer=prepare_native_batch_worker) as executor,
        native_backend(),
    ):
        greedy_agent = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        for count in SPHERE_COUNTS:
            run_shrink(count, greedy_agent)
