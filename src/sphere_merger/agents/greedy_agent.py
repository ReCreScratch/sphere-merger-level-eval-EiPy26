"""Agent that simulates every candidate angle one shot ahead and picks
whichever scores the most on that single shot."""

from __future__ import annotations

from concurrent.futures import Executor

from sphere_merger.agents.base import (
    ANGLE_RANGE_DEGREES,
    ANGLE_STEP_DEGREES,
    DEFAULT_SPEED,
    EXECUTOR_CHUNKSIZE,
    candidate_angles,
    candidate_total_gain,
    simulate_shot,
)
from sphere_merger.game.round import RoundState


def _candidate_gain(args: tuple[RoundState, float, float]) -> tuple[float, int]:
    """Gain of one candidate shot -- a module-level function so it can be
    sent to worker processes (must be picklable by reference)."""
    state, angle, speed = args
    _, gain = simulate_shot(state, angle, speed)
    return angle, gain


class GreedyAgent:
    """Sweeps candidate angles at a fixed speed, picks the best immediate gain.

    Ties are not broken by sweep order. Each tied candidate is instead
    checked one shot further, by the same criterion `LookaheadAgent` ranks
    by, and the best of those wins. This never trades immediate score for
    a better future -- ties are the only thing it looks past this shot
    for; it just stops choosing blindly between equally scoring options.
    """

    def __init__(
        self,
        angle_range: tuple[float, float] = ANGLE_RANGE_DEGREES,
        angle_step: float = ANGLE_STEP_DEGREES,
        speed: float = DEFAULT_SPEED,
        executor: Executor | None = None,
    ) -> None:
        """`executor`, if given, spreads the candidate simulations over
        worker processes instead of running them in the caller. Candidates
        are independent, so this only affects speed, never the result. The
        caller owns the executor's lifecycle.
        """
        self._angles = candidate_angles(angle_range, angle_step)
        self._speed = speed
        self._executor = executor

    def choose_shot(self, state: RoundState) -> tuple[float, float]:
        """Simulate every candidate angle one shot ahead, return the best."""
        args = [(state, angle, self._speed) for angle in self._angles]
        if self._executor is not None:
            results = list(self._executor.map(_candidate_gain, args, chunksize=EXECUTOR_CHUNKSIZE))
        else:
            results = [_candidate_gain(a) for a in args]

        best_gain = max(gain for _, gain in results)
        tied = [angle for angle, gain in results if gain == best_gain]
        if len(tied) == 1:
            return tied[0], self._speed

        deeper_args = [(state, angle, self._speed, self._angles) for angle in tied]
        if self._executor is not None:
            deeper_results = list(
                self._executor.map(candidate_total_gain, deeper_args, chunksize=EXECUTOR_CHUNKSIZE)
            )
        else:
            deeper_results = [candidate_total_gain(a) for a in deeper_args]
        best_angle, _ = max(deeper_results, key=lambda result: result[1])
        return best_angle, self._speed
