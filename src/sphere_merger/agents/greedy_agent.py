"""Agent that simulates every candidate angle one shot ahead and picks
whichever scores the most on that single shot."""

from __future__ import annotations

from sphere_merger.agents.base import (
    ANGLE_RANGE_DEGREES,
    ANGLE_STEP_DEGREES,
    DEFAULT_SPEED,
    candidate_angles,
    simulate_shot,
)
from sphere_merger.game.round import RoundState


class GreedyAgent:
    """Sweeps candidate angles at a fixed speed, picks the best immediate gain.

    Ties (including "no candidate scores anything") resolve to the first
    angle in sweep order, so the choice stays deterministic.
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
        """Simulate every candidate angle one shot ahead, return the best."""
        best_angle = self._angles[0]
        best_gain = -1
        for angle in self._angles:
            _, gain = simulate_shot(state, angle, self._speed)
            if gain > best_gain:
                best_gain = gain
                best_angle = angle
        return best_angle, self._speed
