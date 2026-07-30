from sphere_merger.rendering.renderer import shadow_radius_px


def test_shadow_shrinks_with_height() -> None:
    assert shadow_radius_px(100, 0.0) > shadow_radius_px(100, 5.0)


def test_shadow_never_fully_disappears() -> None:
    assert shadow_radius_px(100, 1000.0) > 0
