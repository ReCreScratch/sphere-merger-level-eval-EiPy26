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

# Purely a broad-phase optimization (skip the O(n^2) scan for pairs that are
# both exactly stationary, see find_colliding_pairs) -- not a physical
# "resting band" like the old gravity model needed. Without gravity nothing
# re-drives a settled sphere's velocity away from exactly zero, so a tiny
# fixed epsilon (float noise only) is all that's needed here.
_MOVING_EPSILON = 1e-9

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
        friction: Fraction of speed removed per step (table drag) -- every
            sphere, every step, regardless of contact state (0 = frictionless
            ice, 1 = stops dead immediately). Replaces the old "only while
            resting on the floor" special case from the 3D/gravity model --
            there's no floor here, everything is always "on the table".
        sphere_restitution: Elasticity of sphere-sphere collisions (0 = fully
            inelastic, spheres stick to their post-collision velocity with no
            bounce-back; 1 = fully elastic, no kinetic energy lost).
        boundary_restitution: Elasticity of contact with the field walls.
            At 1.0 a wall is a perfect reflector and a sphere bounces forever
            at the same speed; values below 1 lose energy on every bounce
            until the sphere settles.
    """

    friction: float = 0.0075
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

    Fixed, deterministic order: integration -> friction -> boundary contact
    -> pairwise sphere collisions (velocity solver, then overlap solver) --
    always in `spheres` list order.

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

    Not yet ported to the 2D/no-gravity model -- `native/sphere_merger_native`
    still expects the old 3D signature. Raises until that port lands (see
    docs/physics_optimizations.md); the Python path above is fully correct
    and is what every caller gets by default (`current_backend() == "python"`).
    """
    raise NotImplementedError(
        "native backend not yet ported to the 2D physics model -- use the Python backend "
        "(the default) until native/sphere_merger_native is updated to match"
    )


@deal.pre(lambda a, b, restitution: is_colliding(a, b))
def _resolve_velocity(a: Sphere, b: Sphere, restitution: float) -> None:
    """Impulse-based collision response along the contact normal.

    Tangential velocity is left untouched (no spin/friction in collisions).
    No "resting contact" special case here (unlike the old 3D/gravity
    model): without gravity, nothing continuously re-drives two touching
    spheres back together, so a normal restitution-scaled bounce simply
    loses energy each time and settles on its own.
    """
    normal = contact_normal(a, b)

    approach_speed = (a.velocity - b.velocity).dot(normal)
    if approach_speed <= 0:
        return

    impulse = (1 + restitution) * approach_speed / (1 / a.mass + 1 / b.mass)
    a.velocity = a.velocity - normal * (impulse / a.mass)
    b.velocity = b.velocity + normal * (impulse / b.mass)
