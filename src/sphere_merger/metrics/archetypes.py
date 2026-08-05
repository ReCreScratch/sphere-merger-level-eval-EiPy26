"""Tagging levels by *what kind* of interesting they are, rather than
scoring them on a single "fun" number.

A single score would average away exactly the distinctions worth having:
a spectacular cascade and a subtle trap are both interesting, for
opposite reasons, and a level can be neither, either or both. So levels
get a set of tags instead, and a level with no tag is a perfectly normal
level, not a failure.

Thresholds are relative to the batch being tagged, never absolute --
scores shift substantially with the initial sphere count (5-sphere levels
score far lower across the board than 8-sphere ones), so a fixed cutoff
would tag one regime almost entirely and the other not at all.
"""

from __future__ import annotations

from enum import Enum

from sphere_merger.metrics.level_metrics import LevelMetrics


class Archetype(Enum):
    """What makes a level stand out, if anything."""

    AHA = "aha"
    """Deep: the obvious move is a trap, and the score comes from a setup
    that has to be planned for."""

    SPECTACLE = "spectacle"
    """Loud: one shot sets off an unusually long merge chain. Fun to
    watch whether or not it took any thought."""

    FAIR_HARD = "fair_hard"
    """Demanding but honest: a high ceiling that chance reliably misses,
    with a *narrow* random spread -- there is one good idea and you either
    find it or you don't."""

    LUCK = "luck"
    """Dice-driven: chance regularly reaches what planning reaches, and
    planning ahead adds little. Interesting mainly as something to filter
    out."""


def quantile(values: list[float], q: float) -> float:
    """Linearly interpolated `q`-quantile of `values` (`q` in [0, 1]).

    Written out rather than pulled from `statistics.quantiles`, which
    only returns evenly spaced cut points and would need re-deriving the
    index for an arbitrary `q` anyway.

    >>> quantile([1.0, 2.0, 3.0, 4.0], 0.5)
    2.5
    >>> quantile([1.0, 2.0, 3.0, 4.0], 0.0)
    1.0
    >>> quantile([5.0], 0.9)
    5.0
    """
    if not values:
        raise ValueError("quantile of an empty sequence is undefined")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


PAYOFF_CONC_MIN = 0.9
"""How concentrated an `AHA` level's payoff has to be. Not batch-relative:
this is a statement about the level's *shape* (nearly everything riding on
the last shot), which means the same thing regardless of the batch around
it. Top-gap levels sit at a median of ~0.95, ordinary ones near 0.67."""


def tag_batch(metrics: list[LevelMetrics]) -> dict[int, set[Archetype]]:
    """Tag every level in `metrics`, keyed by seed.

    Tags are independent: a level can carry several or none.

    Comparisons against a batch quantile are *strict* wherever ties would
    over-tag, which matters more than it looks: `max_combo` only ever
    takes a handful of integer values, so its 90th percentile is typically
    a value hundreds of levels share exactly, and a `>=` there would tag
    most of the batch as remarkable.

    The one exception is `LUCK`'s gap cutoff, which is inclusive. Gaps have
    a hard floor at zero (lookahead never loses to greedy at
    `shot_count=2`) and a quarter of every real batch sits exactly on it,
    so the 25th percentile *is* the floor -- a strict `<` there is not
    selective, it is unsatisfiable, and the tag would silently never fire.
    """
    if not metrics:
        return {}

    gaps = [float(m.depth_gap) for m in metrics]
    gap_high = quantile(gaps, 0.75)
    gap_low = quantile(gaps, 0.25)
    combo_high = quantile([float(m.max_combo) for m in metrics], 0.9)
    ceiling_high = quantile([float(m.lookahead_score) for m in metrics], 0.75)
    chance_low = quantile([m.random_mean for m in metrics], 0.25)
    spread_low = quantile([m.random_std for m in metrics], 0.5)

    tagged: dict[int, set[Archetype]] = {}
    for m in metrics:
        tags: set[Archetype] = set()
        # PAYOFF_CONC_MIN stays inclusive -- it is a statement about the
        # level's shape, not about its rank within this batch.
        if m.depth_gap > gap_high and m.payoff_conc is not None:
            if m.payoff_conc >= PAYOFF_CONC_MIN:
                tags.add(Archetype.AHA)
        if m.max_combo > combo_high:
            tags.add(Archetype.SPECTACLE)
        if (
            m.lookahead_score > ceiling_high
            and m.random_mean < chance_low
            and m.random_std < spread_low
        ):
            tags.add(Archetype.FAIR_HARD)
        if m.luck_share > 0 and m.depth_gap <= gap_low:
            tags.add(Archetype.LUCK)
        tagged[m.seed] = tags
    return tagged
