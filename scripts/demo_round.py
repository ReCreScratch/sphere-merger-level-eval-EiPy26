"""Manual demo: play one round via `rendering.renderer.run_round`.

Click-drag to aim/shoot the next queued sphere; wait for the field to
settle before the next drag is accepted. Reset restarts the same level.
"""

from sphere_merger.game.level import generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector3
from sphere_merger.rendering.renderer import run_round

FIELD = Boundary(x_min=-8.0, x_max=8.0, y_min=-8.0, y_max=8.0, z_min=0.0)
SPAWN = Vector3(0.0, 7.0, 3.0)

LEVEL = generate_random_level(
    seed=42,
    boundary=FIELD,
    spawn_position=SPAWN,
    target_score=50,
    initial_sphere_count=8,
    shot_count=10,
    level_range=(0, 2),
)

if __name__ == "__main__":
    final_state = run_round(LEVEL)
    print(f"Score: {final_state.score} / {LEVEL.target_score}")
    print("Gewonnen!" if final_state.is_won else "Verloren.")
