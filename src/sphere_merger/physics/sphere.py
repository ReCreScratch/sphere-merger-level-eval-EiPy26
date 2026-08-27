"""Sphere physics body (2D: position/velocity live in the play plane, no height)."""

from __future__ import annotations

from dataclasses import dataclass

from sphere_merger.physics.vector import Vector2


@dataclass
class Sphere:
    """A single physics body in the simulation.

    Has no mass: the radius is uniform across all levels (see
    `game.level.radius_for_level`), so a per-sphere mass could only ever
    be a constant. Every solver therefore splits equally between both
    spheres -- overlap push, collision impulse and merge averaging alike.

    Mutable on purpose: the solvers overwrite `position`/`velocity` in
    place rather than building new spheres each step.

    >>> Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=1.0, level=0).radius
    1.0
    """

    position: Vector2
    velocity: Vector2
    radius: float
    level: int

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError(f"radius must be positive, got {self.radius}")
        if self.level < 0:
            raise ValueError(f"level must be non-negative, got {self.level}")
