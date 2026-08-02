from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.shrink import shrink_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(-5.0, 5.0, -5.0, 5.0)


def _level(sphere_count: int, shot_count: int) -> LevelDefinition:
    return LevelDefinition(
        boundary=FIELD,
        initial_spheres=[
            Sphere(Vector2(float(i), 0.0), Vector2(0.0, 0.0), radius=0.5, level=0)
            for i in range(sphere_count)
        ],
        shot_queue=[0] * shot_count,
        spawn_position=Vector2(0.0, 0.0),
        target_score=999,
    )


def test_shrink_level_drops_spheres_down_to_the_predicates_floor() -> None:
    level = _level(sphere_count=4, shot_count=1)

    shrunk = shrink_level(level, is_interesting=lambda lvl: len(lvl.initial_spheres) >= 2)

    assert len(shrunk.initial_spheres) == 2


def test_shrink_level_never_touches_the_shot_queue() -> None:
    level = _level(sphere_count=3, shot_count=3)

    shrunk = shrink_level(level, is_interesting=lambda _lvl: True)

    assert len(shrunk.initial_spheres) == 0
    assert len(shrunk.shot_queue) == 3


def test_shrink_level_is_a_no_op_when_no_sphere_can_be_dropped() -> None:
    level = _level(sphere_count=2, shot_count=1)

    shrunk = shrink_level(level, is_interesting=lambda lvl: len(lvl.initial_spheres) >= 2)

    assert len(shrunk.initial_spheres) == 2
