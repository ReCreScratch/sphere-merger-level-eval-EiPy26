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

    Compares squared distances (no `Vector2`/sqrt) since this runs in the
    O(n^2) broad-phase scan over every sphere pair each step -- see
    scripts/stress_benchmark.py, where this was the dominant cost.
    """
    dx = a.position.x - b.position.x
    dy = a.position.y - b.position.y
    radius_sum = a.radius + b.radius
    return dx * dx + dy * dy < radius_sum * radius_sum


def find_colliding_pairs(
    spheres: list[Sphere], moving_threshold: float = 0.0
) -> list[tuple[int, int]]:
    """Return index pairs (i, j), i < j, of overlapping spheres in `spheres`.

    Pairs are found via a fixed nested loop over list indices, so the result
    depends only on the order of `spheres`, never on set/dict iteration order.

    A pair is skipped without checking `is_colliding` if *both* spheres are
    slower than `moving_threshold` (default 0.0 -- every pair is checked,
    unchanged behavior): two resting spheres can't spontaneously start
    overlapping on their own, so if neither has moved since it last had a
    chance to newly overlap something, re-checking it is wasted work. Once a
    resting sphere is actually disturbed (e.g. hit by a moving one), its own
    velocity rises above the threshold and it's included again from the very
    next call. This is the dominant simulation cost (an O(n^2) scan every
    physics step) per profiling with 5-6 spheres.
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

    Falls back to the relative velocity direction (then a fixed axis) only
    if the centers exactly coincide (distance zero). No 3D-stack tilt case
    here (that was specifically for breaking an exactly-vertical gravity
    equilibrium, which can't arise without gravity/height) -- one normal,
    used by both the velocity solver and the overlap solver.
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

    Mutates `a.position` and `b.position` in place. No mass concept (see
    `Sphere`'s docstring), so the correction is split evenly between both.
    """
    normal = contact_normal(a, b)
    overlap = a.radius + b.radius - distance(a, b)
    a.position = a.position - normal * (overlap * 0.5)
    b.position = b.position + normal * (overlap * 0.5)
