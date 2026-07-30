"""Immutable 3D vector used throughout the physics engine."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vector3:
    """A 3D vector.

    >>> Vector3(1.0, 2.0, 3.0) + Vector3(1.0, 1.0, 1.0)
    Vector3(x=2.0, y=3.0, z=4.0)
    """

    x: float
    y: float
    z: float

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector3:
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other: Vector3) -> float:
        """
        >>> Vector3(1.0, 0.0, 0.0).dot(Vector3(1.0, 0.0, 0.0))
        1.0
        """
        return self.x * other.x + self.y * other.y + self.z * other.z

    def length(self) -> float:
        """
        >>> Vector3(3.0, 4.0, 0.0).length()
        5.0
        """
        return math.sqrt(self.dot(self))
