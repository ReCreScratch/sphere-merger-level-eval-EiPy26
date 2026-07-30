"""Sphere Merger package."""


def score_multiplier(merge_count: int) -> int:
    """Return the point multiplier for a given number of merges.

    >>> score_multiplier(0)
    1
    >>> score_multiplier(3)
    4
    """
    return merge_count + 1
