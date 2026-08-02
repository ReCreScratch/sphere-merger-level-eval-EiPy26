"""Shared agent interface and candidate-shot simulation.

Every agent picks the next shot's angle/speed by simulating candidates on
a private clone of the round state (`simulate_shot`) -- the real `state`
passed to `choose_shot` is never mutated while evaluating options.
"""

from __future__ import annotations

import copy
from typing import Protocol

from sphere_merger.game.round import RoundState, play_shot
from sphere_merger.physics.engine import current_backend

DEFAULT_SPEED = 10.0
ANGLE_RANGE_DEGREES = (0.0, 90.0)
ANGLE_STEP_DEGREES = 1.0


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
    """Cheap `RoundState` clone for trial simulation, replacing `copy.deepcopy`.

    Shares `state.level` by reference instead of copying it: nothing on the
    `simulate_shot` path (`spawn_shot`, `advance_physics`) ever mutates it,
    so its `Boundary`/`PhysicsConfig`/`initial_spheres`/`shot_queue` subtree
    doesn't need isolating -- `deepcopy` walked and copied all of that on
    every single call regardless. `Vector2` is frozen, so a shallow copy of
    each `Sphere` is enough to isolate `spheres`; `remaining_queue` gets its
    own list since `spawn_shot` mutates it via `pop(0)`. This is on the
    hottest path in the codebase -- agents call it thousands of times per
    decision (`LookaheadAgent` alone: candidates + candidates^2) -- so the
    per-call constant factor matters far more here than elsewhere.
    """
    return RoundState(
        level=state.level,
        spheres=[copy.copy(sphere) for sphere in state.spheres],
        remaining_queue=list(state.remaining_queue),
        score=state.score,
        shots_taken=state.shots_taken,
    )


def simulate_shot(state: RoundState, angle_degrees: float, speed: float) -> tuple[RoundState, int]:
    """Play one shot on a clone of `state`, leaving `state` itself untouched.

    Returns the resulting clone and the score gained by this single shot
    (not the round's cumulative score).
    """
    if current_backend() == "rust":
        raise NotImplementedError(
            "native backend not yet ported to the 2D physics model -- use the Python "
            "backend (the default) until native/sphere_merger_native is updated to match"
        )
    trial = _clone_state(state)
    score_before = trial.score
    play_shot(trial, angle_degrees, speed)
    return trial, trial.score - score_before


def candidate_total_gain(args: tuple[RoundState, float, float, list[float]]) -> tuple[float, int]:
    """One candidate's own gain plus the best next-shot gain reachable from
    it (just its own gain if the round is already over there -- nothing
    left to look ahead into).

    Module-level (not a method) so it can be sent to worker processes for
    parallel evaluation (must be picklable by reference). Shared by
    `LookaheadAgent` (its primary ranking) and `GreedyAgent` (a tiebreaker
    among candidates that tie on immediate gain).
    """
    state, angle, speed, angles = args
    trial, gain = simulate_shot(state, angle, speed)
    if trial.is_over:
        return angle, gain
    best_next_gain = max(simulate_shot(trial, next_angle, speed)[1] for next_angle in angles)
    return angle, gain + best_next_gain
