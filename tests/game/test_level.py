import pytest

from sphere_merger.game.level import LevelDefinition, generate_random_level, radius_for_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

FIELD = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0, z_min=0.0)
SPAWN = Vector3(0.0, 0.0, 3.0)


def test_generate_random_level_is_deterministic_for_same_seed() -> None:
    a = generate_random_level(
        42, FIELD, SPAWN, target_score=100, initial_sphere_count=6, shot_count=8
    )
    b = generate_random_level(
        42, FIELD, SPAWN, target_score=100, initial_sphere_count=6, shot_count=8
    )

    assert a == b


def test_generate_random_level_differs_for_different_seed() -> None:
    a = generate_random_level(
        1, FIELD, SPAWN, target_score=100, initial_sphere_count=6, shot_count=8
    )
    b = generate_random_level(
        2, FIELD, SPAWN, target_score=100, initial_sphere_count=6, shot_count=8
    )

    assert a != b


def test_generate_random_level_does_not_touch_global_random_state() -> None:
    import random

    random.seed(1234)
    state_before = random.getstate()
    generate_random_level(42, FIELD, SPAWN, target_score=100, initial_sphere_count=6, shot_count=8)
    assert random.getstate() == state_before


def test_generate_random_level_respects_counts_and_level_range() -> None:
    level = generate_random_level(
        7,
        FIELD,
        SPAWN,
        target_score=50,
        initial_sphere_count=4,
        shot_count=3,
        level_range=(1, 2),
    )

    assert len(level.initial_spheres) == 4
    assert len(level.shot_queue) == 3
    assert all(1 <= sphere.level <= 2 for sphere in level.initial_spheres)
    assert all(1 <= shot_level <= 2 for shot_level in level.shot_queue)


def test_generate_random_level_places_spheres_inside_boundary() -> None:
    level = generate_random_level(
        7, FIELD, SPAWN, target_score=50, initial_sphere_count=10, shot_count=3
    )

    for sphere in level.initial_spheres:
        assert FIELD.x_min <= sphere.position.x - sphere.radius
        assert sphere.position.x + sphere.radius <= FIELD.x_max
        assert FIELD.y_min <= sphere.position.y - sphere.radius
        assert sphere.position.y + sphere.radius <= FIELD.y_max


def test_generate_random_level_places_spheres_without_overlap() -> None:
    level = generate_random_level(
        7, FIELD, SPAWN, target_score=50, initial_sphere_count=10, shot_count=3
    )

    spheres = level.initial_spheres
    for i in range(len(spheres)):
        for j in range(i + 1, len(spheres)):
            a, b = spheres[i], spheres[j]
            dist = (a.position - b.position).length()
            assert dist >= a.radius + b.radius - 1e-9


def test_radius_for_level_is_currently_uniform_across_levels() -> None:
    # Temporary simplification -- see radius_for_level's docstring.
    assert radius_for_level(0) == radius_for_level(1) == radius_for_level(3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_score": 0},
        {"target_score": -10},
    ],
)
def test_level_definition_rejects_non_positive_target_score(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        LevelDefinition(
            boundary=FIELD,
            initial_spheres=[],
            shot_queue=[0],
            spawn_position=SPAWN,
            **kwargs,
        )


def test_level_definition_rejects_empty_shot_queue() -> None:
    with pytest.raises(ValueError):
        LevelDefinition(
            boundary=FIELD,
            initial_spheres=[],
            shot_queue=[],
            spawn_position=SPAWN,
            target_score=10,
        )


def test_level_definition_rejects_negative_shot_queue_levels() -> None:
    with pytest.raises(ValueError):
        LevelDefinition(
            boundary=FIELD,
            initial_spheres=[],
            shot_queue=[0, -1],
            spawn_position=SPAWN,
            target_score=10,
        )


def test_level_definition_accepts_hand_designed_values() -> None:
    level = LevelDefinition(
        boundary=FIELD,
        initial_spheres=[Sphere(Vector3(0.0, 0.0, 0.5), Vector3(0.0, 0.0, 0.0), 0.5, 0)],
        shot_queue=[0, 0, 1],
        spawn_position=SPAWN,
        target_score=10,
    )
    assert level.seed is None
