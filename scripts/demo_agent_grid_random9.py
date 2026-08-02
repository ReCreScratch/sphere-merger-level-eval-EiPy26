"""Manual demo: 9 randomly generated levels (6 initial spheres, 2 shots
each, seeds 0-8), all played by the lookahead agent, side by side.

Starts paused on each level's initial layout; Play replays the recorded
playthroughs, Reset returns to the paused layout. Sweeps candidate angles
across worker processes (see LookaheadAgent's `executor` param) to make up
for the doubled angle resolution.
"""

from concurrent.futures import ProcessPoolExecutor

from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.runner import disable_contracts_in_worker, record_shots
from sphere_merger.game.level import LevelDefinition, generate_random_level, radius_for_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector3
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0, z_min=0.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector3(
    FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN, FIELD.z_min + radius_for_level(0)
)
SHOT_SPEED = 15.0


def _build_levels() -> dict[str, LevelDefinition]:
    return {
        f"seed {seed}": generate_random_level(
            seed=seed,
            boundary=FIELD,
            spawn_position=SPAWN,
            target_score=999,
            initial_sphere_count=6,
            shot_count=2,
            level_range=(0, 2),
        )
        for seed in range(9)
    }


if __name__ == "__main__":
    # Executor creation must stay inside this guard: on Windows, worker
    # processes re-import this module, and creating the pool at module
    # level would spawn a new pool (and re-run everything else) in each of
    # them too.
    with ProcessPoolExecutor(initializer=disable_contracts_in_worker) as executor:
        agent = LookaheadAgent(speed=SHOT_SPEED, executor=executor)
        cells = {
            name: (level, record_shots(level, agent)) for name, level in _build_levels().items()
        }
        run_agent_grid(
            cells,
            columns=3,
            render_config=RenderConfig(window_size=(1400, 1000)),
        )
