import deal
import pytest

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0)


def test_wall_bounce_uses_boundary_restitution() -> None:
    s = Sphere(Vector2(9.96, 0.0), Vector2(4.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(friction=0.0, boundary_restitution=0.5)
    step([s], dt=0.01, boundary=FIELD, config=config)
    assert s.position.x == pytest.approx(9.5)
    assert s.velocity.x == pytest.approx(-2.0)


def test_friction_slows_a_moving_sphere() -> None:
    s = Sphere(Vector2(0.0, 0.0), Vector2(3.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(friction=0.2)
    step([s], dt=0.01, boundary=FIELD, config=config)
    assert s.velocity.x == pytest.approx(2.4)


def test_non_positive_dt_is_rejected() -> None:
    s = Sphere(Vector2(0.0, 0.0), Vector2(0.0, 0.0), radius=0.5, level=0)
    with pytest.raises(deal.PreContractError):
        step([s], dt=0.0, boundary=FIELD)


def test_colliding_spheres_separate_after_step() -> None:
    a = Sphere(Vector2(0.0, 0.0), Vector2(1.0, 0.0), radius=1.0, level=0)
    b = Sphere(Vector2(1.5, 0.0), Vector2(-1.0, 0.0), radius=1.0, level=0)
    step([a, b], dt=0.01, boundary=FIELD, config=PhysicsConfig())
    assert (b.position - a.position).length() >= a.radius + b.radius - 1e-6


def test_collision_filter_excludes_matching_pairs_from_resolution() -> None:
    a = Sphere(Vector2(0.0, 0.0), Vector2(1.0, 0.0), radius=1.0, level=0)
    b = Sphere(Vector2(1.5, 0.0), Vector2(-1.0, 0.0), radius=1.0, level=0)
    step(
        [a, b],
        dt=0.01,
        boundary=FIELD,
        config=PhysicsConfig(friction=0.0),
        collision_filter=lambda x, y: False,
    )
    # Neither the velocity solver nor the overlap solver ran: velocities are
    # unchanged and the spheres are still overlapping.
    assert a.velocity.x == pytest.approx(1.0)
    assert b.velocity.x == pytest.approx(-1.0)
    assert (b.position - a.position).length() < a.radius + b.radius


def test_collision_filter_still_resolves_pairs_it_allows() -> None:
    a = Sphere(Vector2(0.0, 0.0), Vector2(1.0, 0.0), radius=1.0, level=0)
    b = Sphere(Vector2(1.5, 0.0), Vector2(-1.0, 0.0), radius=1.0, level=0)
    step(
        [a, b],
        dt=0.01,
        boundary=FIELD,
        config=PhysicsConfig(friction=0.0),
        collision_filter=lambda x, y: True,
    )
    assert (b.position - a.position).length() >= a.radius + b.radius - 1e-6
