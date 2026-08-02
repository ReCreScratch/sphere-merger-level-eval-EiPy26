import pytest

from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector2

ZERO = Vector2(0.0, 0.0)


def test_non_positive_radius_is_rejected() -> None:
    with pytest.raises(ValueError, match="radius"):
        Sphere(ZERO, ZERO, radius=0.0, level=0)


def test_negative_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="level"):
        Sphere(ZERO, ZERO, radius=1.0, level=-1)
