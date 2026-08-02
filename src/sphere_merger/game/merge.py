"""Merge logic: same-level spheres touching combine into one sphere at the
next level, instead of bouncing off each other.

Meant to run right after a `physics.engine.step()` call made with
`collision_filter=lambda a, b: a.level != b.level` (see `engine.step`'s
docstring) -- that leaves same-level overlapping pairs untouched by the
physics solver so `resolve_merges` can take them over here.
"""

from __future__ import annotations

from sphere_merger.game.level import radius_for_level
from sphere_merger.physics.collision import find_colliding_pairs
from sphere_merger.physics.sphere import Sphere


def merge_spheres(a: Sphere, b: Sphere) -> Sphere:
    """Combine two same-level spheres into one sphere at `level + 1`.

    Momentum-conserving (position and velocity are mass-weighted averages
    of `a` and `b`) -- the merged sphere keeps flying/falling with the
    combined "Restgeschwindigkeit" instead of snapping to a stop. Radius
    currently comes from `radius_for_level` (uniform for now, see its
    docstring) rather than the combined mass -- while that simplification
    is in place, merged spheres stay the same size as everything else
    instead of visibly growing with every merge.

    >>> from sphere_merger.physics.vector import Vector3
    >>> a = Sphere(Vector3(0.0, 0.0, 1.0), Vector3(1.0, 0.0, 0.0), radius=0.5, level=0)
    >>> b = Sphere(Vector3(1.0, 0.0, 1.0), Vector3(-1.0, 0.0, 0.0), radius=0.5, level=0)
    >>> merged = merge_spheres(a, b)
    >>> merged.level, merged.position
    (1, Vector3(x=0.5, y=0.0, z=1.0))
    >>> merged.velocity
    Vector3(x=0.0, y=0.0, z=0.0)
    """
    if a.level != b.level:
        raise ValueError(f"can only merge same-level spheres, got levels {a.level} and {b.level}")
    new_mass = a.mass + b.mass
    new_radius = radius_for_level(a.level + 1)
    new_position = (a.position * a.mass + b.position * b.mass) * (1 / new_mass)
    new_velocity = (a.velocity * a.mass + b.velocity * b.mass) * (1 / new_mass)
    return Sphere(new_position, new_velocity, radius=new_radius, level=a.level + 1)


def resolve_merges(spheres: list[Sphere]) -> list[int]:
    """Merge every same-level overlapping pair in `spheres`, in place.

    Pairs are found via the same fixed index order as
    `physics.collision.find_colliding_pairs` (lowest indices first), so
    results are deterministic regardless of how spheres came to overlap. A
    sphere already merged this call is skipped for any further pairing
    within the same call -- it may still merge again on a later call, once
    it has had a chance to newly collide with something.

    Returns the resulting level of each merge, in processing order (for
    e.g. combo scoring -- one entry per merge, first merge in the shot
    first).

    Deliberately does not use `find_colliding_pairs`'s `moving_threshold`
    (unlike `physics.engine.step`'s own bounce-resolution call): merges are
    the scoring-relevant outcome, not just physics smoothness, so this
    checks every pair every call rather than risking a resting same-level
    pair silently never being noticed as touching.
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
