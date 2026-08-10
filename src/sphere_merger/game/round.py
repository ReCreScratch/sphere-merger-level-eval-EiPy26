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

DT = 1 / 60
# Finer than the previously checked 1/50 -- current parameter sweep uses
# higher shot speeds (up to ~25), which raises tunneling risk (a fast
# sphere's position can jump past another between two discrete steps
# without ever overlapping); a smaller dt keeps per-step travel distance
# down instead. Revisit if merges start looking implausible.
# Shared by every physics-driven part of the game (headless agent
# evaluation, rendered replay, interactive play) so results computed
# headless reproduce identically when replayed/watched -- see
# rendering.agent_grid and rendering.renderer.run_round, which both default
# their own `dt` to this constant instead of a rendering-only value.
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


def is_settled(
    spheres: list[Sphere], settle_speed_threshold: float = SETTLE_SPEED_THRESHOLD
) -> bool:
    """Whether every sphere's speed is below `settle_speed_threshold`.

    Matches test_stress.py's REST_TOLERANCE: stacked contacts settle into a
    small bounded jitter rather than exactly zero (see docs/ki_log.md), so
    this allows for that instead of requiring exact zero.
    """
    return all(sphere.velocity.length() < settle_speed_threshold for sphere in spheres)


def settle(spheres: list[Sphere]) -> None:
    """Force every sphere's velocity to exactly zero, in place.

    `is_settled` only checks for a small residual jitter (see its
    docstring), so spheres that stopped being advanced once they crossed
    that threshold can still be carrying a tiny non-zero velocity. Left
    alone, that residual gets picked back up (and visibly resumes moving)
    once the next shot restarts physics stepping. Call this once a shot is
    considered over so the next one starts from a genuinely resting field.
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

    Same-level pairs are excluded from the physics bounce solver (see
    `physics.engine.step`'s `collision_filter`) so `game.merge.resolve_merges`
    can turn them into a merge instead. Each merge adds
    `score_fn(new_level, combo_index)` to `state.score`, `combo_index`
    counting merges since the current shot was spawned (1-based, so pass 0
    for the first call after `spawn_shot` and reuse the returned value for
    subsequent calls within the same shot).

    Returns the updated `combo_index` and the resulting level of each merge
    caused by this step, in the order they happened.
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

    Headless composition of `spawn_shot` + repeated `advance_physics`, for
    agents/tests that don't need to see it animate frame by frame (for
    that, see `rendering.renderer.run_round`, which drives the same two
    functions itself). Runs until every sphere's speed drops below
    `settle_speed_threshold` (at which point `settle` zeroes out the small
    residual jitter, so the next shot starts from a genuinely resting
    field), the round is won, or `max_settle_steps` is reached.

    Returns the resulting level of each merge caused by this shot, in the
    order they happened.

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
    """Which of `level.initial_spheres`, by index, get merged away or start
    moving at some point during a full playthrough of `shots`.

    Tracks by object identity against a snapshot of `state.spheres` taken
    right after `start_round` -- not `level.initial_spheres` itself:
    `start_round` deep-copies, so even a genuinely untouched sphere is
    never the same object as the one in `level.initial_spheres`, and
    comparing against that would report everything as "merged" regardless
    of what actually happened (a real bug hit once, see
    docs/level_shrinking.md).

    The complement of the returned set are exactly the spheres a caller
    can drop without having affected this specific playthrough at all --
    the basis for `agents.runner.shrink_to_used_spheres`.
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
    """Steps a `RoundState` through a fixed, precomputed list of
    (angle, speed) shots -- e.g. one recorded via `agents.runner.record_shots`
    -- one call at a time, instead of asking an agent live.

    Shared by every "replay a recorded playthrough" view (grid, single-level
    browser) so the check-and-settle atomicity in `step_physics` (see its
    docstring) only has to be right in one place -- a previous, per-view
    copy of this same logic had that atomicity broken in exactly one of its
    two copies (see docs/physics_optimizations.md), which a second
    hand-duplicated copy would have been just as easy to get wrong again.
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

        Remembers the spawned sphere as `current_shot` -- a caller that
        wants to highlight "the sphere just shot" checks it by identity
        (`is`) against `state.spheres`, since a merge replaces rather than
        mutates a sphere (see `game.merge.resolve_merges`): once this one
        merges into something else, the identity check stops matching and
        the highlight naturally disappears instead of following the merge
        result around.
        """
        if not self.state.is_over and self.shot_index < len(self.shots):
            angle, speed = self.shots[self.shot_index]
            spawn_shot(self.state, angle, speed)
            self.current_shot = self.state.spheres[-1]
            self.shot_index += 1
            self.combo_index = 0

    def step_physics(self, dt: float = DT) -> None:
        """Advance the current shot by one frame; if that frame brings it
        below the settle threshold, zero the residual velocity immediately
        (see `settle`'s docstring) instead of on some later call.

        Checking and settling in the same call matters: a caller's main
        loop typically stops stepping once `settled` is reported, so a
        `settle()` that only fires on a *later* call would never actually
        run -- the just-barely-sub-threshold velocity from the frame
        settling was first detected would carry over, unzeroed, into the
        next shot instead of starting it from genuine rest.
        """
        if self.settled:
            return
        self.combo_index, _ = advance_physics(self.state, self.combo_index, dt=dt)
        if self.settled:
            settle(self.state.spheres)
