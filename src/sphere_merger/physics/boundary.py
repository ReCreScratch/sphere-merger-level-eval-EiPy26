"""Axis-aligned rectangular play-field boundary (2D: four walls, no floor/ceiling)."""

from __future__ import annotations

from dataclasses import dataclass

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2


@dataclass
class Boundary:
    """Axis-aligned box that a sphere's surface may never cross."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def __post_init__(self) -> None:
        if self.x_min >= self.x_max:
            raise ValueError("x_min must be less than x_max")
        if self.y_min >= self.y_max:
            raise ValueError("y_min must be less than y_max")


def resolve_boundary(sphere: Sphere, boundary: Boundary, restitution: float) -> None:
    """Clamp `sphere` inside `boundary`, reflecting velocity on contact.

    Every wall is treated the same way: if the sphere's surface would cross
    a bound, its position is clamped to that bound, and the perpendicular
    velocity component is reflected -- scaled by `restitution` -- but only
    if it actually points at that wall.

    That direction guard mirrors `_resolve_velocity`'s `approach_speed`
    check and is needed for the same reason: `resolve_overlap` runs after
    this pass and pushes spheres apart unconditionally, so a sphere wedged
    against a wall can enter the next step penetrating it while already
    moving away. Reflecting that would flip it back into the wall.

    No special "resting" case is needed: with `restitution < 1` a bounce
    loses energy and decays to a standstill on its own.

    >>> s = Sphere(Vector2(4.6, 0.0), Vector2(1.0, 0.0), radius=0.5, level=0)
    >>> b = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0)
    >>> resolve_boundary(s, b, restitution=1.0)
    >>> s.position.x
    4.5
    >>> s.velocity.x
    -1.0
    """
    x, y = sphere.position.x, sphere.position.y
    vx, vy = sphere.velocity.x, sphere.velocity.y
    r = sphere.radius

    if x - r < boundary.x_min:
        x = boundary.x_min + r
        if vx < 0:
            vx = -vx * restitution
    elif x + r > boundary.x_max:
        x = boundary.x_max - r
        if vx > 0:
            vx = -vx * restitution

    if y - r < boundary.y_min:
        y = boundary.y_min + r
        if vy < 0:
            vy = -vy * restitution
    elif y + r > boundary.y_max:
        y = boundary.y_max - r
        if vy > 0:
            vy = -vy * restitution

    sphere.position = Vector2(x, y)
    sphere.velocity = Vector2(vx, vy)
