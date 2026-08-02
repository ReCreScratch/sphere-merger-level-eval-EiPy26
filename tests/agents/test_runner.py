from collections.abc import Iterator

import pytest

from sphere_merger.agents.runner import record_playthrough, shrink_to_used_spheres
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
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


def _three_sphere_level() -> LevelDefinition:
    boundary = Boundary(-5.0, 5.0, -5.0, 5.0)
    return LevelDefinition(
        boundary=boundary,
        initial_spheres=[
            Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=0.5, level=0),
            Sphere(Vector2(1.0, 0.0), Vector2(0.0, 0.0), radius=0.5, level=0),
            Sphere(Vector2(2.0, 0.0), Vector2(0.0, 0.0), radius=0.5, level=0),
        ],
        shot_queue=[0],
        spawn_position=Vector2(0.0, 0.0),
        target_score=999_999,
    )


def test_shrink_to_used_spheres_keeps_anything_used_by_any_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # index 0 is only touched by agent_a, index 1 only by agent_b, index 2
    # by neither -- only index 2 should ever be dropped, since each of the
    # other two matters to at least one agent even though neither agent
    # alone touches both.
    agent_a = _FixedAngleAgent()
    agent_b = _FixedAngleAgent()

    def fake_record_shots(level: LevelDefinition, agent: object) -> list[tuple[float, float]]:
        return [(1.0, 0.0)] if agent is agent_a else [(2.0, 0.0)]

    def fake_touched(level: LevelDefinition, shots: list[tuple[float, float]]) -> set[int]:
        if len(level.initial_spheres) != 3:
            # Second pass, on the already-shrunk level: nothing further to
            # find -- lets the loop converge instead of looping forever.
            return set(range(len(level.initial_spheres)))
        return {0} if shots == [(1.0, 0.0)] else {1}

    monkeypatch.setattr("sphere_merger.agents.runner.record_shots", fake_record_shots)
    monkeypatch.setattr("sphere_merger.agents.runner.touched_sphere_indices", fake_touched)

    shrunk = shrink_to_used_spheres(_three_sphere_level(), [agent_a, agent_b])

    assert len(shrunk.initial_spheres) == 2
    assert {round(s.position.x) for s in shrunk.initial_spheres} == {0, 1}
