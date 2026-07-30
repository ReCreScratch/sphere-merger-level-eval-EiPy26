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


def resolve_boundary(sphere: Sphere, boundary: Boundary, restitution: float) -> None:
    """Clamp `sphere` inside `boundary`, reflecting velocity on contact.

    Every wall (including the floor, `z_min`) is treated the same way: if the
    sphere's surface would cross a bound, its position is clamped to that
    bound and the perpendicular velocity component is reflected, scaled by
    `restitution`.

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
        x, vx = boundary.x_min + r, -vx * restitution
    elif x + r > boundary.x_max:
        x, vx = boundary.x_max - r, -vx * restitution

    if y - r < boundary.y_min:
        y, vy = boundary.y_min + r, -vy * restitution
    elif y + r > boundary.y_max:
        y, vy = boundary.y_max - r, -vy * restitution

    if z - r < boundary.z_min:
        z, vz = boundary.z_min + r, -vz * restitution
    elif boundary.z_max is not None and z + r > boundary.z_max:
        z, vz = boundary.z_max - r, -vz * restitution

    sphere.position = Vector3(x, y, z)
    sphere.velocity = Vector3(vx, vy, vz)
