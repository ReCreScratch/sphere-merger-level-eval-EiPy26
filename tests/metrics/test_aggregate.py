import pytest

from sphere_merger.metrics.aggregate import (
    bin_count,
    describe,
    group_by_quartile,
    histogram,
    shared_histograms,
)


def test_bin_count_covers_the_largest_value() -> None:
    assert bin_count([0.0, 9.9], 10.0) == 1
    assert bin_count([0.0, 10.0], 10.0) == 2
    assert bin_count([], 10.0) == 1


def test_bin_count_rejects_a_nonpositive_width() -> None:
    with pytest.raises(ValueError):
        bin_count([1.0], 0.0)


def test_histogram_puts_values_in_half_open_bins() -> None:
    result = histogram([0.0, 9.9, 10.0], bin_width=10.0)

    assert result.counts == [2, 1]
    assert result.labels == ["0-9", "10-19"]


def test_histogram_keeps_outliers_in_the_last_bin_instead_of_dropping_them() -> None:
    # Explicit bin count smaller than the data needs -- happens whenever
    # several series share an axis and one runs past it.
    result = histogram([0.0, 95.0], bin_width=10.0, bins=2)

    assert sum(result.counts) == 2
    assert result.counts[-1] == 1


def test_histogram_labels_fractional_bins_without_collapsing_them() -> None:
    result = histogram([0.0, 0.5], bin_width=0.25, bins=3)

    assert result.labels == ["0.00-0.25", "0.25-0.50", "0.50-0.75"]


def test_shared_histograms_give_every_series_the_same_axis() -> None:
    # The random baseline tops out far below lookahead; binned separately
    # the two would be stretched across the same width and read as
    # comparable when they are not.
    result = shared_histograms(
        {"random": [0.0, 5.0], "lookahead": [0.0, 90.0]},
        bin_width=10.0,
    )

    assert len(result["random"].counts) == len(result["lookahead"].counts)
    assert sum(result["random"].counts) == 2


def test_describe_of_nothing_is_zeroes_rather_than_an_error() -> None:
    assert describe([]) == {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}


def test_group_by_quartile_splits_by_rank_not_by_value() -> None:
    # A floor-heavy key (most entries at zero) is exactly the real gap
    # distribution; splitting on value would leave three groups empty.
    keyed_on = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 90.0]
    values = [float(i) for i in range(8)]

    grouped = group_by_quartile(values, keyed_on)

    assert [len(g) for g in grouped.values()] == [2, 2, 2, 2]


def test_group_by_quartile_orders_groups_by_the_key() -> None:
    keyed_on = [4.0, 3.0, 2.0, 1.0]
    values = [40.0, 30.0, 20.0, 10.0]

    grouped = group_by_quartile(values, keyed_on)

    assert grouped["Q1"] == [10.0]
    assert grouped["Q4"] == [40.0]


def test_group_by_quartile_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        group_by_quartile([1.0, 2.0], [1.0])
