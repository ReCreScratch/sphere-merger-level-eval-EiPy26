import pytest

from sphere_merger.physics.boundary import Boundary, resolve_boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0)


def test_invalid_bounds_are_rejected() -> None:
    with pytest.raises(ValueError, match="x_min"):
        Boundary(x_min=1.0, x_max=1.0, y_min=-5.0, y_max=5.0)


def test_sphere_within_bounds_is_unaffected() -> None:
    s = Sphere(Vector2(0.0, 0.0), Vector2(1.0, 1.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=1.0)
    assert s.position == Vector2(0.0, 0.0)
    assert s.velocity == Vector2(1.0, 1.0)


def test_x_wall_bounce_reflects_velocity_and_clamps_position() -> None:
    s = Sphere(Vector2(4.8, 0.0), Vector2(2.0, 0.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=0.5)
    assert s.position.x == 4.5
    assert s.velocity.x == -1.0


def test_y_wall_bounce_reflects_velocity_and_clamps_position() -> None:
    s = Sphere(Vector2(0.0, -4.8), Vector2(0.0, -2.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=0.5)
    assert s.position.y == -4.5
    assert s.velocity.y == 1.0


def test_penetrating_sphere_moving_away_keeps_its_velocity() -> None:
    """A sphere pushed into a wall by `resolve_overlap` must not be flipped back in."""
    s = Sphere(Vector2(-4.6, 0.0), Vector2(1.0, 0.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=0.5)
    assert s.position.x == -4.5
    assert s.velocity.x == 1.0


def test_penetrating_sphere_moving_into_wall_is_reflected() -> None:
    s = Sphere(Vector2(-4.6, 0.0), Vector2(-1.0, 0.0), radius=0.5, level=0)
    resolve_boundary(s, FIELD, restitution=0.5)
    assert s.position.x == -4.5
    assert s.velocity.x == 0.5
