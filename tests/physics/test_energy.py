"""Energy/momentum invariants for the velocity and boundary solvers.

Momentum is always conserved by construction (the collision impulse is
applied with equal and opposite sign to both spheres). Kinetic energy is
conserved only when restitution is exactly 1 (perfectly elastic); values
below 1 must dissipate energy so a bouncing sphere settles instead of
hopping forever.
"""

import pytest

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0, z_min=0.0)


def _kinetic_energy(*spheres: Sphere) -> float:
    return sum(0.5 * s.mass * s.velocity.dot(s.velocity) for s in spheres)


def _mechanical_energy(sphere: Sphere, gravity: float) -> float:
    kinetic = 0.5 * sphere.mass * sphere.velocity.dot(sphere.velocity)
    potential = sphere.mass * gravity * (sphere.position.z - FIELD.z_min)
    return kinetic + potential


def test_elastic_head_on_collision_conserves_kinetic_energy() -> None:
    a = Sphere(Vector3(0.0, 0.0, 1.0), Vector3(2.0, 0.0, 0.0), radius=0.5, level=0)
    b = Sphere(Vector3(0.8, 0.0, 1.0), Vector3(-2.0, 0.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(gravity=0.0, sphere_restitution=1.0)

    ke_before = _kinetic_energy(a, b)
    step([a, b], dt=0.01, boundary=FIELD, config=config)
    ke_after = _kinetic_energy(a, b)

    assert ke_after == pytest.approx(ke_before, rel=1e-9)


def test_inelastic_head_on_collision_loses_kinetic_energy() -> None:
    a = Sphere(Vector3(0.0, 0.0, 1.0), Vector3(2.0, 0.0, 0.0), radius=0.5, level=0)
    b = Sphere(Vector3(0.8, 0.0, 1.0), Vector3(-2.0, 0.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(gravity=0.0, sphere_restitution=0.5)

    ke_before = _kinetic_energy(a, b)
    step([a, b], dt=0.01, boundary=FIELD, config=config)
    ke_after = _kinetic_energy(a, b)

    assert ke_after < ke_before


def test_inelastic_floor_bounce_never_exceeds_starting_energy_and_settles() -> None:
    """A ball dropped with boundary_restitution < 1 must lose height each
    bounce and eventually come to rest -- not hop forever at constant height.
    """
    s = Sphere(Vector3(0.0, 0.0, 5.0), Vector3(0.0, 0.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(
        gravity=9.81, friction_min=0.0, friction_max=0.0, boundary_restitution=0.6
    )

    initial_energy = _mechanical_energy(s, config.gravity)
    max_energy_seen = initial_energy
    for _ in range(600):
        step([s], dt=0.01, boundary=FIELD, config=config)
        max_energy_seen = max(max_energy_seen, _mechanical_energy(s, config.gravity))

    # Discrete integration can have tiny step-to-step numerical noise near
    # rest, so "never increases" is checked against the starting energy
    # rather than strictly step-by-step.
    assert max_energy_seen <= initial_energy + 1e-9
    # Settled: at rest on the floor, not still hopping (with friction=0, the
    # unavoidable leftover is the resting height's own potential energy).
    assert s.velocity.length() == pytest.approx(0.0, abs=1e-9)
    assert s.position.z == pytest.approx(FIELD.z_min + s.radius, abs=1e-2)
