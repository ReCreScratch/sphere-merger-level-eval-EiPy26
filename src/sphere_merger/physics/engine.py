"""Advances the physics simulation by fixed time steps."""

from __future__ import annotations

import math
from collections.abc import Callable
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
from sphere_merger.physics.vector import Vector3


@dataclass
class PhysicsConfig:
    """Tunable physics parameters, exposed for a future settings menu.

    Attributes:
        gravity: Downward acceleration applied to `velocity.z` each step
            (units/s^2). Higher = falls faster.
        friction_min: Fraction of horizontal speed removed per step while a
            sphere rests on the floor, applied at/above
            `friction_speed_threshold` (0 = frictionless ice, 1 = stops dead
            on contact). Kept low so a fast sphere still slides far enough
            for bank shots off other spheres/walls.
        friction_max: Friction fraction applied as horizontal speed
            approaches zero. Higher than `friction_min` so a nearly-stopped
            sphere snaps to rest quickly instead of crawling for hundreds of
            extra steps.
        friction_speed_threshold: Horizontal speed at/above which
            `friction_min` applies; between 0 and this speed, friction ramps
            linearly down to `friction_min` as speed increases.
        sphere_restitution: Elasticity of sphere-sphere collisions (0 = fully
            inelastic, spheres stick to their post-collision velocity with no
            bounce-back; 1 = fully elastic, no kinetic energy lost).
        boundary_restitution: Elasticity of contact with the field boundary
            (floor and walls). At 1.0 the floor is a perfect trampoline and a
            falling sphere bounces forever at the same height; values below 1
            lose energy on every bounce until the sphere settles.
        rest_threshold_factor: Multiplier on `gravity * dt` (one step's worth
            of gravity) below which boundary contact is treated as resting
            instead of bouncing. Without this, a settling sphere never fully
            stops -- it converges to a small non-zero "jitter" velocity
            instead, a discretization artifact rather than real physics. The
            steady-state jitter speed is always < `gravity * dt`, so a
            factor of 1.0 reliably stops it regardless of
            `boundary_restitution`; 0 disables resting altogether.
    """

    gravity: float = 9.81
    friction_min: float = 0.015
    friction_max: float = 0.3
    friction_speed_threshold: float = 6.0
    sphere_restitution: float = 0.9
    boundary_restitution: float = 0.6
    rest_threshold_factor: float = 1.0


@deal.pre(lambda spheres, dt, boundary, config=None, collision_filter=None: dt > 0)
def step(
    spheres: list[Sphere],
    dt: float,
    boundary: Boundary,
    config: PhysicsConfig | None = None,
    collision_filter: Callable[[Sphere, Sphere], bool] | None = None,
) -> None:
    """Advance all `spheres` by one time step `dt`, mutating them in place.

    Fixed, deterministic order: gravity -> integration -> boundary contact
    (incl. floor friction) -> pairwise sphere collisions (velocity solver,
    then overlap solver) -- always in `spheres` list order.

    `collision_filter`, if given, is checked for every colliding pair before
    resolving it; pairs for which it returns `False` are left exactly as
    found (no bounce, no overlap correction). This lets callers outside the
    physics layer take over specific pairs themselves -- e.g. the game loop
    handling same-level spheres as a merge instead of a bounce -- without
    the physics engine needing to know why.
    """
    if config is None:
        config = PhysicsConfig()
    rest_velocity_threshold = config.rest_threshold_factor * config.gravity * dt

    for sphere in spheres:
        sphere.velocity = Vector3(
            sphere.velocity.x, sphere.velocity.y, sphere.velocity.z - config.gravity * dt
        )
        sphere.position = sphere.position + sphere.velocity * dt
        resolve_boundary(sphere, boundary, config.boundary_restitution, rest_velocity_threshold)
        if sphere.position.z <= boundary.z_min + sphere.radius + 1e-9:
            friction = _resting_friction(sphere.velocity, config)
            sphere.velocity = Vector3(
                sphere.velocity.x * (1 - friction),
                sphere.velocity.y * (1 - friction),
                sphere.velocity.z,
            )

    for i, j in find_colliding_pairs(spheres):
        a, b = spheres[i], spheres[j]
        if not is_colliding(a, b):
            continue
        if collision_filter is not None and not collision_filter(a, b):
            continue
        _resolve_velocity(a, b, config.sphere_restitution, rest_velocity_threshold)
        resolve_overlap(a, b)


def _resting_friction(velocity: Vector3, config: PhysicsConfig) -> float:
    """Friction fraction for a sphere resting on the floor at `velocity`.

    Linearly interpolates from `friction_max` at zero horizontal speed down
    to `friction_min` at/above `friction_speed_threshold`: fast spheres keep
    sliding (bank shots stay possible), slow ones shed their last bit of
    speed quickly instead of crawling for hundreds of extra steps.

    >>> config = PhysicsConfig(friction_min=0.0, friction_max=0.4, friction_speed_threshold=4.0)
    >>> _resting_friction(Vector3(4.0, 0.0, 0.0), config)
    0.0
    >>> _resting_friction(Vector3(0.0, 0.0, 0.0), config)
    0.4
    >>> _resting_friction(Vector3(2.0, 0.0, 0.0), config)
    0.2
    """
    horizontal_speed = math.hypot(velocity.x, velocity.y)
    speed_fraction = min(horizontal_speed / config.friction_speed_threshold, 1.0)
    return config.friction_max - (config.friction_max - config.friction_min) * speed_fraction


@deal.pre(lambda a, b, restitution, rest_velocity_threshold=0.0: is_colliding(a, b))
def _resolve_velocity(
    a: Sphere, b: Sphere, restitution: float, rest_velocity_threshold: float = 0.0
) -> None:
    """Impulse-based collision response along the contact normal.

    Tangential velocity is left untouched (no spin/friction in collisions).
    Below `rest_velocity_threshold`, the collision is treated as resting
    contact (fully inelastic along the normal) rather than a bounce. This
    matters for stacked spheres: gravity re-drives the same tiny approach
    speed into the contact every step (like it does at the floor), and
    without a rest case, that would jitter forever instead of settling --
    the same discretization artifact `resolve_boundary`'s
    `rest_velocity_threshold` already guards against.
    """
    normal = contact_normal(a, b)

    approach_speed = (a.velocity - b.velocity).dot(normal)
    if approach_speed <= 0:
        return

    effective_restitution = 0.0 if approach_speed < rest_velocity_threshold else restitution
    impulse = (1 + effective_restitution) * approach_speed / (1 / a.mass + 1 / b.mass)
    a.velocity = a.velocity - normal * (impulse / a.mass)
    b.velocity = b.velocity + normal * (impulse / b.mass)
