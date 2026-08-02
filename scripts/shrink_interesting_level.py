"""Demo: shrink a known-interesting level (fewer initial spheres / shorter
shot queue, see game.shrink) while requiring the greedy/lookahead score gap
to stay at least as large -- for a smaller, easier-to-read example of the
same divergence. Opens both the original and the shrunk level side by side
in the grid so they can be compared by eye.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import prepare_native_batch_worker, record_playthrough
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.game.shrink import shrink_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

SEED = 44
FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0


def _build_level(seed: int) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=6,
        shot_count=2,
        level_range=(0, 2),
    )


if __name__ == "__main__":
    with (
        ProcessPoolExecutor(initializer=prepare_native_batch_worker) as executor,
        native_backend(),
    ):
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        def _gap(level: LevelDefinition) -> int:
            _greedy_shots, greedy_score, _greedy_combo = record_playthrough(level, greedy)
            _lookahead_shots, lookahead_score, _lookahead_combo = record_playthrough(
                level, lookahead
            )
            return abs(greedy_score - lookahead_score)

        original = _build_level(SEED)
        baseline_gap = _gap(original)
        print(
            f"original: {len(original.initial_spheres)} spheres, "
            f"{len(original.shot_queue)} shots, gap {baseline_gap}"
        )

        shrunk = shrink_level(original, is_interesting=lambda lvl: _gap(lvl) >= baseline_gap)
        print(
            f"shrunk:   {len(shrunk.initial_spheres)} spheres, "
            f"{len(shrunk.shot_queue)} shots, gap {_gap(shrunk)}"
        )

        cells = {}
        for name, level in [("original", original), ("shrunk", shrunk)]:
            greedy_shots, greedy_score, _greedy_combo = record_playthrough(level, greedy)
            lookahead_shots, lookahead_score, _lookahead_combo = record_playthrough(
                level, lookahead
            )
            cells[f"{name} / greedy ({greedy_score})"] = (level, greedy_shots)
            cells[f"{name} / lookahead ({lookahead_score})"] = (level, lookahead_shots)

    run_agent_grid(cells, columns=2, render_config=RenderConfig(window_size=(1200, 900)))
