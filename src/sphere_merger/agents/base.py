"""Shared agent interface and candidate-shot simulation.

Every agent picks the next shot's angle/speed by simulating candidates on
a private deep copy of the round state (`simulate_shot`) -- the real
`state` passed to `choose_shot` is never mutated while evaluating options.
"""

from __future__ import annotations

import copy
from typing import Protocol

from sphere_merger.game.round import RoundState, play_shot

DEFAULT_SPEED = 10.0
ANGLE_RANGE_DEGREES = (0.0, 90.0)
ANGLE_STEP_DEGREES = 5.0


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


def simulate_shot(state: RoundState, angle_degrees: float, speed: float) -> tuple[RoundState, int]:
    """Play one shot on a deep copy of `state`, leaving `state` itself untouched.

    Returns the resulting copy and the score gained by this single shot
    (not the round's cumulative score).
    """
    trial = copy.deepcopy(state)
    score_before = trial.score
    play_shot(trial, angle_degrees, speed)
    return trial, trial.score - score_before
