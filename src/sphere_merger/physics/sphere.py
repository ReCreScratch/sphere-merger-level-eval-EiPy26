"""Sphere physics body (2D: position/velocity live in the play plane, no height)."""

from __future__ import annotations

from dataclasses import dataclass

from sphere_merger.physics.vector import Vector2


@dataclass
class Sphere:
    """A single physics body in the simulation.

    >>> Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=1.0, level=0).mass
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

    @property
    def mass(self) -> float:
        """Mass derived from volume (radius cubed)."""
        return self.radius**3
