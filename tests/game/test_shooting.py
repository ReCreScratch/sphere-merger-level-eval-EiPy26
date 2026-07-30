import pytest

from sphere_merger.game.shooting import shoot
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3


def test_shoot_sets_velocity_from_angle_and_speed() -> None:
    s = Sphere(Vector3(0.0, 0.0, 2.0), Vector3(0.0, 0.0, 1.0), radius=1.0, level=0)
    shoot(s, angle_degrees=90.0, speed=4.0)
    assert s.velocity.x == pytest.approx(0.0, abs=1e-9)
    assert s.velocity.y == pytest.approx(4.0)


def test_shoot_leaves_vertical_velocity_untouched() -> None:
    s = Sphere(Vector3(0.0, 0.0, 2.0), Vector3(0.0, 0.0, 1.0), radius=1.0, level=0)
    shoot(s, angle_degrees=0.0, speed=3.0)
    assert s.velocity.z == 1.0
