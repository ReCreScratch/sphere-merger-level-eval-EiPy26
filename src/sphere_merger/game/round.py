"""One round: shoot the queued spheres one at a time, merging and scoring
as the field settles, until the target score is reached or the queue runs
out.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from sphere_merger.game.level import LevelDefinition, radius_for_level
from sphere_merger.game.merge import resolve_merges
from sphere_merger.game.scoring import MergeScoreFn, default_merge_score
from sphere_merger.game.shooting import shoot
from sphere_merger.physics.engine import step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

DT = 0.01
MAX_SETTLE_STEPS = 2000
# Matches test_stress.py's REST_TOLERANCE: stacked contacts settle into a
# small bounded jitter rather than exactly zero (see docs/ki_log.md), so
# "at rest" has to allow for that instead of requiring exact zero.
SETTLE_SPEED_THRESHOLD = 0.5


@dataclass
class RoundState:
    """Mutable state of a round in progress.

    Attributes:
        level: The round's (fixed) definition -- boundary, physics config,
            spawn position, target score.
        spheres: Every sphere currently on the field.
        remaining_queue: Levels still to be shot, in order (next shot first).
        score: Accumulated points from merges so far.
        shots_taken: Number of shots played so far.
    """

    level: LevelDefinition
    spheres: list[Sphere]
    remaining_queue: list[int]
    score: int = field(default=0)
    shots_taken: int = field(default=0)

    @property
    def is_won(self) -> bool:
        return self.score >= self.level.target_score

    @property
    def is_lost(self) -> bool:
        return not self.is_won and not self.remaining_queue

    @property
    def is_over(self) -> bool:
        return self.is_won or self.is_lost


def start_round(level: LevelDefinition) -> RoundState:
    """A fresh `RoundState` for `level`: its starting field, untouched queue."""
    return RoundState(
        level=level,
        spheres=copy.deepcopy(level.initial_spheres),
        remaining_queue=list(level.shot_queue),
    )


def _same_level(a: Sphere, b: Sphere) -> bool:
    return a.level == b.level


def play_shot(
    state: RoundState,
    angle_degrees: float,
    speed: float,
    score_fn: MergeScoreFn = default_merge_score,
    dt: float = DT,
    max_settle_steps: int = MAX_SETTLE_STEPS,
    settle_speed_threshold: float = SETTLE_SPEED_THRESHOLD,
) -> list[int]:
    """Shoot the next queued sphere and simulate until the field settles.

    Mutates `state` in place: pops the next level off `remaining_queue`,
    spawns it at `state.level.spawn_position` and shoots it (see
    `game.shooting.shoot`), then repeatedly advances physics -- with
    same-level pairs excluded from the bounce solver, see
    `physics.engine.step`'s `collision_filter` -- and resolves merges
    (`game.merge.resolve_merges`) until every sphere's speed drops below
    `settle_speed_threshold`, the round is won, or `max_settle_steps` is
    reached. Each merge adds `score_fn(new_level, combo_index)` to
    `state.score`, `combo_index` counting merges within this shot (1-based,
    first merge first).

    Returns the resulting level of each merge caused by this shot, in the
    order they happened.

    Raises:
        RuntimeError: if the round is already won or lost.
    """
    if state.is_over:
        raise RuntimeError("round is already over, cannot play another shot")

    next_level = state.remaining_queue.pop(0)
    sphere = Sphere(
        position=state.level.spawn_position,
        velocity=Vector3(0.0, 0.0, 0.0),
        radius=radius_for_level(next_level),
        level=next_level,
    )
    shoot(sphere, angle_degrees, speed)
    state.spheres.append(sphere)
    state.shots_taken += 1

    combo_index = 0
    merged_levels: list[int] = []
    for _ in range(max_settle_steps):
        step(
            state.spheres,
            dt,
            state.level.boundary,
            state.level.physics_config,
            collision_filter=lambda a, b: not _same_level(a, b),
        )
        for new_level in resolve_merges(state.spheres):
            combo_index += 1
            state.score += score_fn(new_level, combo_index)
            merged_levels.append(new_level)

        if state.is_won:
            break
        if all(s.velocity.length() < settle_speed_threshold for s in state.spheres):
            break

    return merged_levels
