"""Hand-designed baseline levels for agent-loop testing (Meilenstein 5).

Each level targets a specific agent's strength rather than a generic
"difficulty": positions were tuned empirically against the real physics
simulation (hand-derived trajectories aren't reliable here -- friction,
restitution and merge momentum interact too much to predict by hand), then
verified by actually running `RandomAgent`/`GreedyAgent`/`LookaheadAgent`
against each level.

All three share the same field/spawn corner and shot speed
(`agents.base.DEFAULT_SPEED`, the fixed speed every agent sweeps at), so
only sphere placement, level, and shot queue distinguish them.
"""

from __future__ import annotations

from sphere_merger.game.level import LevelDefinition, radius_for_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.sphere import Sphere
from sphere_merger.physics.vector import Vector3

_FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0, z_min=0.0)
_SPAWN_MARGIN = 1.0
_SPAWN = Vector3(
    _FIELD.x_min + _SPAWN_MARGIN, _FIELD.y_min + _SPAWN_MARGIN, _FIELD.z_min + radius_for_level(0)
)


def _sphere(x: float, y: float, level: int) -> Sphere:
    return Sphere(
        Vector3(x, y, _SPAWN.z), Vector3(0.0, 0.0, 0.0), radius=radius_for_level(level), level=level
    )


# Five level-0 spheres spread every ~20 degrees across the reachable 0-90
# degree cone (each at that angle's natural at-rest point for a lone shot at
# DEFAULT_SPEED) -- close enough together that nearly any shot angle lands
# on one. Random, greedy and lookahead all reach the target reliably.
RANDOM_FRIENDLY = LevelDefinition(
    boundary=_FIELD,
    initial_spheres=[
        _sphere(-1.69, -4.42, 0),
        _sphere(-2.09, -3.32, 0),
        _sphere(-2.84, -2.43, 0),
        _sphere(-3.85, -1.84, 0),
        _sphere(-5.00, -1.64, 0),
    ],
    shot_queue=[0, 0],
    spawn_position=_SPAWN,
    target_score=4,
)

# Two isolated, non-interacting targets, one per queued shot's level -- each
# needs precise aim (unlike RANDOM_FRIENDLY) but taking the best available
# shot each turn is already globally optimal: greedy matches lookahead,
# random lags because it rarely aims precisely enough.
GREEDY_OPTIMAL = LevelDefinition(
    boundary=_FIELD,
    initial_spheres=[_sphere(-1.84, -3.85, 0), _sphere(-3.85, -1.84, 1)],
    shot_queue=[0, 1],
    spawn_position=_SPAWN,
    target_score=6,
)

# A level-0 sphere D and level-1 sphere E, placed touching. Shot 1 is a
# level-1 ball: hitting E directly scores +4 immediately (greedy's obvious
# choice) but consumes E, leaving D to merge alone for +2 on shot 2 (total
# 6). Missing on purpose (0 immediate) leaves D and E both in place, so
# shot 2 (level-0) can merge into D and immediately cascade into the
# untouched E for level 0->1->2 (+2, then +8 at combo_index 2 = 10 total).
# Only a 2-shot lookahead finds the higher total; greedy always takes the
# immediate +4.
LOOKAHEAD_TRAP = LevelDefinition(
    boundary=_FIELD,
    initial_spheres=[_sphere(-3.57, -2.80, 0), _sphere(-4.5, -3.0, 1)],
    shot_queue=[1, 0],
    spawn_position=_SPAWN,
    target_score=10,
)

BASELINE_LEVELS: dict[str, LevelDefinition] = {
    "random_friendly": RANDOM_FRIENDLY,
    "greedy_optimal": GREEDY_OPTIMAL,
    "lookahead_trap": LOOKAHEAD_TRAP,
}
