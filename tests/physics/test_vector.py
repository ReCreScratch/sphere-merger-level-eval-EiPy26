from sphere_merger.physics.vector import Vector2


def test_sub_gives_difference_vector() -> None:
    assert Vector2(3.0, 3.0) - Vector2(1.0, 2.0) == Vector2(2.0, 1.0)


def test_scalar_mul_scales_all_components() -> None:
    assert Vector2(1.0, 2.0) * 2.0 == Vector2(2.0, 4.0)
