"""Manual demo: record greedy/lookahead playthroughs for a fixed list of
seeds and open the grid so they can be watched via Play -- no manual play,
no re-simulation once the window is open.

Python backend only for now: the native extension hasn't been ported to
the 2D/no-gravity physics model yet (see docs/physics_optimizations.md).
"""

from concurrent.futures import ProcessPoolExecutor

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import disable_contracts_in_worker, record_playthrough
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

SEEDS = [44, 49]
FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 20.0


def _build_level(seed: int) -> LevelDefinition:
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=6,
        shot_count=3,
        level_range=(0, 2),
    )


if __name__ == "__main__":
    with ProcessPoolExecutor(initializer=disable_contracts_in_worker) as executor:
        greedy = GreedyAgent(speed=SHOT_SPEED, executor=executor)
        lookahead = LookaheadAgent(speed=SHOT_SPEED, executor=executor)

        cells = {}
        for seed in SEEDS:
            level = _build_level(seed)
            greedy_shots, greedy_score = record_playthrough(level, greedy)
            lookahead_shots, lookahead_score = record_playthrough(level, lookahead)
            print(f"seed {seed}: greedy={greedy_score} lookahead={lookahead_score}")
            cells[f"seed {seed} / greedy ({greedy_score})"] = (level, greedy_shots)
            cells[f"seed {seed} / lookahead ({lookahead_score})"] = (level, lookahead_shots)

    run_agent_grid(cells, columns=2, render_config=RenderConfig(window_size=(1200, 900)))
