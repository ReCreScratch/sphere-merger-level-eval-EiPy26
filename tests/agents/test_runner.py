from collections.abc import Iterator

import pytest

from sphere_merger.agents.runner import (
    ShotRecord,
    max_combo,
    record_playthrough,
    shrink_to_used_spheres,
)
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

    records = record_playthrough(level, _FixedAngleAgent())

    assert len(records) == 3
    assert max_combo(records) == 2


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

    records = record_playthrough(level, _FixedAngleAgent())

    assert max_combo(records) == 0


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

    def fake_record_playthrough(level: LevelDefinition, agent: object) -> list[ShotRecord]:
        angle = 1.0 if agent is agent_a else 2.0
        return [ShotRecord(angle=angle, speed=0.0, score_after=0, merged_levels=[])]

    def fake_touched(level: LevelDefinition, shots: list[tuple[float, float]]) -> set[int]:
        if len(level.initial_spheres) != 3:
            # Second pass, on the already-shrunk level: nothing further to
            # find -- lets the loop converge instead of looping forever.
            return set(range(len(level.initial_spheres)))
        return {0} if shots == [(1.0, 0.0)] else {1}

    monkeypatch.setattr("sphere_merger.agents.runner.record_playthrough", fake_record_playthrough)
    monkeypatch.setattr("sphere_merger.agents.runner.touched_sphere_indices", fake_touched)

    result = shrink_to_used_spheres(
        _three_sphere_level(), iterated_agents=[agent_a, agent_b], fixed_playthroughs=[]
    )

    assert len(result.level.initial_spheres) == 2
    assert {round(s.position.x) for s in result.level.initial_spheres} == {0, 1}


def _five_sphere_level() -> LevelDefinition:
    boundary = Boundary(-5.0, 5.0, -5.0, 5.0)
    return LevelDefinition(
        boundary=boundary,
        initial_spheres=[
            Sphere(Vector2(float(i), 0.0), Vector2(0.0, 0.0), radius=0.5, level=0) for i in range(5)
        ],
        shot_queue=[0],
        spawn_position=Vector2(0.0, 0.0),
        target_score=999_999,
    )


def test_shrink_to_used_spheres_checks_fixed_playthroughs_once_and_iterated_agents_every_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # index 0 is protected by a precomputed "fixed" playthrough (like a
    # prior lookahead run's shots) whose touched-check runs exactly once,
    # on the original 5-sphere level; the "iterated" agent (like greedy)
    # touches {1, 2} on that first pass, but after 3 and 4 are dropped, its
    # touched set shrinks to just {1} on the smaller field (simulating
    # greedy finding a different, simpler shot once the removed spheres
    # are out of the way) -- exposing index 2 as safe to drop too, on a
    # second pass.
    iterated_agent = _FixedAngleAgent()
    fixed_marker = [(9.0, 9.0)]
    fixed_check_sizes: list[int] = []

    def fake_record_playthrough(level: LevelDefinition, agent: object) -> list[ShotRecord]:
        return [ShotRecord(angle=1.0, speed=1.0, score_after=0, merged_levels=[])]

    def fake_touched(level: LevelDefinition, shots: list[tuple[float, float]]) -> set[int]:
        if shots == fixed_marker:
            fixed_check_sizes.append(len(level.initial_spheres))
            return {0}
        return {1, 2} if len(level.initial_spheres) == 5 else {1}

    monkeypatch.setattr("sphere_merger.agents.runner.record_playthrough", fake_record_playthrough)
    monkeypatch.setattr("sphere_merger.agents.runner.touched_sphere_indices", fake_touched)

    result = shrink_to_used_spheres(
        _five_sphere_level(),
        iterated_agents=[iterated_agent],
        fixed_playthroughs=[(fixed_marker, 0, 0)],
    )

    assert len(result.level.initial_spheres) == 2
    assert {round(s.position.x) for s in result.level.initial_spheres} == {0, 1}
    # The fixed agent's touched-check only ever ran once, against the
    # original 5-sphere level -- never re-simulated as the field shrank.
    assert fixed_check_sizes == [5]
