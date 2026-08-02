"""Parity check: the Rust port of `physics.engine.step`
(`sphere_merger_native.step_native`, see `native/sphere_merger_native/`)
must produce the same trajectory as the Python reference implementation,
step for step -- within float tolerance, not bit-exact (see
`_assert_matches`'s docstring for why).

Skipped entirely if the native extension hasn't been built (see
README.md) -- it's an optional accelerator, not a hard dependency for
running the test suite.
"""

import copy
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

sphere_merger_native = pytest.importorskip("sphere_merger_native")

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0)
CONFIG = PhysicsConfig()
DT = 0.05


def _same_level(a: Sphere, b: Sphere) -> bool:
    return a.level == b.level


def _boundary_tuple(boundary: Boundary) -> tuple[float, float, float, float]:
    return (boundary.x_min, boundary.x_max, boundary.y_min, boundary.y_max)


def _config_tuple(config: PhysicsConfig) -> tuple[float, float, float]:
    return (config.friction, config.sphere_restitution, config.boundary_restitution)


def _to_tuples(spheres: list[Sphere]) -> list[tuple[float, float, float, float, float, int]]:
    return [
        (s.position.x, s.position.y, s.velocity.x, s.velocity.y, s.radius, s.level) for s in spheres
    ]


def _run_python(spheres: list[Sphere], steps: int) -> list[Sphere]:
    for _ in range(steps):
        step(spheres, DT, FIELD, CONFIG, collision_filter=lambda a, b: not _same_level(a, b))
    return spheres


def _run_native(
    spheres: list[tuple[float, float, float, float, float, int]], steps: int
) -> list[tuple[float, float, float, float, float, int]]:
    for _ in range(steps):
        spheres = sphere_merger_native.step_native(
            spheres, DT, _boundary_tuple(FIELD), _config_tuple(CONFIG), True
        )
    return spheres


def _isclose(a: Vector2, b: Vector2) -> bool:
    return all(
        math.isclose(getattr(a, axis), getattr(b, axis), rel_tol=1e-9, abs_tol=1e-9)
        for axis in ("x", "y")
    )


def _assert_matches(python_result: list[Sphere], native_result: list[tuple]) -> None:
    """Positions/velocities only have to match within float tolerance, not
    exactly: `mass` (`radius ** 3`) goes through Python's `pow` (MSVC CRT)
    on one side and Rust's `powf` (MinGW libm) on the other -- unlike +/-/*
    // /sqrt, `pow` isn't IEEE754-mandated to be correctly rounded, so the
    two can differ in the last bit for an arbitrary radius (verified: for
    `radius=0.5`, the actual game's constant via `radius_for_level`, both
    sides compute exactly `0.125`, no rounding involved either way -- this
    only shows up for arbitrary radii, as hypothesis generates here).
    """
    assert len(python_result) == len(native_result)
    for sphere, (x, y, vx, vy, radius, level) in zip(python_result, native_result, strict=True):
        assert _isclose(sphere.position, Vector2(x, y))
        assert _isclose(sphere.velocity, Vector2(vx, vy))
        assert sphere.radius == radius
        assert sphere.level == level


def test_native_step_matches_python_for_a_fixed_scenario() -> None:
    scenario = [
        Sphere(Vector2(0.0, 0.0), Vector2(1.0, 0.5), radius=0.5, level=0),
        Sphere(Vector2(0.8, 0.0), Vector2(-1.0, 0.0), radius=0.5, level=1),
        Sphere(Vector2(-2.0, 1.0), Vector2(0.0, -0.5), radius=0.6, level=0),
    ]
    python_result = _run_python(copy.deepcopy(scenario), steps=100)
    native_result = _run_native(_to_tuples(scenario), steps=100)

    _assert_matches(python_result, native_result)


sphere_strategy = st.builds(
    Sphere,
    position=st.builds(
        Vector2,
        x=st.floats(min_value=-8.0, max_value=8.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-8.0, max_value=8.0, allow_nan=False, allow_infinity=False),
    ),
    velocity=st.builds(
        Vector2,
        x=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    ),
    radius=st.floats(min_value=0.2, max_value=0.9, allow_nan=False, allow_infinity=False),
    level=st.integers(min_value=0, max_value=5),
)


@settings(max_examples=25)
@given(spheres=st.lists(sphere_strategy, min_size=1, max_size=6))
def test_native_step_matches_python_for_random_scenarios(spheres: list[Sphere]) -> None:
    python_result = _run_python(copy.deepcopy(spheres), steps=30)
    native_result = _run_native(_to_tuples(spheres), steps=30)

    _assert_matches(python_result, native_result)
