"""Collision detection and overlap resolution between spheres (2D)."""

from __future__ import annotations

import deal

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

OVERLAP_EPSILON = 1e-9
# Last-resort push-apart direction if centers coincide AND both spheres move
# identically (relative velocity also zero). Fixed (not random) to keep the
# solver deterministic.
DEGENERATE_NORMAL = Vector2(1.0, 0.0)


def distance(a: Sphere, b: Sphere) -> float:
    """Euclidean distance between two sphere centers.

    >>> s1 = Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=1.0, level=0)
    >>> s2 = Sphere(Vector2(3.0, 4.0), Vector2(0.0, 0.0), radius=1.0, level=0)
    >>> distance(s1, s2)
    5.0
    """
    return (b.position - a.position).length()


def is_colliding(a: Sphere, b: Sphere) -> bool:
    """Whether two spheres overlap.

    Compares squared distances, avoiding a `Vector2` allocation and a
    `sqrt`: profiling found this the dominant cost of the whole
    simulation, since it runs for every sphere pair on every step.
    """
    dx = a.position.x - b.position.x
    dy = a.position.y - b.position.y
    radius_sum = a.radius + b.radius
    return dx * dx + dy * dy < radius_sum * radius_sum


def find_colliding_pairs(
    spheres: list[Sphere], moving_threshold: float = 0.0
) -> list[tuple[int, int]]:
    """Return index pairs (i, j), i < j, of overlapping spheres in `spheres`.

    A fixed nested loop over list indices, so the result depends only on
    the order of `spheres` and never on set/dict iteration order. This
    O(n^2) scan runs every physics step and is the dominant simulation
    cost.

    With `moving_threshold` above 0, a pair is skipped outright if *both*
    spheres are slower than it, on the assumption that neither can have
    newly come to overlap anything. Caveat: `resolve_overlap` displaces
    spheres without giving them velocity, so that assumption does not
    strictly hold -- a sphere pushed into a resting neighbour yields a
    pair that is never re-examined. The default of 0.0 checks every pair.
    """
    threshold_squared = moving_threshold * moving_threshold
    moving = [sphere.velocity.dot(sphere.velocity) >= threshold_squared for sphere in spheres]
    pairs = []
    for i in range(len(spheres)):
        for j in range(i + 1, len(spheres)):
            if not moving[i] and not moving[j]:
                continue
            if is_colliding(spheres[i], spheres[j]):
                pairs.append((i, j))
    return pairs


def contact_normal(a: Sphere, b: Sphere) -> Vector2:
    """Exact unit vector from `a` towards `b`.

    Used by both the velocity solver and the overlap solver. If the
    centers exactly coincide there is no direction to derive, so it falls
    back to the relative velocity, and to a fixed axis if that is zero too
    -- fixed rather than random, to keep the solver deterministic.
    """
    delta = b.position - a.position
    dist = delta.length()
    if dist > 0:
        return delta * (1 / dist)
    relative_velocity = b.velocity - a.velocity
    speed = relative_velocity.length()
    return relative_velocity * (1 / speed) if speed > 0 else DEGENERATE_NORMAL


@deal.pre(lambda a, b: is_colliding(a, b))
@deal.ensure(lambda a, b, result: distance(a, b) >= a.radius + b.radius - OVERLAP_EPSILON)
def resolve_overlap(a: Sphere, b: Sphere) -> None:
    """Push two overlapping spheres apart along their connecting axis.

    Mutates both positions in place, splitting the correction evenly (no
    mass, see `Sphere`). Leaves velocities untouched -- separating the
    spheres is `_resolve_velocity`'s job.
    """
    normal = contact_normal(a, b)
    overlap = a.radius + b.radius - distance(a, b)
    a.position = a.position - normal * (overlap * 0.5)
    b.position = b.position + normal * (overlap * 0.5)
