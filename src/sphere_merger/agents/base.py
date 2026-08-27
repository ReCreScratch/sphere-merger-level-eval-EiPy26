"""Shared agent interface and candidate-shot simulation.

Every agent picks the next shot's angle/speed by simulating candidates on
a private clone of the round state (`simulate_shot`) -- the real `state`
passed to `choose_shot` is never mutated while evaluating options.
"""

from __future__ import annotations

import copy
from typing import Protocol

from sphere_merger.game.level import radius_for_level
from sphere_merger.game.round import (
    DT,
    MAX_SETTLE_STEPS,
    SETTLE_SPEED_THRESHOLD,
    RoundState,
    play_shot,
)
from sphere_merger.physics.engine import current_backend
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

DEFAULT_SPEED = 10.0
ANGLE_RANGE_DEGREES = (0.0, 90.0)
ANGLE_STEP_DEGREES = 1.0

EXECUTOR_CHUNKSIZE = 4
"""How many candidate angles an agent hands a worker per task.

`Executor.map`'s default of one task per item was measurably worse than
useless for `GreedyAgent`: its per-candidate work is a single
`simulate_shot`, so the pickling round-trip cost more than the simulation
and the parallel sweep ran *slower* than the sequential one (0.089s vs
0.062s; batching to 4 gives 0.018s). `LookaheadAgent` suffers far less --
each of its tasks already holds a full next-shot sweep -- but still gains.

Four is a compromise against the 91 default candidates: large enough to
amortise the round-trip, small enough that the resulting ~23 chunks still
spread over a 16-worker pool without idling workers at the tail.
"""


class Agent(Protocol):
    """Picks the next queued shot's angle/speed from the current `state`."""

    def choose_shot(self, state: RoundState) -> tuple[float, float]: ...


def candidate_angles(
    angle_range: tuple[float, float] = ANGLE_RANGE_DEGREES,
    angle_step: float = ANGLE_STEP_DEGREES,
) -> list[float]:
    """Evenly spaced angles from `angle_range[0]` to `angle_range[1]`, inclusive.

    >>> candidate_angles((0.0, 20.0), 5.0)
    [0.0, 5.0, 10.0, 15.0, 20.0]
    """
    low, high = angle_range
    count = int(round((high - low) / angle_step))
    return [low + i * angle_step for i in range(count + 1)]


def _clone_state(state: RoundState) -> RoundState:
    """Cheap `RoundState` clone for trial simulation, instead of `deepcopy`.

    Shares `state.level` by reference: nothing on the `simulate_shot` path
    mutates it, so its whole subtree needs no isolating, whereas
    `deepcopy` walked and copied all of it on every call. `Vector2` is
    frozen, so a shallow copy per `Sphere` isolates `spheres`;
    `remaining_queue` needs its own list because `spawn_shot` pops from
    it.

    This is the hottest path in the codebase -- `LookaheadAgent` alone
    calls it candidates + candidates^2 times per decision -- so the
    per-call constant factor matters more here than anywhere else.
    """
    return RoundState(
        level=state.level,
        spheres=[copy.copy(sphere) for sphere in state.spheres],
        remaining_queue=list(state.remaining_queue),
        score=state.score,
        shots_taken=state.shots_taken,
    )


def _simulate_shot_native(
    state: RoundState, angle_degrees: float, speed: float
) -> tuple[RoundState, int]:
    """`simulate_shot`'s native-backend branch.

    The entire settle loop -- spawn, repeated step, merge, score -- runs as
    one call into the extension rather than many Python-level `step`
    calls. That, not `step_native` alone, is where the native backend's
    real speedup comes from (see docs/physics_optimizations.md).

    Custom `score_fn`, `max_settle_steps` or `settle_speed_threshold` are
    unsupported here: arbitrary Python callables cannot cross the FFI
    boundary, so the native loop hardcodes `game.round`'s defaults.
    Nothing in this codebase passes anything else on this path.
    """
    import sphere_merger_native

    next_level = state.remaining_queue[0]
    next_radius = radius_for_level(next_level)
    boundary = state.level.boundary
    config = state.level.physics_config
    spawn = state.level.spawn_position

    final_spheres, gain, _won = sphere_merger_native.simulate_shot_native(
        [
            (s.position.x, s.position.y, s.velocity.x, s.velocity.y, s.radius, s.level)
            for s in state.spheres
        ],
        next_level,
        next_radius,
        (spawn.x, spawn.y),
        angle_degrees,
        speed,
        DT,
        (boundary.x_min, boundary.x_max, boundary.y_min, boundary.y_max),
        (config.friction, config.sphere_restitution, config.boundary_restitution),
        MAX_SETTLE_STEPS,
        SETTLE_SPEED_THRESHOLD,
        state.score,
        state.level.target_score,
    )

    trial = RoundState(
        level=state.level,
        spheres=[
            Sphere(position=Vector2(x, y), velocity=Vector2(vx, vy), radius=radius, level=level)
            for x, y, vx, vy, radius, level in final_spheres
        ],
        remaining_queue=state.remaining_queue[1:],
        score=state.score + gain,
        shots_taken=state.shots_taken + 1,
    )
    return trial, gain


def simulate_shot(state: RoundState, angle_degrees: float, speed: float) -> tuple[RoundState, int]:
    """Play one shot on a clone of `state`, leaving `state` itself untouched.

    Returns the resulting clone and the score gained by this single shot
    (not the round's cumulative score).
    """
    if current_backend() == "rust":
        return _simulate_shot_native(state, angle_degrees, speed)
    trial = _clone_state(state)
    score_before = trial.score
    play_shot(trial, angle_degrees, speed)
    return trial, trial.score - score_before


def candidate_total_gain(args: tuple[RoundState, float, float, list[float]]) -> tuple[float, int]:
    """One candidate's own gain plus the best next-shot gain from there.

    Falls back to just its own gain if the round ends on this shot, since
    there is nothing left to look ahead into.

    Module-level rather than a method so it stays picklable by reference
    and can be sent to worker processes. Shared by `LookaheadAgent` as its
    primary ranking and by `GreedyAgent` as a tiebreaker.
    """
    state, angle, speed, angles = args
    trial, gain = simulate_shot(state, angle, speed)
    if trial.is_over:
        return angle, gain
    best_next_gain = max(simulate_shot(trial, next_angle, speed)[1] for next_angle in angles)
    return angle, gain + best_next_gain
