from sphere_merger.game.level import LevelDefinition
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_browser import AgentMode, BrowserEntry, ViewMode, _categories

FIELD = Boundary(-5.0, 5.0, -5.0, 5.0)


def _level() -> LevelDefinition:
    return LevelDefinition(
        boundary=FIELD,
        initial_spheres=[],
        shot_queue=[0],
        spawn_position=Vector2(0.0, 0.0),
        target_score=999,
    )


def _entry(seed: int, gap_increase: int, spheres_removed: int) -> BrowserEntry:
    return BrowserEntry(
        seed=seed,
        original_gap=10,
        shrunk_gap=10 + gap_increase,
        spheres_removed=spheres_removed,
        gap_increase=gap_increase,
        original_level=_level(),
        shrunk_level=_level(),
        original_greedy_shots=[(1.0, 2.0)],
        original_lookahead_shots=[(3.0, 4.0)],
        shrunk_greedy_shots=[(5.0, 6.0)],
        shrunk_lookahead_shots=[(7.0, 8.0)],
        original_greedy_score=1,
        original_lookahead_score=2,
        shrunk_greedy_score=3,
        shrunk_lookahead_score=4,
    )


def test_browser_entry_level_and_shots_pick_the_right_combination() -> None:
    entry = _entry(seed=0, gap_increase=0, spheres_removed=0)

    assert entry.level(ViewMode.ORIGINAL) is entry.original_level
    assert entry.level(ViewMode.SHRUNK) is entry.shrunk_level
    assert entry.shots(ViewMode.ORIGINAL, AgentMode.GREEDY) == [(1.0, 2.0)]
    assert entry.shots(ViewMode.ORIGINAL, AgentMode.LOOKAHEAD) == [(3.0, 4.0)]
    assert entry.shots(ViewMode.SHRUNK, AgentMode.GREEDY) == [(5.0, 6.0)]
    assert entry.shots(ViewMode.SHRUNK, AgentMode.LOOKAHEAD) == [(7.0, 8.0)]


def test_categories_sort_by_gap_increase_max_shrink_and_least_changed() -> None:
    entries = [
        _entry(seed=1, gap_increase=10, spheres_removed=1),
        _entry(seed=2, gap_increase=30, spheres_removed=5),
        _entry(seed=3, gap_increase=-5, spheres_removed=0),
    ]

    categories = _categories(entries)
    names = [name for name, _ranked in categories]
    assert names == ["Gap-Zuwachs", "Max Shrink", "Kaum veraendert"]

    gap_increase_ranked = categories[0][1]
    assert [e.seed for e in gap_increase_ranked] == [2, 1, 3]

    max_shrink_ranked = categories[1][1]
    assert [e.seed for e in max_shrink_ranked] == [2, 1, 3]

    least_changed_ranked = categories[2][1]
    assert [e.seed for e in least_changed_ranked] == [3, 1, 2]
