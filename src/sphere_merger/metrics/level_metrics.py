"""Per-level metrics derived from one batch run's saved records (see
`scripts/agent_batch_timing.py` and docs/data_schema.md).

Pure derivation, no simulation: every number here is read off the scores
and per-shot data a batch run already wrote out. The point is to turn
"what did the agents score" into "what kind of level is this for a
human" -- see docs/interesting_levels.md for what each dimension is
supposed to capture and where the approach stops working.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


def payoff_concentration(cumulative_scores: list[int]) -> float | None:
    """Share of the final score earned by the *last* shot alone.

    `cumulative_scores` is a playthrough's running score after each shot
    (`*_score_per_shot` in the saved records). 1.0 means every point came
    from the final shot -- a pure setup-then-payoff level, the shape
    greedy reliably walks into by grabbing points early instead. `None`
    when nothing was scored at all, since "which shot earned it" has no
    answer then.

    >>> payoff_concentration([0, 40])
    1.0
    >>> payoff_concentration([20, 40])
    0.5
    >>> payoff_concentration([0, 0]) is None
    True
    """
    if not cumulative_scores or cumulative_scores[-1] == 0:
        return None
    previous = cumulative_scores[-2] if len(cumulative_scores) > 1 else 0
    return (cumulative_scores[-1] - previous) / cumulative_scores[-1]


def skill_effect(informed_score: int, random_scores: list[int]) -> float | None:
    """How far the informed score stands out from chance, in standard
    deviations of the random baseline.

    An effect size (Cohen's d against a one-sample baseline): the raw
    distance `informed - mean(random)` says nothing on its own, since a
    level whose random outcomes swing wildly can produce that distance by
    luck alone. Dividing by the spread is what separates "skill decides
    this level" from "the dice do". `None` if the baseline has no spread
    (every sample identical), where the ratio is undefined.

    >>> round(skill_effect(50, [10, 20, 30]), 2)
    3.67
    >>> skill_effect(50, [10, 10, 10]) is None
    True
    """
    if len(random_scores) < 2:
        return None
    spread = statistics.pstdev(random_scores)
    if spread == 0:
        return None
    return (informed_score - statistics.mean(random_scores)) / spread


def luck_reach(informed_score: int, random_scores: list[int]) -> float:
    """Share of random samples that matched or beat `informed_score`.

    0.0 means chance never stumbled into the informed result; anything
    above that is a level where flailing can pay off as well as planning,
    which dilutes whatever the other metrics say about skill.

    >>> luck_reach(30, [10, 30, 40, 20])
    0.5
    >>> luck_reach(30, [10, 20])
    0.0
    """
    if not random_scores:
        return 0.0
    return sum(1 for score in random_scores if score >= informed_score) / len(random_scores)


@dataclass(frozen=True)
class LevelMetrics:
    """One level's derived metrics, across the dimensions that plausibly
    make a level interesting to a human (see module docstring).

    Attributes:
        seed: The level's seed -- enough to rebuild it, given the run's `meta`.
        depth_gap: `lookahead_score - greedy_score`, signed rather than
            absolute: at `shot_count=2` lookahead's 2-ply search is
            effectively optimal, so this is what the obvious move gives up
            against the best one, and it is never negative in practice
            (checked: 0 of 2000 levels).
        payoff_conc: See `payoff_concentration`, for lookahead's playthrough.
        random_mean: Mean of the random baseline samples.
        random_std: Population standard deviation of those samples.
        skill_gain: See `skill_effect`, lookahead against the baseline.
        luck_share: See `luck_reach`, lookahead against the baseline.
        max_combo: Longest single-shot merge chain lookahead set off.
        greedy_score: Final score of the greedy playthrough.
        lookahead_score: Final score of the lookahead playthrough.
    """

    seed: int
    depth_gap: int
    payoff_conc: float | None
    random_mean: float
    random_std: float
    skill_gain: float | None
    luck_share: float
    max_combo: int
    greedy_score: int
    lookahead_score: int

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> LevelMetrics:
        """Derive metrics from one saved `levels[]` entry.

        Expects the schema `scripts/agent_batch_timing.py` writes (see
        docs/data_schema.md) -- notably `random_scores` and
        `lookahead_score_per_shot`, both added after the first batch runs,
        so older files will not work here.
        """
        random_scores = record["random_scores"]
        lookahead_score = record["lookahead_score"]
        return cls(
            seed=record["seed"],
            depth_gap=lookahead_score - record["greedy_score"],
            payoff_conc=payoff_concentration(record["lookahead_score_per_shot"]),
            random_mean=statistics.mean(random_scores),
            random_std=statistics.pstdev(random_scores),
            skill_gain=skill_effect(lookahead_score, random_scores),
            luck_share=luck_reach(lookahead_score, random_scores),
            max_combo=record["lookahead_max_combo"],
            greedy_score=record["greedy_score"],
            lookahead_score=lookahead_score,
        )
