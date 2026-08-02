"""Parity check: `agents.base.simulate_shot`'s native-backend branch
(`sphere_merger_native.simulate_shot_native`, the whole settle loop -- spawn,
physics steps, merges, scoring -- in one FFI call) must produce the same
resulting `RoundState` as the pure-Python path, for the same starting state
and candidate shot -- within float tolerance, not bit-exact.

The actual game's `radius_for_level` is currently a constant
(`BASE_RADIUS = 0.5`), so unlike `test_native_step_parity.py`, `pow`/`powf`
(mass) can't be the source of any mismatch here (`0.5 ** 3` is exact, no
fractional bits to round either way). The source here is `cos`/`sin`
(spawn velocity from angle): verified for one failing case that Python's
`math.cos` (MSVC CRT) and Rust's `f64::cos` (MinGW libm) differ by exactly
1 ULP for the same input -- like `pow`, correct rounding isn't IEEE754-
mandated for transcendental functions, so cross-compiler bit-parity can't
be guaranteed. That single-ULP seed then compounds over the settle loop's
collisions (chaotic, like any collision physics -- see
`test_determinism.py`'s docstring) into a still-tiny (~1e-15 relative in
the case above) but no-longer-single-bit difference by the end.

Practical upshot: mixing backends run-over-run for the same level isn't
bit-reproducible the way staying on one backend is; scores/merge counts
are unaffected in every case observed so far, only continuous
position/velocity values by a negligible amount.

Skipped entirely if the native extension hasn't been built (see README.md).
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sphere_merger.agents.base import simulate_shot
from sphere_merger.game.level import generate_random_level, radius_for_level
from sphere_merger.game.round import start_round
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

pytest.importorskip("sphere_merger_native")

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0, z_min=0.0)
SPAWN = Vector3(FIELD.x_min + 1.0, FIELD.y_min + 1.0, FIELD.z_min + radius_for_level(0))


def _level(seed: int):
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=40,
        initial_sphere_count=5,
        shot_count=3,
        level_range=(0, 2),
    )


def _isclose_vec(a: Vector3, b: Vector3) -> bool:
    return all(
        math.isclose(getattr(a, axis), getattr(b, axis), rel_tol=1e-6, abs_tol=1e-6)
        for axis in ("x", "y", "z")
    )


def _isclose_sphere(a: Sphere, b: Sphere) -> bool:
    return (
        _isclose_vec(a.position, b.position)
        and _isclose_vec(a.velocity, b.velocity)
        and a.radius == b.radius
        and a.level == b.level
    )


@settings(max_examples=20, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=9),
    angle=st.floats(min_value=0.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    speed=st.floats(min_value=5.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_native_simulate_shot_matches_python(seed: int, angle: float, speed: float) -> None:
    state = start_round(_level(seed))

    python_trial, python_gain = simulate_shot(state, angle, speed)
    with native_backend():
        rust_trial, rust_gain = simulate_shot(state, angle, speed)

    assert python_gain == rust_gain
    assert python_trial.score == rust_trial.score
    assert python_trial.remaining_queue == rust_trial.remaining_queue
    assert python_trial.shots_taken == rust_trial.shots_taken
    assert len(python_trial.spheres) == len(rust_trial.spheres)
    for python_sphere, rust_sphere in zip(python_trial.spheres, rust_trial.spheres, strict=True):
        assert _isclose_sphere(python_sphere, rust_sphere)
