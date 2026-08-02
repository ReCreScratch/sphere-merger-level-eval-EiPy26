"""Advances the physics simulation by fixed time steps."""

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
from sphere_merger.physics.vector import Vector3

_active_backend = "python"


def enable_native_backend() -> None:
    """Route `step` through the native Rust extension (`sphere_merger_native`,
    see `native/sphere_merger_native/` and README.md) for the rest of this
    process, permanently.

    Global (process-wide) switch rather than a parameter threaded through
    every caller (`advance_physics`, `play_shot`, `simulate_shot`, agents,
    runner...) -- mirrors `agents.runner.disable_contracts_in_worker`'s
    pattern, meant to be used the same way (as a `ProcessPoolExecutor`
    `initializer`, see `agents.runner.prepare_native_batch_worker`) since
    the flag doesn't cross process boundaries either. For the calling
    process itself, prefer the scoped `native_backend()` context manager.
    """
    global _active_backend
    _active_backend = "rust"


@contextmanager
def native_backend() -> Iterator[None]:
    """Route `step` through the native Rust extension for the duration of
    the block, then restore whatever backend was active before.

    See `enable_native_backend` for why this is a global switch, not a
    parameter.
    """
    global _active_backend
    previous = _active_backend
    _active_backend = "rust"
    try:
        yield
    finally:
        _active_backend = previous


def current_backend() -> str:
    """`"python"` or `"rust"` -- whichever backend `step` (and callers that
    check this themselves, e.g. `agents.base.simulate_shot`'s own native
    fast path) currently route through.
    """
    return _active_backend


@dataclass
class PhysicsConfig:
    """Tunable physics parameters, exposed for a future settings menu.

    Attributes:
        gravity: Downward acceleration applied to `velocity.z` each step
            (units/s^2). Higher = falls faster.
        friction: Fraction of horizontal speed removed per step while a
            sphere rests on the floor (0 = frictionless ice, 1 = stops dead
            on contact).
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
    friction: float = 0.02
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
    if _active_backend == "rust":
        _step_native(spheres, dt, boundary, config, collision_filter)
        return
    rest_velocity_threshold = config.rest_threshold_factor * config.gravity * dt

    for sphere in spheres:
        sphere.velocity = Vector3(
            sphere.velocity.x, sphere.velocity.y, sphere.velocity.z - config.gravity * dt
        )
        sphere.position = sphere.position + sphere.velocity * dt
        resolve_boundary(sphere, boundary, config.boundary_restitution, rest_velocity_threshold)
        if sphere.position.z <= boundary.z_min + sphere.radius + 1e-9:
            sphere.velocity = Vector3(
                sphere.velocity.x * (1 - config.friction),
                sphere.velocity.y * (1 - config.friction),
                sphere.velocity.z,
            )

    for i, j in find_colliding_pairs(spheres, moving_threshold=rest_velocity_threshold):
        a, b = spheres[i], spheres[j]
        if not is_colliding(a, b):
            continue
        if collision_filter is not None and not collision_filter(a, b):
            continue
        _resolve_velocity(a, b, config.sphere_restitution, rest_velocity_threshold)
        resolve_overlap(a, b)


def _step_native(
    spheres: list[Sphere],
    dt: float,
    boundary: Boundary,
    config: PhysicsConfig,
    collision_filter: Callable[[Sphere, Sphere], bool] | None,
) -> None:
    """`step`'s native-backend branch, active while `native_backend()` (or
    `enable_native_backend()`) is in effect.

    `collision_filter` can't cross the FFI boundary as an arbitrary Python
    callable, so it's collapsed to a bool: non-`None` is assumed to mean
    "exclude same-level pairs", the only filter `game.round.advance_physics`
    (the sole caller that ever passes one) uses. A genuinely different
    filter would silently misbehave under this backend.
    """
    import sphere_merger_native

    boundary_args = (
        boundary.x_min,
        boundary.x_max,
        boundary.y_min,
        boundary.y_max,
        boundary.z_min,
        boundary.z_max,
    )
    config_args = (
        config.gravity,
        config.friction,
        config.sphere_restitution,
        config.boundary_restitution,
        config.rest_threshold_factor,
    )
    sphere_args = [
        (
            s.position.x,
            s.position.y,
            s.position.z,
            s.velocity.x,
            s.velocity.y,
            s.velocity.z,
            s.radius,
            s.level,
        )
        for s in spheres
    ]
    updated = sphere_merger_native.step_native(
        sphere_args, dt, boundary_args, config_args, collision_filter is not None
    )
    for sphere, (x, y, z, vx, vy, vz, _radius, _level) in zip(spheres, updated, strict=True):
        sphere.position = Vector3(x, y, z)
        sphere.velocity = Vector3(vx, vy, vz)


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
