"""Energy/momentum invariants for the velocity and boundary solvers.

Momentum is always conserved by construction (the collision impulse is
applied with equal and opposite sign to both spheres). Kinetic energy is
conserved only when restitution is exactly 1 (perfectly elastic); values
below 1 must dissipate energy so a bouncing/sliding sphere settles instead
of moving forever.
"""

import pytest

from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import PhysicsConfig, step
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(x_min=-10.0, x_max=10.0, y_min=-10.0, y_max=10.0)


def _kinetic_energy(*spheres: Sphere) -> float:
    # No mass concept (see Sphere's docstring) -- unit mass everywhere.
    return sum(0.5 * s.velocity.dot(s.velocity) for s in spheres)


def test_elastic_head_on_collision_conserves_kinetic_energy() -> None:
    a = Sphere(Vector2(0.0, 0.0), Vector2(2.0, 0.0), radius=0.5, level=0)
    b = Sphere(Vector2(0.8, 0.0), Vector2(-2.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(friction=0.0, sphere_restitution=1.0)

    ke_before = _kinetic_energy(a, b)
    step([a, b], dt=0.01, boundary=FIELD, config=config)
    ke_after = _kinetic_energy(a, b)

    assert ke_after == pytest.approx(ke_before, rel=1e-9)


def test_inelastic_head_on_collision_loses_kinetic_energy() -> None:
    a = Sphere(Vector2(0.0, 0.0), Vector2(2.0, 0.0), radius=0.5, level=0)
    b = Sphere(Vector2(0.8, 0.0), Vector2(-2.0, 0.0), radius=0.5, level=0)
    config = PhysicsConfig(friction=0.0, sphere_restitution=0.5)

    ke_before = _kinetic_energy(a, b)
    step([a, b], dt=0.01, boundary=FIELD, config=config)
    ke_after = _kinetic_energy(a, b)

    assert ke_after < ke_before


def test_wall_bounces_lose_energy_and_sphere_eventually_stops() -> None:
    """A sphere bounced repeatedly off the walls with `boundary_restitution
    < 1` (and `friction > 0`) must lose energy and eventually come to rest --
    not bounce/slide forever at constant speed. Without gravity, friction
    alone (no floor-contact special case needed) is what guarantees this.
    """
    s = Sphere(Vector2(0.0, 0.0), Vector2(8.0, 3.0), radius=0.5, level=0)
    config = PhysicsConfig(friction=0.05, boundary_restitution=0.6)

    initial_energy = _kinetic_energy(s)
    max_energy_seen = initial_energy
    for _ in range(2000):
        step([s], dt=0.01, boundary=FIELD, config=config)
        max_energy_seen = max(max_energy_seen, _kinetic_energy(s))

    # Discrete integration can have tiny step-to-step numerical noise near
    # rest, so "never increases" is checked against the starting energy
    # rather than strictly step-by-step.
    assert max_energy_seen <= initial_energy + 1e-9
    assert s.velocity.length() == pytest.approx(0.0, abs=1e-6)
