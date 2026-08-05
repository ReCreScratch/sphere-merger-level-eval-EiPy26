from typing import Any

import pytest

from sphere_merger.metrics.level_metrics import (
    LevelMetrics,
    luck_reach,
    payoff_concentration,
    skill_effect,
)


def test_payoff_concentration_ignores_shots_that_scored_nothing() -> None:
    # Same final score, opposite shapes: everything on the last shot vs.
    # everything already banked before it.
    assert payoff_concentration([0, 60]) == 1.0
    assert payoff_concentration([60, 60]) == 0.0


def test_payoff_concentration_of_a_single_shot_is_the_whole_score() -> None:
    assert payoff_concentration([40]) == 1.0


def test_payoff_concentration_is_undefined_without_points() -> None:
    assert payoff_concentration([]) is None
    assert payoff_concentration([0, 0]) is None


def test_skill_effect_scales_with_baseline_spread_not_just_distance() -> None:
    # Identical raw distance (informed - mean = 20), but the noisy
    # baseline could plausibly produce that gap by chance and the tight
    # one could not -- the effect size has to separate them.
    tight = skill_effect(30, [10, 10, 10, 10, 20])
    noisy = skill_effect(30, [0, 0, 20, 20, 10])
    assert tight is not None and noisy is not None
    assert tight > noisy


def test_skill_effect_is_undefined_without_baseline_spread() -> None:
    assert skill_effect(50, [10, 10, 10]) is None
    assert skill_effect(50, [10]) is None


def test_luck_reach_counts_samples_matching_the_informed_score() -> None:
    # Equal counts as reached: chance got the same result planning did.
    assert luck_reach(30, [10, 30, 40, 20]) == 0.5
    assert luck_reach(30, [10, 20, 25]) == 0.0


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "seed": 7,
        "random_scores": [0, 10, 20],
        "greedy_score": 20,
        "lookahead_score": 60,
        "lookahead_score_per_shot": [0, 60],
        "lookahead_max_combo": 4,
    }
    record.update(overrides)
    return record


def test_from_record_derives_every_dimension() -> None:
    metrics = LevelMetrics.from_record(_record())

    assert metrics.seed == 7
    assert metrics.depth_gap == 40
    assert metrics.payoff_conc == 1.0
    assert metrics.random_mean == 10
    assert metrics.max_combo == 4
    assert metrics.luck_share == 0.0
    assert metrics.skill_gain is not None and metrics.skill_gain > 0


def test_depth_gap_is_signed_so_a_greedy_win_stays_visible() -> None:
    # Never seen in 2000 real levels (lookahead is effectively optimal at
    # shot_count=2), but an abs() here would silently hide it if a future
    # shot count made lookahead beatable.
    metrics = LevelMetrics.from_record(_record(greedy_score=60, lookahead_score=20))

    assert metrics.depth_gap == -40


def test_from_record_rejects_pre_random_sampling_files() -> None:
    # Older runs saved a single `random_score`; silently treating those as
    # a missing baseline would produce metrics that look fine and mean
    # nothing.
    stale = _record()
    del stale["random_scores"]

    with pytest.raises(KeyError):
        LevelMetrics.from_record(stale)
