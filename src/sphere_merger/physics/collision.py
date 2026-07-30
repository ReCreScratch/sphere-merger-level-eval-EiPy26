"""Collision detection and overlap resolution between spheres."""

from __future__ import annotations

import deal

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

OVERLAP_EPSILON = 1e-9
# Last-resort push-apart direction if centers coincide AND both spheres move
# identically (relative velocity also zero). Fixed (not random) to keep the
# solver deterministic.
DEGENERATE_NORMAL = Vector3(1.0, 0.0, 0.0)


def distance(a: Sphere, b: Sphere) -> float:
    """Euclidean distance between two sphere centers.

    >>> s1 = Sphere(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0), radius=1.0, level=0)
    >>> s2 = Sphere(Vector3(3.0, 4.0, 0.0), Vector3(0.0, 0.0, 0.0), radius=1.0, level=0)
    >>> distance(s1, s2)
    5.0
    """
    return (b.position - a.position).length()


def is_colliding(a: Sphere, b: Sphere) -> bool:
    """Whether two spheres overlap."""
    return distance(a, b) < a.radius + b.radius


def find_colliding_pairs(spheres: list[Sphere]) -> list[tuple[int, int]]:
    """Return index pairs (i, j), i < j, of overlapping spheres in `spheres`.

    Pairs are found via a fixed nested loop over list indices, so the result
    depends only on the order of `spheres`, never on set/dict iteration order.
    """
    pairs = []
    for i in range(len(spheres)):
        for j in range(i + 1, len(spheres)):
            if is_colliding(spheres[i], spheres[j]):
                pairs.append((i, j))
    return pairs


def _degenerate_normal(a: Sphere, b: Sphere) -> Vector3:
    """Push-apart direction when both sphere centers coincide.

    Uses the relative velocity direction (the spheres separate the way they
    are already moving apart); falls back to a fixed axis if that is zero too.
    """
    relative_velocity = b.velocity - a.velocity
    speed = relative_velocity.length()
    if speed > 0:
        return relative_velocity * (1 / speed)
    return DEGENERATE_NORMAL


@deal.pre(lambda a, b: is_colliding(a, b))
@deal.ensure(lambda a, b, result: distance(a, b) >= a.radius + b.radius - OVERLAP_EPSILON)
def resolve_overlap(a: Sphere, b: Sphere) -> None:
    """Push two overlapping spheres apart along their connecting axis.

    Mutates `a.position` and `b.position` in place. The correction is
    mass-weighted so the lighter sphere moves proportionally more.
    """
    delta = b.position - a.position
    dist = delta.length()
    normal = delta * (1 / dist) if dist > 0 else _degenerate_normal(a, b)
    overlap = a.radius + b.radius - dist
    total_mass = a.mass + b.mass
    a.position = a.position - normal * (overlap * (b.mass / total_mass))
    b.position = b.position + normal * (overlap * (a.mass / total_mass))
