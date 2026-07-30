"""Determinism tests: identical input must always yield identical output.

Physics with collisions is chaotic (tiny differences amplify), but the
simulation itself must never be a source of that variance -- the same
starting state has to produce the exact same trajectory every time,
otherwise level metrics and agent comparisons would not be reproducible.
"""

import copy

from hypothesis import given, settings
from hypothesis import strategies as st

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0, z_min=0.0)


def _run(spheres: list[Sphere], steps: int) -> list[Sphere]:
    for _ in range(steps):
        step(spheres, dt=0.05, boundary=FIELD)
    return spheres


def test_repeat_run_is_identical_for_a_fixed_scenario() -> None:
    scenario = [
        Sphere(Vector3(0.0, 0.0, 3.0), Vector3(1.0, 0.5, 0.0), radius=0.5, level=0),
        Sphere(Vector3(0.8, 0.0, 4.0), Vector3(-1.0, 0.0, 0.0), radius=0.5, level=1),
        Sphere(Vector3(-2.0, 1.0, 1.0), Vector3(0.0, -0.5, 2.0), radius=0.6, level=0),
    ]
    run_a = _run(copy.deepcopy(scenario), steps=50)
    run_b = _run(copy.deepcopy(scenario), steps=50)

    assert run_a == run_b


sphere_strategy = st.builds(
    Sphere,
    position=st.builds(
        Vector3,
        x=st.floats(min_value=-8.0, max_value=8.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-8.0, max_value=8.0, allow_nan=False, allow_infinity=False),
        z=st.floats(min_value=1.0, max_value=8.0, allow_nan=False, allow_infinity=False),
    ),
    velocity=st.builds(
        Vector3,
        x=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
        z=st.floats(min_value=-3.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    ),
    radius=st.floats(min_value=0.2, max_value=0.9, allow_nan=False, allow_infinity=False),
    level=st.integers(min_value=0, max_value=5),
)


@settings(max_examples=25)
@given(spheres=st.lists(sphere_strategy, min_size=1, max_size=4))
def test_repeat_run_is_identical_for_random_scenarios(spheres: list[Sphere]) -> None:
    run_a = _run(copy.deepcopy(spheres), steps=20)
    run_b = _run(copy.deepcopy(spheres), steps=20)

    assert run_a == run_b
