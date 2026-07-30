"""Manual demo: same starting scenario shot at 32 different angles at once.

Quick visual check of angle-sensitivity and of simulation independence
(no shared state) before this pattern gets used for real agent evaluation.
"""

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3
from sphere_merger.rendering.grid_view import run_angle_sweep
from sphere_merger.rendering.renderer import RenderConfig

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0, z_min=0.0)

SPHERES = [
    Sphere(Vector3(0.0, 0.0, 0.5), Vector3(0.0, 0.0, 0.0), radius=0.5, level=0),
    Sphere(Vector3(3.0, 2.0, 0.6), Vector3(0.0, 0.0, 0.0), radius=0.6, level=1),
    Sphere(Vector3(-2.5, -3.0, 0.5), Vector3(0.0, 0.0, 0.0), radius=0.5, level=0),
    Sphere(Vector3(4.0, -3.5, 0.7), Vector3(0.0, 0.0, 0.0), radius=0.7, level=2),
]
SHOT_SPHERE_INDEX = 0

if __name__ == "__main__":
    # Kept separate from PhysicsConfig's default friction (used by the
    # interactive single-instance demo) so that demo is unaffected.
    run_angle_sweep(
        SPHERES,
        SHOT_SPHERE_INDEX,
        FIELD,
        columns=8,
        rows=4,
        speed=50.0,
        physics_config=PhysicsConfig(friction=0.02),
        render_config=RenderConfig(),
        fullscreen=True,
    )
