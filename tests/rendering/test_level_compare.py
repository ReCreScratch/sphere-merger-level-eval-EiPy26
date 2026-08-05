import pygame

from sphere_merger.game.level import LevelDefinition
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.level_compare import (
    CompareEntry,
    _build_cells,
    _clamp_scroll,
    _layout_sidebar_items,
    _sidebar_index_at,
    _wrap_text,
)

FIELD = Boundary(-6.0, 6.0, -6.0, 6.0)


def _level() -> LevelDefinition:
    return LevelDefinition(
        boundary=FIELD,
        initial_spheres=[],
        shot_queue=[0],
        spawn_position=Vector2(-5.0, -5.0),
        target_score=999,
    )


def _entry() -> CompareEntry:
    return CompareEntry(
        seed=42,
        reason="test entry",
        original_gap=10,
        shrunk_gap=6,
        spheres_removed=2,
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


def test_compare_entry_panels_cover_all_four_combinations_in_order() -> None:
    entry = _entry()

    labels = [label for label, _level, _shots in entry.panels()]
    assert labels == [
        "Original x Greedy",
        "Original x Lookahead",
        "Shrunk x Greedy",
        "Shrunk x Lookahead",
    ]

    shots = [shots for _label, _level, shots in entry.panels()]
    assert shots == [[(1.0, 2.0)], [(3.0, 4.0)], [(5.0, 6.0)], [(7.0, 8.0)]]

    levels = [level for _label, level, _shots in entry.panels()]
    assert levels == [
        entry.original_level,
        entry.original_level,
        entry.shrunk_level,
        entry.shrunk_level,
    ]


def test_build_cells_lays_out_a_2x2_grid_with_matching_labels() -> None:
    entry = _entry()

    cells = _build_cells(entry, area_size=(400.0, 400.0), area_offset=(100.0, 50.0))

    assert len(cells) == 4
    assert [cell.label for cell in cells] == [
        "Original x Greedy",
        "Original x Lookahead",
        "Shrunk x Greedy",
        "Shrunk x Lookahead",
    ]
    # Top-left cell's outline starts at the area's own offset; the grid
    # tiles outward from there rather than ignoring it.
    assert cells[0].outline.left >= 100
    assert cells[0].outline.top >= 50
    # Second column starts roughly a half-width further right than the first.
    assert cells[1].outline.left > cells[0].outline.left
    # Second row starts further down than the first.
    assert cells[2].outline.top > cells[0].outline.top


def test_wrap_text_breaks_long_reason_into_lines_that_fit(monkeypatch) -> None:
    pygame.font.init()
    font = pygame.font.Font(None, 15)

    text = "Groesste Gap-Zunahme: Greedy wird nach dem Shrink deutlich besser"
    lines = _wrap_text(text, font, max_width=120)

    assert len(lines) > 1
    for line in lines:
        assert font.size(line)[0] <= 120
    # No words lost or reordered across the wrap.
    assert " ".join(lines).split() == text.split()


def test_wrap_text_keeps_a_short_reason_on_one_line() -> None:
    pygame.font.init()
    font = pygame.font.Font(None, 15)

    lines = _wrap_text("kurzer Grund", font, max_width=500)

    assert lines == ["kurzer Grund"]


def _entry_with_reason(seed: int, reason: str) -> CompareEntry:
    entry = _entry()
    entry.seed = seed
    entry.reason = reason
    return entry


def test_layout_sidebar_items_grows_row_height_for_longer_reasons() -> None:
    pygame.font.init()
    small_font = pygame.font.Font(None, 15)
    entries = [
        _entry_with_reason(1, "kurz"),
        _entry_with_reason(
            2, "ein deutlich laengerer Grund, der garantiert in mehrere Zeilen umbricht"
        ),
    ]

    layouts = _layout_sidebar_items(entries, small_font)

    assert len(layouts) == 2
    short_rect, short_lines = layouts[0]
    long_rect, long_lines = layouts[1]
    assert len(long_lines) > len(short_lines)
    assert long_rect.height > short_rect.height
    # Rows stack directly beneath each other, no gap or overlap.
    assert long_rect.top == short_rect.bottom


def test_clamp_scroll_stays_within_zero_and_max_scroll() -> None:
    assert _clamp_scroll(-50, content_height=500, visible_height=300) == 0
    assert _clamp_scroll(50, content_height=500, visible_height=300) == 50
    assert _clamp_scroll(10_000, content_height=500, visible_height=300) == 200
    # Content shorter than the visible area -- nothing to scroll, ever.
    assert _clamp_scroll(10_000, content_height=200, visible_height=300) == 0


def test_sidebar_index_at_accounts_for_scroll_offset() -> None:
    pygame.font.init()
    small_font = pygame.font.Font(None, 15)
    entries = [_entry_with_reason(i, "kurz") for i in range(5)]
    layouts = _layout_sidebar_items(entries, small_font)
    row_height = layouts[0][0].height

    # Unscrolled, the row at y=5 is the first entry.
    assert _sidebar_index_at(layouts, (10, 5), scroll=0) == 0
    # Scrolled down by one row, the same screen position now hits the second entry.
    assert _sidebar_index_at(layouts, (10, 5), scroll=row_height) == 1
    # Far outside the list entirely.
    assert _sidebar_index_at(layouts, (10, 100_000), scroll=0) is None
