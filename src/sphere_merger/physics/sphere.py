"""Sphere physics body (2D: position/velocity live in the play plane, no height)."""

from __future__ import annotations

from dataclasses import dataclass

from sphere_merger.physics.vector import Vector2


@dataclass
class Sphere:
    """A single physics body in the simulation.

    No mass: every sphere counts equally in collisions/merges (uniform
    radius everywhere anyway, see `game.level.radius_for_level`'s
    docstring) -- so a per-sphere mass would only ever be a constant, not
    real information. Solvers that used to be mass-weighted (overlap push,
    collision impulse, merge averaging) are equal-split instead.

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
