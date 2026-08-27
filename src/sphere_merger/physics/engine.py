"""Advances the physics simulation by fixed time steps (2D, no gravity)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import deal

from sphere_merger.physics.boundary import Boundary, resolve_boundary
from sphere_merger.physics.collision import (
    contact_normal,
    find_colliding_pairs,
    is_colliding,
    resolve_overlap,
)
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

# Broad-phase optimization only (see find_colliding_pairs), not a physical
# resting band: nothing re-drives a settled sphere away from zero velocity,
# so this only has to cover float noise.
_MOVING_EPSILON = 1e-9

# Which backend `step` routes through. Process-wide rather than a
# parameter, because the flag cannot cross process boundaries anyway:
# workers set it themselves via a ProcessPoolExecutor initializer (see
# agents.runner.prepare_native_batch_worker).
_active_backend = "python"


def enable_native_backend() -> None:
    """Switch this process to the native Rust backend permanently."""
    global _active_backend
    _active_backend = "rust"


@contextmanager
def native_backend() -> Iterator[None]:
    """Use the native Rust backend for this block, then restore the previous one."""
    global _active_backend
    previous = _active_backend
    _active_backend = "rust"
    try:
        yield
    finally:
        _active_backend = previous


def current_backend() -> str:
    """`"python"` or `"rust"`, for callers with their own native fast path."""
    return _active_backend


@dataclass
class PhysicsConfig:
    """Tunable physics parameters.

    Attributes:
        friction: Fraction of speed removed from every sphere every step
            (0 = frictionless, 1 = stops dead immediately).
        sphere_restitution: Elasticity of sphere-sphere collisions
            (0 = no bounce-back, 1 = no kinetic energy lost).
        boundary_restitution: Elasticity of contact with the walls. Below
            1 every bounce loses energy until the sphere settles.
    """

    friction: float = 0.0175
    sphere_restitution: float = 0.9
    boundary_restitution: float = 0.6


@deal.pre(lambda spheres, dt, boundary, config=None, collision_filter=None: dt > 0)
def step(
    spheres: list[Sphere],
    dt: float,
    boundary: Boundary,
    config: PhysicsConfig | None = None,
    collision_filter: Callable[[Sphere, Sphere], bool] | None = None,
) -> None:
    """Advance all `spheres` by one time step `dt`, mutating them in place.

    Fixed, deterministic order: integration -> friction -> boundary
    contact -> pairwise collisions (velocity solver, then overlap solver),
    always in `spheres` list order.

    `collision_filter`, if given, is asked about every colliding pair
    before it is resolved; pairs it rejects are left exactly as found, with
    neither bounce nor overlap correction. That lets a caller outside the
    physics layer claim specific pairs for itself -- the game loop merges
    same-level spheres this way -- without the engine knowing why.
    """
    if config is None:
        config = PhysicsConfig()
    if _active_backend == "rust":
        _step_native(spheres, dt, boundary, config, collision_filter)
        return

    for sphere in spheres:
        sphere.position = sphere.position + sphere.velocity * dt
        sphere.velocity = sphere.velocity * (1 - config.friction)
        resolve_boundary(sphere, boundary, config.boundary_restitution)

    for i, j in find_colliding_pairs(spheres, moving_threshold=_MOVING_EPSILON):
        a, b = spheres[i], spheres[j]
        if not is_colliding(a, b):
            continue
        if collision_filter is not None and not collision_filter(a, b):
            continue
        _resolve_velocity(a, b, config.sphere_restitution)
        resolve_overlap(a, b)


def _step_native(
    spheres: list[Sphere],
    dt: float,
    boundary: Boundary,
    config: PhysicsConfig,
    collision_filter: Callable[[Sphere, Sphere], bool] | None,
) -> None:
    """`step`'s native-backend branch.

    `collision_filter` cannot cross the FFI boundary as a Python callable,
    so it collapses to a bool: non-`None` is taken to mean "exclude
    same-level pairs", the only filter any caller passes. **A different
    filter would silently misbehave under this backend.**
    """
    import sphere_merger_native

    boundary_args = (boundary.x_min, boundary.x_max, boundary.y_min, boundary.y_max)
    config_args = (config.friction, config.sphere_restitution, config.boundary_restitution)
    sphere_args = [
        (s.position.x, s.position.y, s.velocity.x, s.velocity.y, s.radius, s.level) for s in spheres
    ]
    updated = sphere_merger_native.step_native(
        sphere_args, dt, boundary_args, config_args, collision_filter is not None
    )
    for sphere, (x, y, vx, vy, _radius, _level) in zip(spheres, updated, strict=True):
        sphere.position = Vector2(x, y)
        sphere.velocity = Vector2(vx, vy)


@deal.pre(lambda a, b, restitution: is_colliding(a, b))
def _resolve_velocity(a: Sphere, b: Sphere, restitution: float) -> None:
    """Impulse-based collision response along the contact normal.

    The standard equal-mass impulse formula, split evenly (no mass, see
    `Sphere`). Tangential velocity is left untouched -- no spin, no
    friction in collisions. Pairs already moving apart are ignored, so a
    restitution-scaled bounce loses energy each time and settles without
    needing a resting-contact special case.
    """
    normal = contact_normal(a, b)

    approach_speed = (a.velocity - b.velocity).dot(normal)
    if approach_speed <= 0:
        return

    impulse = (1 + restitution) * approach_speed / 2
    a.velocity = a.velocity - normal * impulse
    b.velocity = b.velocity + normal * impulse
