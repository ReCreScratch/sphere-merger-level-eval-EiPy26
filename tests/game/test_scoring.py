from sphere_merger.game.scoring import default_merge_score


def test_default_merge_score_is_exponential_in_level() -> None:
    assert default_merge_score(new_level=0, combo_index=1) == 1
    assert default_merge_score(new_level=1, combo_index=1) == 2
    assert default_merge_score(new_level=2, combo_index=1) == 4


def test_default_merge_score_scales_linearly_with_combo() -> None:
    assert default_merge_score(new_level=3, combo_index=1) == 8
    assert default_merge_score(new_level=3, combo_index=2) == 16
    assert default_merge_score(new_level=3, combo_index=3) == 24
