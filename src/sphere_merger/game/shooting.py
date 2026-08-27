"""Slingshot shot mechanic: turns an angle + speed into a velocity.

Deliberately knows nothing about input devices, so an agent sweeping
candidate angles headless uses exactly the same code as the mouse.
"""

from __future__ import annotations

import math

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2


def shoot(sphere: Sphere, angle_degrees: float, speed: float) -> None:
    """Set `sphere`'s velocity to `speed` at `angle_degrees`.

    `angle_degrees` follows standard math convention: 0 = +x axis,
    counter-clockwise positive.

    >>> from sphere_merger.physics.vector import Vector2
    >>> s = Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=1.0, level=0)
    >>> shoot(s, angle_degrees=0.0, speed=5.0)
    >>> round(s.velocity.x, 5), round(s.velocity.y, 5)
    (5.0, 0.0)
    """
    angle_radians = math.radians(angle_degrees)
    sphere.velocity = Vector2(speed * math.cos(angle_radians), speed * math.sin(angle_radians))
