"""Immutable 2D vector used throughout the physics engine."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vector2:
    """A 2D vector.

    >>> Vector2(1.0, 2.0) + Vector2(1.0, 1.0)
    Vector2(x=2.0, y=3.0)
    """

    x: float
    y: float

    def __add__(self, other: Vector2) -> Vector2:
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector2) -> Vector2:
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vector2:
        return Vector2(self.x * scalar, self.y * scalar)

    def dot(self, other: Vector2) -> float:
        """
        >>> Vector2(1.0, 0.0).dot(Vector2(1.0, 0.0))
        1.0
        """
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        """
        >>> Vector2(3.0, 4.0).length()
        5.0
        """
        return math.sqrt(self.dot(self))
