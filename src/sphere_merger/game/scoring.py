"""Points awarded per merge.

Kept as a plain, swappable function (not hard-wired into the round loop)
so the formula can change without touching `game/round.py` -- pass a
different one to `play_shot`'s `score_fn` parameter.
"""

from __future__ import annotations

from collections.abc import Callable

MergeScoreFn = Callable[[int, int], int]


def default_merge_score(new_level: int, combo_index: int) -> int:
    """Points for one merge resulting in `new_level`.

    Exponential in level (rewards high-level merges strongly) times a
    linear combo multiplier (rewards chaining several merges from a single
    shot). `combo_index` is 1-based: 1 for the first merge in a shot, 2 for
    the second, and so on.

    >>> default_merge_score(new_level=3, combo_index=1)
    8
    >>> default_merge_score(new_level=3, combo_index=2)
    16
    """
    return 2**new_level * combo_index
