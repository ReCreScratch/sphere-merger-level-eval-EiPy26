"""Level shrinking: reduce a `LevelDefinition` to a smaller/simpler variant
that still exhibits some caller-defined "interesting" property, for
human-legible example levels -- the same idea as Hypothesis's shrinking,
applied to levels instead of test inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from sphere_merger.game.level import LevelDefinition

IsInteresting = Callable[[LevelDefinition], bool]


def _without_sphere(level: LevelDefinition, index: int) -> LevelDefinition:
    spheres = list(level.initial_spheres)
    del spheres[index]
    return replace(level, initial_spheres=spheres)


def _without_last_shot(level: LevelDefinition) -> LevelDefinition:
    return replace(level, shot_queue=level.shot_queue[:-1])


def shrink_level(level: LevelDefinition, is_interesting: IsInteresting) -> LevelDefinition:
    """Repeatedly simplify `level` -- drop one initial sphere or shorten the
    shot queue by one -- as long as `is_interesting` still holds on the
    result.

    Greedy delta-debugging: on each pass, tries every single-step
    simplification and keeps the first one that preserves
    `is_interesting`, then starts over from there. Stops once no single
    simplification preserves it anymore (a local minimum, not necessarily
    the smallest possible level).

    `level` itself must already satisfy `is_interesting` -- not re-checked
    here, since callers already know this (e.g. it's the level they just
    found while searching).
    """
    current = level
    shrank = True
    while shrank:
        shrank = False

        for index in range(len(current.initial_spheres)):
            candidate = _without_sphere(current, index)
            if is_interesting(candidate):
                current = candidate
                shrank = True
                break
        if shrank:
            continue

        if len(current.shot_queue) > 1:
            candidate = _without_last_shot(current)
            if is_interesting(candidate):
                current = candidate
                shrank = True

    return current
