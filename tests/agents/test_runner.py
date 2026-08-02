from collections.abc import Iterator

import pytest

from sphere_merger.agents.runner import record_playthrough
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2


class _FixedAngleAgent:
    def choose_shot(self, state: RoundState) -> tuple[float, float]:
        return (0.0, 0.0)


def _fake_play_shot(chains: Iterator[list[int]]):
    def play_shot(state: RoundState, angle_degrees: float, speed: float) -> list[int]:
        state.remaining_queue.pop(0)
        state.shots_taken += 1
        return next(chains)

    return play_shot


def test_record_playthrough_reports_longest_combo_across_shots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Three shots with combo chains of length 1, 2 and 0 -- longest is 2,
    # not the last shot's or the sum.
    monkeypatch.setattr(
        "sphere_merger.agents.runner.play_shot",
        _fake_play_shot(iter([[1], [1, 2], []])),
    )
    level = LevelDefinition(
        boundary=Boundary(-5.0, 5.0, -5.0, 5.0),
        initial_spheres=[],
        shot_queue=[0, 0, 0],
        spawn_position=Vector2(0.0, 0.0),
        target_score=999_999,
    )

    shots, _score, max_combo = record_playthrough(level, _FixedAngleAgent())

    assert len(shots) == 3
    assert max_combo == 2


def test_record_playthrough_max_combo_is_zero_without_merges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sphere_merger.agents.runner.play_shot",
        _fake_play_shot(iter([[], []])),
    )
    level = LevelDefinition(
        boundary=Boundary(-5.0, 5.0, -5.0, 5.0),
        initial_spheres=[],
        shot_queue=[0, 0],
        spawn_position=Vector2(0.0, 0.0),
        target_score=999_999,
    )

    _shots, _score, max_combo = record_playthrough(level, _FixedAngleAgent())

    assert max_combo == 0
