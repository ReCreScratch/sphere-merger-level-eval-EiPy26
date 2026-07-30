import pytest

from sphere_merger.physics.boundary import Boundary, resolve_boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

FIELD = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0, z_min=0.0)


def test_invalid_bounds_are_rejected() -> None:
    with pytest.raises(ValueError, match="x_min"):
        Boundary(x_min=1.0, x_max=1.0, y_min=-5.0, y_max=5.0, z_min=0.0)


def test_sphere_within_bounds_is_unaffected() -> None:
    s = Sphere(Vector3(0.0, 0.0, 1.0), Vector3(1.0, 1.0, 1.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=1.0)
    assert s.position == Vector3(0.0, 0.0, 1.0)
    assert s.velocity == Vector3(1.0, 1.0, 1.0)


def test_wall_bounce_reflects_velocity_and_clamps_position() -> None:
    s = Sphere(Vector3(4.8, 0.0, 1.0), Vector3(2.0, 0.0, 0.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=0.5)
    assert s.position.x == 4.5
    assert s.velocity.x == -1.0


def test_ceiling_is_optional() -> None:
    open_top = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0, z_min=0.0)
    s = Sphere(Vector3(0.0, 0.0, 1000.0), Vector3(0.0, 0.0, 10.0), radius=0.5, level=0)
    resolve_boundary(s, open_top, restitution=1.0)
    assert s.position.z == 1000.0
    assert s.velocity.z == 10.0
