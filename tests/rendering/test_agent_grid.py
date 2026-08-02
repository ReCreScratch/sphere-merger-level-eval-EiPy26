"""Regression test for a settle-timing bug in `_Cell.step_physics`:
`run_agent_grid`'s main loop stops calling `step_physics` for a cell as
soon as it reports `settled`, so a `settle()` that only fires on some
*later* call (the previous version's separate `else` branch) would never
actually run -- the still-nonzero, merely sub-threshold velocity from the
frame settling was first detected would carry into the next shot instead
of starting it from genuine rest. Caught by a user watching the grid
replay: residual motion changed the replayed trajectory (and therefore
the score) compared to the headless-recorded run, which never had this
bug (`game.round.play_shot` checks and settles atomically already).
"""

from sphere_merger.game.level import LevelDefinition
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.vector import Vector2
from sphere_merger.rendering.agent_grid import _Cell, compute_viewport, field_rect

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)


def _make_cell(shots: list[tuple[float, float]]) -> _Cell:
    level = LevelDefinition(
        boundary=FIELD,
        initial_spheres=[],
        shot_queue=[0] * len(shots),
        spawn_position=Vector2(-4.0, -4.0),
        target_score=999,
    )
    viewport = compute_viewport(level.boundary, (400.0, 400.0), (0.0, 0.0))
    outline = field_rect(level.boundary, viewport)
    return _Cell(label="test", level=level, shots=shots, viewport=viewport, outline=outline)


def test_step_physics_zeroes_velocity_the_moment_it_settles() -> None:
    cell = _make_cell([(30.0, 10.0)])
    cell.spawn_next_shot()

    steps = 0
    while not cell.settled:
        cell.step_physics(dt=1 / 50)
        steps += 1
        assert steps < 5000, "scenario never settled -- adjust the test shot"

    assert all(sphere.velocity == Vector2(0.0, 0.0) for sphere in cell.state.spheres)
