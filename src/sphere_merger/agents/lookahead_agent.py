"""Agent that simulates two shots ahead -- this shot's candidates, each
followed by the best candidate for the next queued shot -- and picks the
first shot leading to the best combined score."""

from __future__ import annotations

from sphere_merger.agents.base import (
    ANGLE_RANGE_DEGREES,
    ANGLE_STEP_DEGREES,
    DEFAULT_SPEED,
    candidate_angles,
    simulate_shot,
)
from sphere_merger.game.round import RoundState


class LookaheadAgent:
    """Sweeps this shot's candidates, each scored by its own gain plus the
    best next-shot candidate's gain, and picks the first shot with the best
    2-shot total.

    Falls back to the single shot's own gain once it ends the round or
    empties the queue -- there is nothing left to look ahead into.
    """

    def __init__(
        self,
        angle_range: tuple[float, float] = ANGLE_RANGE_DEGREES,
        angle_step: float = ANGLE_STEP_DEGREES,
        speed: float = DEFAULT_SPEED,
    ) -> None:
        self._angles = candidate_angles(angle_range, angle_step)
        self._speed = speed

    def choose_shot(self, state: RoundState) -> tuple[float, float]:
        """Simulate two shots ahead for every candidate, return the best first shot."""
        best_angle = self._angles[0]
        best_total_gain = -1
        for angle in self._angles:
            trial, gain = simulate_shot(state, angle, self._speed)
            total_gain = gain if trial.is_over else gain + self._best_next_gain(trial)
            if total_gain > best_total_gain:
                best_total_gain = total_gain
                best_angle = angle
        return best_angle, self._speed

    def _best_next_gain(self, state: RoundState) -> int:
        """Highest single-shot gain achievable from `state`'s next queued shot."""
        return max(simulate_shot(state, angle, self._speed)[1] for angle in self._angles)
