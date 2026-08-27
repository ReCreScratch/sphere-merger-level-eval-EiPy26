"""Agent that simulates two shots ahead -- this shot's candidates, each
followed by the best candidate for the next queued shot -- and picks the
first shot leading to the best combined score."""

from __future__ import annotations

from concurrent.futures import Executor

from sphere_merger.agents.base import (
    ANGLE_RANGE_DEGREES,
    ANGLE_STEP_DEGREES,
    DEFAULT_SPEED,
    EXECUTOR_CHUNKSIZE,
    candidate_angles,
    candidate_total_gain,
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
        executor: Executor | None = None,
    ) -> None:
        """`executor`, if given, spreads this shot's candidates -- each
        carrying its own full next-shot sweep -- over worker processes.
        Candidates are independent, so this only affects speed, never the
        result. The caller owns the executor's lifecycle.
        """
        self._angles = candidate_angles(angle_range, angle_step)
        self._speed = speed
        self._executor = executor

    def choose_shot(self, state: RoundState) -> tuple[float, float]:
        """Simulate two shots ahead for every candidate, return the best first shot."""
        args = [(state, angle, self._speed, self._angles) for angle in self._angles]
        if self._executor is not None:
            results = list(
                self._executor.map(candidate_total_gain, args, chunksize=EXECUTOR_CHUNKSIZE)
            )
        else:
            results = [candidate_total_gain(a) for a in args]
        best_angle, _ = max(results, key=lambda result: result[1])
        return best_angle, self._speed
