from sphere_merger.physics.vector import Vector3


def test_sub_gives_difference_vector() -> None:
    assert Vector3(3.0, 3.0, 3.0) - Vector3(1.0, 2.0, 3.0) == Vector3(2.0, 1.0, 0.0)


def test_scalar_mul_scales_all_components() -> None:
    assert Vector3(1.0, 2.0, 3.0) * 2.0 == Vector3(2.0, 4.0, 6.0)
