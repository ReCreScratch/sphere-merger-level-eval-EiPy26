import pytest

from sphere_merger.game.merge import merge_spheres, resolve_merges
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3


def _sphere(x: float, level: int = 0, radius: float = 0.5, vx: float = 0.0) -> Sphere:
    return Sphere(Vector3(x, 0.0, 1.0), Vector3(vx, 0.0, 0.0), radius=radius, level=level)


def test_merge_spheres_increments_level() -> None:
    merged = merge_spheres(_sphere(0.0), _sphere(0.5))
    assert merged.level == 1


def test_merge_spheres_conserves_mass() -> None:
    a, b = _sphere(0.0), _sphere(0.5)
    merged = merge_spheres(a, b)
    assert merged.mass == pytest.approx(a.mass + b.mass)


def test_merge_spheres_conserves_momentum() -> None:
    a = _sphere(0.0, vx=2.0)
    b = _sphere(0.5, vx=-1.0)
    merged = merge_spheres(a, b)
    assert merged.velocity.x * merged.mass == pytest.approx(
        a.velocity.x * a.mass + b.velocity.x * b.mass
    )


def test_merge_spheres_rejects_different_levels() -> None:
    with pytest.raises(ValueError):
        merge_spheres(_sphere(0.0, level=0), _sphere(0.5, level=1))


def test_resolve_merges_combines_touching_same_level_pair() -> None:
    spheres = [_sphere(0.0), _sphere(0.4)]
    new_levels = resolve_merges(spheres)

    assert new_levels == [1]
    assert len(spheres) == 1
    assert spheres[0].level == 1


def test_resolve_merges_ignores_non_touching_spheres() -> None:
    spheres = [_sphere(0.0), _sphere(10.0)]
    new_levels = resolve_merges(spheres)

    assert new_levels == []
    assert len(spheres) == 2


def test_resolve_merges_ignores_touching_different_level_spheres() -> None:
    spheres = [_sphere(0.0, level=0), _sphere(0.4, level=1)]
    new_levels = resolve_merges(spheres)

    assert new_levels == []
    assert len(spheres) == 2


def test_resolve_merges_only_pairs_each_sphere_once_per_call() -> None:
    # Three mutually touching same-level spheres: only the lowest-index
    # pair (0, 1) merges this call; sphere 2 stays untouched.
    spheres = [_sphere(0.0), _sphere(0.4), _sphere(0.8)]
    new_levels = resolve_merges(spheres)

    assert new_levels == [1]
    assert len(spheres) == 2
    assert {s.level for s in spheres} == {0, 1}


def test_resolve_merges_handles_multiple_independent_pairs() -> None:
    spheres = [_sphere(0.0), _sphere(0.4), _sphere(20.0), _sphere(20.4)]
    new_levels = resolve_merges(spheres)

    assert new_levels == [1, 1]
    assert len(spheres) == 2
