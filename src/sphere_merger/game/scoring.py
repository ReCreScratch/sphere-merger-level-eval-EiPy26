"""Points awarded per merge.

A plain function rather than logic inside the round loop, so the formula
can be swapped via `play_shot`'s `score_fn` parameter.
"""

from __future__ import annotations

from collections.abc import Callable

MergeScoreFn = Callable[[int, int], int]


def default_merge_score(new_level: int, combo_index: int) -> int:
    """Points for one merge resulting in `new_level`.

    Exponential in the level, linear in the combo, so chaining merges from
    a single shot pays off. `combo_index` is 1-based.

    >>> default_merge_score(new_level=3, combo_index=1)
    8
    >>> default_merge_score(new_level=3, combo_index=2)
    16
    """
    return 2**new_level * combo_index
