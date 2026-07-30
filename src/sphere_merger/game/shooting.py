"""Slingshot shot mechanic: turns an angle + speed into a velocity.

Kept separate from any input device (mouse, agent angle-sweep, ...) so the
same shot logic works headless -- an agent can call `shoot` directly with a
candidate angle/speed without any UI involved.
"""

from __future__ import annotations

import math

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3


def shoot(sphere: Sphere, angle_degrees: float, speed: float) -> None:
    """Set `sphere`'s horizontal velocity to `speed` at `angle_degrees`.

    `angle_degrees` follows standard math convention: 0 = +x axis,
    counter-clockwise positive. Vertical velocity is left untouched.

    >>> from sphere_merger.physics.vector import Vector3
    >>> s = Sphere(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0), radius=1.0, level=0)
    >>> shoot(s, angle_degrees=0.0, speed=5.0)
    >>> round(s.velocity.x, 5), round(s.velocity.y, 5)
    (5.0, 0.0)
    """
    angle_radians = math.radians(angle_degrees)
    sphere.velocity = Vector3(
        speed * math.cos(angle_radians),
        speed * math.sin(angle_radians),
        sphere.velocity.z,
    )
