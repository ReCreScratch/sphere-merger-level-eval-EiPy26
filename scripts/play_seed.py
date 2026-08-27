"""Manual demo: play a specific batch-run seed yourself, live, no agent
pre-simulation involved -- same generation parameters as
scripts/long_run.py, so it's the exact same level the agents were
evaluated on. Click-drag to aim/shoot; wait for the field to settle
before the next drag is accepted. Reset restarts the same level.
"""

from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.renderer import run_round

SEED = 44

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)

LEVEL = generate_random_level(
    seed=SEED,
    boundary=FIELD,
    spawn_position=SPAWN,
    target_score=999,
    initial_sphere_count=6,
    shot_count=3,
    level_range=(0, 2),
)

if __name__ == "__main__":
    final_state = run_round(LEVEL)
    print(f"Seed {SEED} -- Score: {final_state.score} / {LEVEL.target_score}")
    print("Gewonnen!" if final_state.is_won else "Verloren.")
