import pytest

from sphere_merger.metrics.archetypes import Archetype, quantile, tag_batch
from sphere_merger.metrics.level_metrics import LevelMetrics


def _metrics(seed: int, **overrides: float) -> LevelMetrics:
    values: dict[str, float] = {
        "depth_gap": 0,
        "payoff_conc": 0.5,
        "random_mean": 10.0,
        "random_std": 5.0,
        "skill_gain": 1.0,
        "luck_share": 0.0,
        "max_combo": 2,
        "greedy_score": 20,
        "lookahead_score": 20,
    }
    values.update(overrides)
    return LevelMetrics(
        seed=seed,
        depth_gap=int(values["depth_gap"]),
        payoff_conc=values["payoff_conc"],
        random_mean=values["random_mean"],
        random_std=values["random_std"],
        skill_gain=values["skill_gain"],
        luck_share=values["luck_share"],
        max_combo=int(values["max_combo"]),
        greedy_score=int(values["greedy_score"]),
        lookahead_score=int(values["lookahead_score"]),
    )


def test_quantile_interpolates_between_neighbours() -> None:
    assert quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert quantile([0.0, 10.0], 0.25) == 2.5


def test_quantile_rejects_an_empty_batch() -> None:
    with pytest.raises(ValueError):
        quantile([], 0.5)


def test_aha_needs_both_a_high_gap_and_a_concentrated_payoff() -> None:
    # Same top-of-batch gap, different shapes: only the level whose points
    # all ride on the last shot is a trap for the obvious move.
    batch = [_metrics(i, depth_gap=0) for i in range(8)]
    batch.append(_metrics(100, depth_gap=50, payoff_conc=0.95))
    batch.append(_metrics(101, depth_gap=50, payoff_conc=0.4))

    tags = tag_batch(batch)

    assert Archetype.AHA in tags[100]
    assert Archetype.AHA not in tags[101]


def test_fair_hard_needs_a_high_ceiling_chance_misses_narrowly() -> None:
    batch = [_metrics(i, lookahead_score=20, random_mean=10.0, random_std=5.0) for i in range(8)]
    # High ceiling, chance far below it, and a tight baseline: one idea.
    batch.append(_metrics(100, lookahead_score=90, random_mean=1.0, random_std=0.5))
    # Same ceiling and low mean, but wildly swinging chance -- not "one idea".
    batch.append(_metrics(101, lookahead_score=90, random_mean=1.0, random_std=40.0))

    tags = tag_batch(batch)

    assert Archetype.FAIR_HARD in tags[100]
    assert Archetype.FAIR_HARD not in tags[101]


def test_luck_needs_chance_to_reach_the_plan_and_planning_to_add_little() -> None:
    batch = [_metrics(i, depth_gap=20) for i in range(8)]
    # Chance reaches lookahead and there was nothing to plan anyway.
    batch.append(_metrics(100, depth_gap=0, luck_share=0.2))
    # Chance reaches it, but planning still pays off a lot -- not a dice level.
    batch.append(_metrics(101, depth_gap=90, luck_share=0.2))

    tags = tag_batch(batch)

    assert Archetype.LUCK in tags[100]
    assert Archetype.LUCK not in tags[101]


def test_luck_still_fires_when_a_quarter_of_the_batch_has_no_gap_at_all() -> None:
    # The shape every real batch has: gaps floor at zero (lookahead never
    # loses to greedy at shot_count=2) and a large share sit exactly on
    # that floor, so the 25th percentile *is* the floor. A strict cutoff
    # there is unsatisfiable and the tag would never fire on real data --
    # which is exactly what happened before this was caught.
    batch = [_metrics(i, depth_gap=0) for i in range(4)]
    batch += [_metrics(10 + i, depth_gap=30) for i in range(4)]
    batch.append(_metrics(100, depth_gap=0, luck_share=0.15))

    tags = tag_batch(batch)

    assert Archetype.LUCK in tags[100]


def test_tags_are_independent_so_a_level_can_be_several_things() -> None:
    batch = [_metrics(i) for i in range(8)]
    batch.append(_metrics(100, depth_gap=50, payoff_conc=0.95, max_combo=9))

    tags = tag_batch(batch)

    assert {Archetype.AHA, Archetype.SPECTACLE} <= tags[100]


def test_an_unremarkable_level_carries_no_tag() -> None:
    batch = [_metrics(i) for i in range(8)]

    tags = tag_batch(batch)

    assert tags[3] == set()


def test_tagging_an_empty_batch_yields_nothing_rather_than_failing() -> None:
    assert tag_batch([]) == {}
