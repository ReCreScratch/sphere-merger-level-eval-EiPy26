from sphere_merger import score_multiplier


def test_score_multiplier_increases_with_merges() -> None:
    assert score_multiplier(0) < score_multiplier(1) < score_multiplier(2)
