"""Binning and batch-level summaries, for turning a thousand per-level
records into the handful of numbers a chart can show.

Kept separate from `level_metrics` (what one level is) and `archetypes`
(what kind of level it is): this module only ever reduces a collection to
distributions and averages, and knows nothing about what the values mean.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Histogram:
    """Counts per bin, with a printable label per bin.

    Attributes:
        labels: One label per bin, e.g. `"0-9"`, in bin order.
        counts: How many values fell into each bin.
    """

    labels: list[str]
    counts: list[int]


def bin_count(values: list[float], bin_width: float) -> int:
    """How many bins of `bin_width` are needed to cover `values` from 0.

    >>> bin_count([0.0, 9.0], 10.0)
    1
    >>> bin_count([0.0, 10.0], 10.0)
    2
    >>> bin_count([], 10.0)
    1
    """
    if bin_width <= 0:
        raise ValueError("bin_width must be positive")
    if not values:
        return 1
    return max(1, math.floor(max(values) / bin_width) + 1)


def histogram(values: list[float], bin_width: float, bins: int | None = None) -> Histogram:
    """Bin `values` into `bins` half-open intervals of `bin_width` from 0.

    Values at or above the last bin's start all land in it, so a caller
    binning several series against a shared axis (see
    `shared_histograms`) never loses an outlier off the end.

    >>> histogram([0.0, 5.0, 12.0], bin_width=10.0).counts
    [2, 1]
    >>> histogram([0.0, 5.0, 12.0], bin_width=10.0).labels
    ['0-9', '10-19']
    """
    if bins is None:
        bins = bin_count(values, bin_width)
    counts = [0] * bins
    for value in values:
        index = min(int(value / bin_width), bins - 1)
        counts[max(index, 0)] += 1

    labels = []
    for i in range(bins):
        low = i * bin_width
        high = low + bin_width
        if bin_width >= 1:
            labels.append(f"{low:.0f}-{high - 1:.0f}")
        else:
            labels.append(f"{low:.2f}-{high:.2f}")
    return Histogram(labels=labels, counts=counts)


def shared_histograms(series: dict[str, list[float]], bin_width: float) -> dict[str, Histogram]:
    """Bin several series against one shared axis, so their bars line up.

    Binning each series on its own axis would make them visually
    comparable only by accident -- the random baseline tops out far below
    lookahead, and would otherwise be stretched across the same width.
    """
    widest = max((bin_count(values, bin_width) for values in series.values()), default=1)
    return {name: histogram(values, bin_width, bins=widest) for name, values in series.items()}


def describe(values: list[float]) -> dict[str, float]:
    """Mean, median, min and max of `values` (all 0.0 when empty)."""
    if not values:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def group_by_quartile(
    values: list[float], keyed_on: list[float], labels: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4")
) -> dict[str, list[float]]:
    """Split `values` into four groups by their partner's rank in `keyed_on`.

    Both lists are parallel (one entry per level). Used to show how one
    metric moves across another's range -- e.g. payoff concentration
    across gap quartiles, which is what makes the gap mean something
    concrete rather than just "these two agents differ here".

    Splits by rank, not by value, so a distribution with a heavy floor
    (gaps pile up at zero) still yields four non-empty groups instead of
    three empty ones and one holding everything.
    """
    if len(values) != len(keyed_on):
        raise ValueError("values and keyed_on must be parallel")
    if not values:
        return {label: [] for label in labels}

    order = sorted(range(len(values)), key=lambda i: keyed_on[i])
    grouped: dict[str, list[float]] = {label: [] for label in labels}
    per_group = len(order) / len(labels)
    for rank, index in enumerate(order):
        label = labels[min(int(rank / per_group), len(labels) - 1)]
        grouped[label].append(values[index])
    return grouped
