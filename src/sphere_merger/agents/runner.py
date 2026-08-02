"""Headless agent-vs-level runner: repeatedly ask an agent for a shot and
play it out until the round is won or lost."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import deal

from sphere_merger.agents.base import Agent
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState, play_shot, start_round


def disable_contracts_in_worker() -> None:
    """`deal.disable()` for one worker process.

    Pass as a `ProcessPoolExecutor`'s `initializer` when an agent's
    candidate simulations run in worker processes (see agents' `executor`
    param) -- `contracts_disabled()` only reaches the calling process, not
    workers spawned from it, since `deal`'s switch is per-process state.
    """
    deal.disable(warn=False)


@contextmanager
def contracts_disabled() -> Iterator[None]:
    """Turn off `deal` contracts for the duration of the block.

    Scoped to headless batch runs (this module) -- interactive play
    (`rendering.renderer`) never calls this, so contracts stay on as a
    correctness net there. `deal`'s switch is process-global (no native
    scoping), so parallel candidate evaluation in worker processes (see
    agents' `executor` param) needs its own `deal.disable()` via the
    executor's `initializer`; this only covers the calling process.
    """
    deal.disable(warn=False)
    try:
        yield
    finally:
        deal.enable(warn=False)


def play_round(level: LevelDefinition, agent: Agent) -> RoundState:
    """Play `level` from scratch, letting `agent` pick every shot.

    Returns the final `RoundState` once the round is won or the shot queue
    runs out.
    """
    state = start_round(level)
    with contracts_disabled():
        while not state.is_over:
            angle, speed = agent.choose_shot(state)
            play_shot(state, angle, speed)
    return state


def record_playthrough(
    level: LevelDefinition, agent: Agent
) -> tuple[list[tuple[float, float]], int]:
    """Play `level` with `agent`, recording each chosen (angle, speed) shot
    alongside the final score.

    For replaying a playthrough later (e.g. animated in a rendered grid)
    without needing the agent -- or its per-shot candidate simulation --
    live at render time.
    """
    state = start_round(level)
    shots: list[tuple[float, float]] = []
    with contracts_disabled():
        while not state.is_over:
            angle, speed = agent.choose_shot(state)
            shots.append((angle, speed))
            play_shot(state, angle, speed)
    return shots, state.score


def record_shots(level: LevelDefinition, agent: Agent) -> list[tuple[float, float]]:
    """Like `record_playthrough`, but for callers that only need the shots."""
    return record_playthrough(level, agent)[0]
