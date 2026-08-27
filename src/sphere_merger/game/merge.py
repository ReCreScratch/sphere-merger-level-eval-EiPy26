"""Merge logic: touching same-level spheres combine into one sphere at the
next level instead of bouncing off each other.

Runs right after a `physics.engine.step()` called with
`collision_filter=lambda a, b: a.level != b.level`, which leaves
same-level overlapping pairs alone for `resolve_merges` to take over.
"""

from __future__ import annotations

from sphere_merger.game.level import radius_for_level
from sphere_merger.physics.collision import find_colliding_pairs
from sphere_merger.physics.sphere import Sphere


def merge_spheres(a: Sphere, b: Sphere) -> Sphere:
    """Combine two same-level spheres into one sphere at `level + 1`.

    Position and velocity are the plain average of `a` and `b`, which
    conserves momentum given that every sphere counts equally (no mass,
    see `Sphere`). The merged sphere keeps flying with that combined
    velocity rather than snapping to a stop, and takes its radius from
    `radius_for_level`, so it does not visibly grow.

    >>> from sphere_merger.physics.vector import Vector2
    >>> a = Sphere(Vector2(0.0, 0.0), Vector2(1.0, 0.0), radius=0.5, level=0)
    >>> b = Sphere(Vector2(1.0, 0.0), Vector2(-1.0, 0.0), radius=0.5, level=0)
    >>> merged = merge_spheres(a, b)
    >>> merged.level, merged.position
    (1, Vector2(x=0.5, y=0.0))
    >>> merged.velocity
    Vector2(x=0.0, y=0.0)
    """
    if a.level != b.level:
        raise ValueError(f"can only merge same-level spheres, got levels {a.level} and {b.level}")
    new_radius = radius_for_level(a.level + 1)
    new_position = (a.position + b.position) * 0.5
    new_velocity = (a.velocity + b.velocity) * 0.5
    return Sphere(new_position, new_velocity, radius=new_radius, level=a.level + 1)


def resolve_merges(spheres: list[Sphere]) -> list[int]:
    """Merge every same-level overlapping pair in `spheres`, in place.

    Returns the resulting level of each merge in processing order, one
    entry per merge, which is what combo scoring consumes. Pairs come from
    `find_colliding_pairs` in fixed index order, so the outcome is
    deterministic; a sphere that already merged this call is skipped until
    the next one.

    Unlike `physics.engine.step`, this passes no `moving_threshold`: a
    missed merge costs points, not just physics smoothness, so every pair
    is checked every call rather than trusting that a resting same-level
    pair cannot be touching.
    """
    already_merged: set[int] = set()
    to_remove: set[int] = set()
    new_levels: list[int] = []

    for i, j in find_colliding_pairs(spheres):
        if i in already_merged or j in already_merged:
            continue
        a, b = spheres[i], spheres[j]
        if a.level != b.level:
            continue
        merged = merge_spheres(a, b)
        spheres[i] = merged
        to_remove.add(j)
        already_merged.add(i)
        already_merged.add(j)
        new_levels.append(merged.level)

    if to_remove:
        spheres[:] = [sphere for idx, sphere in enumerate(spheres) if idx not in to_remove]

    return new_levels
