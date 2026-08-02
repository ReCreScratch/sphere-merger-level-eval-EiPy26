"""Manual demo: a handful of spheres moving/colliding in a box, rendered live.

No real level generation yet (that's a later milestone) -- this script only
exists to visually inspect the physics engine.
"""

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.renderer import run

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0)

SPHERES = [
    Sphere(Vector2(-6.0, 0.0), Vector2(2.0, 0.5), radius=0.8, level=0),
    Sphere(Vector2(-2.0, 2.0), Vector2(1.0, -1.0), radius=1.0, level=1),
    Sphere(Vector2(2.0, -1.0), Vector2(-1.5, 0.5), radius=0.6, level=2),
    Sphere(Vector2(5.0, 3.0), Vector2(-0.5, -1.5), radius=0.9, level=0),
    Sphere(Vector2(0.0, -4.0), Vector2(0.0, 1.0), radius=0.7, level=3),
]

if __name__ == "__main__":
    run(SPHERES, FIELD)
