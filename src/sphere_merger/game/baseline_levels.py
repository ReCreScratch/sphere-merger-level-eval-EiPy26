"""Placeholder baseline levels for early agent-loop testing.

Reuses `generate_random_level` with fixed seeds instead of hand-designed
placements/solutions -- fast to produce, still fully reproducible, but
`target_score` is only a rough guess, not a derived reachable value. This
is a stand-in for the real baseline levels (Meilenstein 5: hand-designed,
with a known solution and target score), to be replaced later.
"""

from __future__ import annotations

from sphere_merger.game.level import LevelDefinition, generate_random_level, radius_for_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector3

_FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0, z_min=0.0)
_SPAWN_MARGIN = 1.0
_SPAWN = Vector3(
    _FIELD.x_min + _SPAWN_MARGIN, _FIELD.y_min + _SPAWN_MARGIN, _FIELD.z_min + radius_for_level(0)
)

BASELINE_EASY = generate_random_level(
    seed=1,
    boundary=_FIELD,
    spawn_position=_SPAWN,
    target_score=30,
    initial_sphere_count=4,
    shot_count=8,
    level_range=(0, 1),
)

BASELINE_MEDIUM = generate_random_level(
    seed=2,
    boundary=_FIELD,
    spawn_position=_SPAWN,
    target_score=60,
    initial_sphere_count=6,
    shot_count=10,
    level_range=(0, 2),
)

BASELINE_HARD = generate_random_level(
    seed=3,
    boundary=_FIELD,
    spawn_position=_SPAWN,
    target_score=100,
    initial_sphere_count=8,
    shot_count=12,
    level_range=(0, 2),
)

BASELINE_LEVELS: dict[str, LevelDefinition] = {
    "easy": BASELINE_EASY,
    "medium": BASELINE_MEDIUM,
    "hard": BASELINE_HARD,
}
