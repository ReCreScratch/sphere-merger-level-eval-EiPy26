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
from sphere_merger.physics.vector import Vector2

# Small enough to limit tunneling at the shot speeds in use (up to ~25):
# a fast sphere must not jump past another between two discrete steps.
# Every physics-driven part of the game shares this value -- headless
# evaluation, replay and interactive play alike -- so a result computed
# headless reproduces exactly when watched.
DT = 1 / 60
MAX_SETTLE_STEPS = 2000
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


def is_settled(
    spheres: list[Sphere], settle_speed_threshold: float = SETTLE_SPEED_THRESHOLD
) -> bool:
    """Whether every sphere's speed is below `settle_speed_threshold`.

    A threshold rather than exact zero, matching test_stress.py's
    REST_TOLERANCE: contacts settle into a small bounded jitter.
    """
    return all(sphere.velocity.length() < settle_speed_threshold for sphere in spheres)


def settle(spheres: list[Sphere]) -> None:
    """Force every sphere's velocity to exactly zero, in place.

    Spheres accepted by `is_settled` still carry a small residual, which
    would visibly resume moving once the next shot restarts stepping. Call
    this at the end of a shot so the next starts from a resting field.
    """
    for sphere in spheres:
        sphere.velocity = Vector2(0.0, 0.0)


def spawn_shot(state: RoundState, angle_degrees: float, speed: float) -> None:
    """Pop the next queued level, spawn it at the spawn position and shoot it.

    Mutates `state` in place: appends the new sphere to `state.spheres` and
    increments `state.shots_taken`. Does not advance physics -- call
    `advance_physics` (once per frame for live rendering, or in a loop via
    `play_shot` headless) to actually move/merge it.

    Raises:
        RuntimeError: if the round is already won or lost.
    """
    if state.is_over:
        raise RuntimeError("round is already over, cannot play another shot")

    next_level = state.remaining_queue.pop(0)
    sphere = Sphere(
        position=state.level.spawn_position,
        velocity=Vector2(0.0, 0.0),
        radius=radius_for_level(next_level),
        level=next_level,
    )
    shoot(sphere, angle_degrees, speed)
    state.spheres.append(sphere)
    state.shots_taken += 1


def advance_physics(
    state: RoundState,
    combo_index: int,
    score_fn: MergeScoreFn = default_merge_score,
    dt: float = DT,
) -> tuple[int, list[int]]:
    """Advance `state.spheres` by one physics step and resolve any merges.

    Same-level pairs are withheld from the bounce solver (`step`'s
    `collision_filter`) so `resolve_merges` can turn them into a merge
    instead. Each merge adds `score_fn(new_level, combo_index)` to the
    score, where `combo_index` counts merges since the shot was spawned:
    pass 0 on the first call after `spawn_shot`, then feed the returned
    value back in for the rest of the shot.

    Returns the updated `combo_index` and the level of each merge this
    step caused, in order.
    """
    step(
        state.spheres,
        dt,
        state.level.boundary,
        state.level.physics_config,
        collision_filter=lambda a, b: not _same_level(a, b),
    )
    merged_levels: list[int] = []
    for new_level in resolve_merges(state.spheres):
        combo_index += 1
        state.score += score_fn(new_level, combo_index)
        merged_levels.append(new_level)
    return combo_index, merged_levels


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

    Headless composition of `spawn_shot` and repeated `advance_physics`,
    for agents and tests that need no animation;
    `rendering.renderer.run_round` drives the same two functions itself.
    Stops when the field settles (then `settle` zeroes the residual), the
    round is won, or `max_settle_steps` is reached.

    Returns the level of each merge this shot caused, in order.

    Raises:
        RuntimeError: if the round is already won or lost.
    """
    spawn_shot(state, angle_degrees, speed)

    combo_index = 0
    merged_levels: list[int] = []
    for _ in range(max_settle_steps):
        combo_index, new_levels = advance_physics(state, combo_index, score_fn, dt)
        merged_levels.extend(new_levels)

        if state.is_won:
            break
        if is_settled(state.spheres, settle_speed_threshold):
            settle(state.spheres)
            break

    return merged_levels


def touched_sphere_indices(level: LevelDefinition, shots: list[tuple[float, float]]) -> set[int]:
    """Indices of the initial spheres that merge away or start moving
    during a full playthrough of `shots`.

    Identity is tracked against a snapshot taken after `start_round`, not
    against `level.initial_spheres`. `start_round` deep-copies, so no
    sphere is ever the same object as its counterpart in the definition,
    and comparing there would report everything as merged (a real bug once
    hit, see docs/level_shrinking.md).

    The complement is exactly the set a caller may drop without affecting
    this playthrough -- the basis for `agents.runner.shrink_to_used_spheres`.
    """
    state = start_round(level)
    initial_spheres = list(state.spheres)
    initial_positions = [(s.position.x, s.position.y) for s in initial_spheres]
    for angle_degrees, speed in shots:
        play_shot(state, angle_degrees, speed)

    touched: set[int] = set()
    for i, sphere in enumerate(initial_spheres):
        still_present = any(s is sphere for s in state.spheres)
        if not still_present:
            touched.add(i)
            continue
        moved = (sphere.position.x, sphere.position.y) != initial_positions[i] or (
            sphere.velocity.x,
            sphere.velocity.y,
        ) != (0.0, 0.0)
        if moved:
            touched.add(i)
    return touched


@dataclass
class ShotReplay:
    """Steps a `RoundState` through a precomputed list of (angle, speed)
    shots one call at a time, instead of asking an agent live.

    Shared by every view that replays a recorded playthrough, so the
    check-and-settle atomicity in `step_physics` only has to be right
    once. An earlier per-view copy of this logic had exactly that broken
    in one of its two copies (see docs/physics_optimizations.md).
    """

    level: LevelDefinition
    shots: list[tuple[float, float]]
    state: RoundState = field(init=False)
    shot_index: int = field(init=False, default=0)
    combo_index: int = field(init=False, default=0)
    current_shot: Sphere | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.state = start_round(self.level)

    def reset(self) -> None:
        self.state = start_round(self.level)
        self.shot_index = 0
        self.combo_index = 0
        self.current_shot = None

    @property
    def settled(self) -> bool:
        return is_settled(self.state.spheres)

    def spawn_next_shot(self) -> None:
        """Spawn the next recorded shot, if the round isn't over and any are left.

        Remembers it as `current_shot` so a view can highlight the sphere
        just shot by identity (`is`) against `state.spheres`. Because a
        merge replaces rather than mutates, that check stops matching the
        moment this sphere merges, and the highlight disappears by itself
        instead of following the merge result around.
        """
        if not self.state.is_over and self.shot_index < len(self.shots):
            angle, speed = self.shots[self.shot_index]
            spawn_shot(self.state, angle, speed)
            self.current_shot = self.state.spheres[-1]
            self.shot_index += 1
            self.combo_index = 0

    def step_physics(self, dt: float = DT) -> None:
        """Advance the current shot by one frame, zeroing the residual
        velocity in the same call if this frame settles it.

        The atomicity matters: a caller's loop stops stepping as soon as
        `settled` reports true, so a `settle()` deferred to a later call
        would never run at all, and the sub-threshold velocity would carry
        into the next shot.
        """
        if self.settled:
            return
        self.combo_index, _ = advance_physics(self.state, self.combo_index, dt=dt)
        if self.settled:
            settle(self.state.spheres)
