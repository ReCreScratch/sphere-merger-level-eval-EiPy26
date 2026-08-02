"""Axis-aligned rectangular play-field boundary."""

from __future__ import annotations

from dataclasses import dataclass

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3


@dataclass
class Boundary:
    """Axis-aligned box that a sphere's surface may never cross.

    `z_max` is optional; a field open at the top (default) has no ceiling.
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float | None = None

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            raise ValueError("x_min must be less than x_max")
        if self.y_min >= self.y_max:
            raise ValueError("y_min must be less than y_max")
        if self.z_max is not None and self.z_min >= self.z_max:
            raise ValueError("z_min must be less than z_max")


def resolve_boundary(
    sphere: Sphere,
    boundary: Boundary,
    restitution: float,
    rest_velocity_threshold: float = 0.0,
) -> None:
    """Clamp `sphere` inside `boundary`, reflecting velocity on contact.

    Every wall (including the floor, `z_min`) is treated the same way: if the
    sphere's surface would cross a bound, its position is clamped to that
    bound. The perpendicular velocity component is then either zeroed (if its
    magnitude is at or below `rest_velocity_threshold` -- the sphere is
    treated as resting rather than bouncing) or reflected, scaled by
    `restitution`.

    Without a resting threshold, a sphere settling under gravity never fully
    stops: each step's gravity nudge triggers a fresh, ever-smaller bounce,
    converging to a stable non-zero "jitter" velocity instead of zero (a
    discretization artifact, not a property of the real physical system).
    `<=` rather than `<` matters here: with the default `rest_threshold_factor
    = 1.0`, `rest_velocity_threshold` is exactly `gravity * dt` -- precisely
    the speed one step of freefall gives a sphere starting at rest (e.g. one
    just zeroed by `game.round.settle` for the previous shot). `<` alone
    would classify that exact-equality case as a bounce, not rest, producing
    a stable two-step jitter cycle (bounce -> rest -> bounce -> ...) the very
    next time physics resumes on an already-settled sphere.

    >>> s = Sphere(Vector3(0.0, 0.0, 0.4), Vector3(0.0, 0.0, -1.0), radius=0.5, level=0)
    >>> b = Boundary(x_min=-5, x_max=5, y_min=-5, y_max=5, z_min=0.0)
    >>> resolve_boundary(s, b, restitution=1.0)
    >>> s.position.z
    0.5
    >>> s.velocity.z
    1.0
    """
    x, y, z = sphere.position.x, sphere.position.y, sphere.position.z
    vx, vy, vz = sphere.velocity.x, sphere.velocity.y, sphere.velocity.z
    r = sphere.radius

    if x - r < boundary.x_min:
        x = boundary.x_min + r
        vx = 0.0 if abs(vx) <= rest_velocity_threshold else -vx * restitution
    elif x + r > boundary.x_max:
        x = boundary.x_max - r
        vx = 0.0 if abs(vx) <= rest_velocity_threshold else -vx * restitution

    if y - r < boundary.y_min:
        y = boundary.y_min + r
        vy = 0.0 if abs(vy) <= rest_velocity_threshold else -vy * restitution
    elif y + r > boundary.y_max:
        y = boundary.y_max - r
        vy = 0.0 if abs(vy) <= rest_velocity_threshold else -vy * restitution

    if z - r < boundary.z_min:
        z = boundary.z_min + r
        vz = 0.0 if abs(vz) <= rest_velocity_threshold else -vz * restitution
    elif boundary.z_max is not None and z + r > boundary.z_max:
        z = boundary.z_max - r
        vz = 0.0 if abs(vz) <= rest_velocity_threshold else -vz * restitution

    sphere.position = Vector3(x, y, z)
    sphere.velocity = Vector3(vx, vy, vz)
