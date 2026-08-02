"""Manual demo: a random level (seed 0, 6 initial spheres, 2 shots, shot
speed 20) where lookahead scores more than greedy -- found by scanning
seeds 0-19 for the first level where lookahead's final score beats
greedy's (it turned out to be the very first one tried: greedy 18,
lookahead 30).

Shots are precomputed constants (recorded once at 1-degree sweep
resolution) rather than simulated at startup -- the agents already ran
their search when this level was found, so there is nothing left to
re-simulate here, just replay.

Starts paused on the level's initial layout; Play replays both recorded
playthroughs side by side, Reset returns to the paused layout.
"""

from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import run_agent_grid
from sphere_merger.rendering.renderer import RenderConfig

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 20.0
SEED = 0

# Recorded ahead of time via agents.runner.record_shots (1-degree sweep)
# -- greedy scores 18, lookahead scores 30.
GREEDY_SHOTS = [(28.0, SHOT_SPEED), (27.0, SHOT_SPEED)]
LOOKAHEAD_SHOTS = [(29.0, SHOT_SPEED), (28.0, SHOT_SPEED)]

if __name__ == "__main__":
    level = generate_random_level(
        seed=SEED,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=999,
        initial_sphere_count=6,
        shot_count=2,
        level_range=(0, 2),
    )
    cells = {
        "greedy": (level, GREEDY_SHOTS),
        "lookahead": (level, LOOKAHEAD_SHOTS),
    }
    run_agent_grid(cells, columns=2, render_config=RenderConfig(window_size=(1200, 700)))
