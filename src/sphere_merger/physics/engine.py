"""Advances the physics simulation by fixed time steps."""

from __future__ import annotations

from dataclasses import dataclass

import deal

from sphere_merger.physics.boundary import Boundary, resolve_boundary
from sphere_merger.physics.collision import find_colliding_pairs, is_colliding, resolve_overlap
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3


@dataclass
class PhysicsConfig:
    """Tunable physics parameters, exposed for a future settings menu."""

    gravity: float = 9.81
    friction: float = 0.1
    sphere_restitution: float = 1.0
    boundary_restitution: float = 1.0


@deal.pre(lambda spheres, dt, boundary, config=None: dt > 0)
def step(
    spheres: list[Sphere],
    dt: float,
    boundary: Boundary,
    config: PhysicsConfig | None = None,
) -> None:
    """Advance all `spheres` by one time step `dt`, mutating them in place.

    Fixed, deterministic order: gravity -> integration -> boundary contact
    (incl. floor friction) -> pairwise sphere collisions (velocity solver,
    then overlap solver) -- always in `spheres` list order.
    """
    if config is None:
        config = PhysicsConfig()

    for sphere in spheres:
        sphere.velocity = Vector3(
            sphere.velocity.x, sphere.velocity.y, sphere.velocity.z - config.gravity * dt
        )
        sphere.position = sphere.position + sphere.velocity * dt
        resolve_boundary(sphere, boundary, config.boundary_restitution)
        if sphere.position.z <= boundary.z_min + sphere.radius + 1e-9:
            sphere.velocity = Vector3(
                sphere.velocity.x * (1 - config.friction),
                sphere.velocity.y * (1 - config.friction),
                sphere.velocity.z,
            )

    for i, j in find_colliding_pairs(spheres):
        a, b = spheres[i], spheres[j]
        if not is_colliding(a, b):
            continue
        _resolve_velocity(a, b, config.sphere_restitution)
        resolve_overlap(a, b)


@deal.pre(lambda a, b, restitution: is_colliding(a, b))
def _resolve_velocity(a: Sphere, b: Sphere, restitution: float) -> None:
    """Impulse-based collision response along the contact normal.

    Tangential velocity is left untouched (no spin/friction in collisions).
    """
    delta = b.position - a.position
    dist = delta.length()
    normal = delta * (1 / dist) if dist > 0 else Vector3(1.0, 0.0, 0.0)

    approach_speed = (a.velocity - b.velocity).dot(normal)
    if approach_speed <= 0:
        return

    impulse = (1 + restitution) * approach_speed / (1 / a.mass + 1 / b.mass)
    a.velocity = a.velocity - normal * (impulse / a.mass)
    b.velocity = b.velocity + normal * (impulse / b.mass)
