"""Collision detection and overlap resolution between spheres."""

from __future__ import annotations

import math

import deal

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

OVERLAP_EPSILON = 1e-9
# Last-resort push-apart direction if centers coincide AND both spheres move
# identically (relative velocity also zero). Fixed (not random) to keep the
# solver deterministic.
DEGENERATE_NORMAL = Vector3(1.0, 0.0, 0.0)
# A contact normal with (near) zero horizontal component is tilted by this
# much toward +x. Gravity never introduces a horizontal push on its own, so
# an exactly vertical stack (or coincident centers with a purely vertical
# relative velocity) can otherwise sit in an unstable equilibrium and
# oscillate forever instead of toppling/separating sideways.
VERTICAL_TILT_EPSILON = 1e-9
VERTICAL_TILT_AMOUNT = 1e-3


def distance(a: Sphere, b: Sphere) -> float:
    """Euclidean distance between two sphere centers.

    >>> s1 = Sphere(Vector3(0.0, 0.0, 0.0), Vector3(0.0, 0.0, 0.0), radius=1.0, level=0)
    >>> s2 = Sphere(Vector3(3.0, 4.0, 0.0), Vector3(0.0, 0.0, 0.0), radius=1.0, level=0)
    >>> distance(s1, s2)
    5.0
    """
    return (b.position - a.position).length()


def is_colliding(a: Sphere, b: Sphere) -> bool:
    """Whether two spheres overlap.

    Compares squared distances (no `Vector3`/sqrt) since this runs in the
    O(n^2) broad-phase scan over every sphere pair each step -- see
    scripts/stress_benchmark.py, where this was the dominant cost.
    """
    dx = a.position.x - b.position.x
    dy = a.position.y - b.position.y
    dz = a.position.z - b.position.z
    radius_sum = a.radius + b.radius
    return dx * dx + dy * dy + dz * dz < radius_sum * radius_sum


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


def _raw_normal(a: Sphere, b: Sphere) -> Vector3:
    """Exact unit vector from `a` towards `b`.

    Falls back to the relative velocity direction (then a fixed axis) only
    if the centers exactly coincide (distance zero).
    """
    delta = b.position - a.position
    dist = delta.length()
    if dist > 0:
        return delta * (1 / dist)
    relative_velocity = b.velocity - a.velocity
    speed = relative_velocity.length()
    return relative_velocity * (1 / speed) if speed > 0 else DEGENERATE_NORMAL


def contact_normal(a: Sphere, b: Sphere) -> Vector3:
    """`_raw_normal`, but tilted slightly toward +x if (near) exactly
    vertical -- for the velocity solver only, not overlap correction.

    Gravity never introduces a horizontal push on its own, so an exactly
    vertical stack can otherwise sit in an unstable equilibrium and jitter
    forever instead of toppling/separating sideways. `resolve_overlap` must
    NOT use this: pushing along a direction other than the true separation
    axis by the scalar overlap amount no longer lands exactly on
    `radius_sum` and can violate its postcondition.
    """
    normal = _raw_normal(a, b)
    if math.hypot(normal.x, normal.y) < VERTICAL_TILT_EPSILON:
        tilted = Vector3(VERTICAL_TILT_AMOUNT, 0.0, normal.z)
        normal = tilted * (1 / tilted.length())
    return normal


@deal.pre(lambda a, b: is_colliding(a, b))
@deal.ensure(lambda a, b, result: distance(a, b) >= a.radius + b.radius - OVERLAP_EPSILON)
def resolve_overlap(a: Sphere, b: Sphere) -> None:
    """Push two overlapping spheres apart along their connecting axis.

    Mutates `a.position` and `b.position` in place. The correction is
    mass-weighted so the lighter sphere moves proportionally more.
    """
    normal = _raw_normal(a, b)
    overlap = a.radius + b.radius - distance(a, b)
    total_mass = a.mass + b.mass
    a.position = a.position - normal * (overlap * (b.mass / total_mass))
    b.position = b.position + normal * (overlap * (a.mass / total_mass))
