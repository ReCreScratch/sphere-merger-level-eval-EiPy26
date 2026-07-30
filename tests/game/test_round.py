import pytest

from sphere_merger.game.level import LevelDefinition, radius_for_level
from sphere_merger.game.round import RoundState, play_shot, settle, start_round
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

FIELD = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0, z_min=0.0)


def _touching_pair_level(target_score: int = 100) -> LevelDefinition:
    """A level where the very first shot lands right next to an existing
    same-level sphere, close enough to merge on contact."""
    radius = radius_for_level(0)
    return LevelDefinition(
        boundary=FIELD,
        initial_spheres=[
            Sphere(Vector3(0.0, 0.0, radius), Vector3(0.0, 0.0, 0.0), radius, level=0)
        ],
        shot_queue=[0],
        spawn_position=Vector3(0.9, 0.0, radius),
        target_score=target_score,
    )


def _far_apart_level(target_score: int = 100) -> LevelDefinition:
    radius = radius_for_level(0)
    return LevelDefinition(
        boundary=FIELD,
        initial_spheres=[
            Sphere(Vector3(-4.0, 0.0, radius), Vector3(0.0, 0.0, 0.0), radius, level=0)
        ],
        shot_queue=[0],
        spawn_position=Vector3(4.0, 0.0, radius),
        target_score=target_score,
    )


def test_start_round_copies_initial_state_independently() -> None:
    level = _touching_pair_level()
    state = start_round(level)

    state.spheres.clear()
    state.remaining_queue.clear()

    assert len(level.initial_spheres) == 1
    assert level.shot_queue == [0]


def test_play_shot_spawns_and_pops_queue_even_without_merge() -> None:
    level = _far_apart_level()
    state = start_round(level)

    merged = play_shot(state, angle_degrees=0.0, speed=0.0)

    assert merged == []
    assert state.score == 0
    assert state.shots_taken == 1
    assert state.remaining_queue == []
    assert len(state.spheres) == 2


def test_play_shot_merges_and_scores_touching_same_level_pair() -> None:
    level = _touching_pair_level()
    state = start_round(level)

    merged = play_shot(state, angle_degrees=0.0, speed=0.0)

    assert merged == [1]
    assert state.score == 2  # default_merge_score(new_level=1, combo_index=1)
    assert len(state.spheres) == 1
    assert state.spheres[0].level == 1
    assert state.shots_taken == 1


def test_play_shot_ends_round_immediately_once_target_score_is_reached() -> None:
    level = _touching_pair_level(target_score=1)
    state = start_round(level)

    play_shot(state, angle_degrees=0.0, speed=0.0)

    assert state.is_won
    assert state.is_over


def test_round_is_lost_when_queue_empties_without_reaching_target() -> None:
    level = _far_apart_level(target_score=1000)
    state = start_round(level)

    play_shot(state, angle_degrees=0.0, speed=0.0)

    assert not state.is_won
    assert state.is_lost
    assert state.is_over


def test_play_shot_raises_once_round_is_over() -> None:
    state = RoundState(level=_far_apart_level(), spheres=[], remaining_queue=[], score=0)

    with pytest.raises(RuntimeError):
        play_shot(state, angle_degrees=0.0, speed=0.0)


def test_settle_zeroes_all_velocities() -> None:
    radius = radius_for_level(0)
    spheres = [
        Sphere(Vector3(0.0, 0.0, radius), Vector3(1.0, -2.0, 0.3), radius, level=0),
        Sphere(Vector3(3.0, 0.0, radius), Vector3(0.0, 0.0, 0.0), radius, level=0),
    ]

    settle(spheres)

    assert all(sphere.velocity == Vector3(0.0, 0.0, 0.0) for sphere in spheres)


def test_play_shot_leaves_a_settled_shot_at_true_rest() -> None:
    level = _far_apart_level()
    state = start_round(level)

    play_shot(state, angle_degrees=0.0, speed=0.0)

    assert all(sphere.velocity == Vector3(0.0, 0.0, 0.0) for sphere in state.spheres)
