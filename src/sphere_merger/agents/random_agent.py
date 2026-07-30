"""Agent that picks a uniformly random candidate angle each shot."""

from __future__ import annotations

import random

from sphere_merger.agents.base import ANGLE_RANGE_DEGREES, DEFAULT_SPEED
from sphere_merger.game.round import RoundState


class RandomAgent:
    """Picks the angle uniformly from `angle_range` at a fixed `speed`.

    Draws from a private, seeded `random.Random` instance, so the same
    `seed` always produces the same sequence of shots.
    """

    def __init__(
        self,
        seed: int,
        angle_range: tuple[float, float] = ANGLE_RANGE_DEGREES,
        speed: float = DEFAULT_SPEED,
    ) -> None:
        self._rng = random.Random(seed)
        self._angle_range = angle_range
        self._speed = speed

    def choose_shot(self, state: RoundState) -> tuple[float, float]:
        """Ignore `state`; return a random angle at the fixed speed."""
        angle = self._rng.uniform(*self._angle_range)
        return angle, self._speed
