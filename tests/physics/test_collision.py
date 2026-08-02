import deal
import pytest
from hypothesis import given
from hypothesis import strategies as st

from sphere_merger.physics.collision import (
    OVERLAP_EPSILON,
    distance,
    find_colliding_pairs,
    is_colliding,
    resolve_overlap,
)
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

ZERO = Vector2(0.0, 0.0)


def _sphere_at(x: float, radius: float = 1.0) -> Sphere:
    return Sphere(Vector2(x, 0.0), ZERO, radius=radius, level=0)


def test_is_colliding_true_when_overlapping() -> None:
    assert is_colliding(_sphere_at(0.0), _sphere_at(1.5))


def test_is_colliding_false_when_apart() -> None:
    assert not is_colliding(_sphere_at(0.0), _sphere_at(5.0))


def test_find_colliding_pairs_returns_only_overlapping_indices() -> None:
    spheres = [_sphere_at(0.0), _sphere_at(1.5), _sphere_at(10.0)]
    assert find_colliding_pairs(spheres) == [(0, 1)]


def test_resolve_overlap_requires_actual_overlap() -> None:
    with pytest.raises(deal.PreContractError):
        resolve_overlap(_sphere_at(0.0), _sphere_at(5.0))


def test_resolve_overlap_separates_two_spheres() -> None:
    a, b = _sphere_at(0.0), _sphere_at(1.5)
    resolve_overlap(a, b)
    assert distance(a, b) >= a.radius + b.radius - OVERLAP_EPSILON


def test_resolve_overlap_coincident_uses_relative_velocity_direction() -> None:
    a = Sphere(ZERO, Vector2(0.0, 0.0), radius=1.0, level=0)
    b = Sphere(ZERO, Vector2(0.0, 5.0), radius=1.0, level=0)
    resolve_overlap(a, b)
    assert a.position.y < 0.0
    assert b.position.y > 0.0
    assert a.position.x == 0.0
    assert b.position.x == 0.0


def test_resolve_overlap_coincident_and_no_relative_velocity_falls_back_to_x_axis() -> None:
    a = Sphere(ZERO, Vector2(2.0, 0.0), radius=1.0, level=0)
    b = Sphere(ZERO, Vector2(2.0, 0.0), radius=1.0, level=0)
    resolve_overlap(a, b)
    assert a.position.x < 0.0
    assert b.position.x > 0.0
    assert a.position.y == 0.0 == b.position.y


radii = st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
overlap_amounts = st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False)


@given(radius_a=radii, radius_b=radii, overlap_amount=overlap_amounts)
def test_resolve_overlap_always_removes_overlap(
    radius_a: float, radius_b: float, overlap_amount: float
) -> None:
    dist = max(radius_a + radius_b - overlap_amount, 0.01)
    a = Sphere(ZERO, ZERO, radius=radius_a, level=0)
    b = Sphere(Vector2(dist, 0.0), ZERO, radius=radius_b, level=0)
    resolve_overlap(a, b)
    assert distance(a, b) >= a.radius + b.radius - 1e-6
