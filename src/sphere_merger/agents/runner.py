"""Headless agent-vs-level runner: repeatedly ask an agent for a shot and
play it out until the round is won or lost."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import deal

from sphere_merger.agents.base import Agent
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState, play_shot, start_round
from sphere_merger.physics.engine import enable_native_backend


def disable_contracts_in_worker() -> None:
    """`deal.disable()` for one worker process.

    Pass as a `ProcessPoolExecutor`'s `initializer` when an agent's
    candidate simulations run in worker processes (see agents' `executor`
    param) -- `contracts_disabled()` only reaches the calling process, not
    workers spawned from it, since `deal`'s switch is per-process state.
    """
    deal.disable(warn=False)


def prepare_native_batch_worker() -> None:
    """Combined `ProcessPoolExecutor` `initializer`: disables `deal`
    contracts and switches physics to the native Rust backend, both for
    one worker process.

    Use instead of `disable_contracts_in_worker` when a batch run should
    use `physics.engine.native_backend()` (see its docstring for why the
    switch is process-global and needs its own initializer per worker,
    same reasoning as `deal`'s).
    """
    disable_contracts_in_worker()
    enable_native_backend()


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
) -> tuple[list[tuple[float, float]], int, int]:
    """Play `level` with `agent`, recording each chosen (angle, speed) shot
    alongside the final score and the longest combo chain seen.

    For replaying a playthrough later (e.g. animated in a rendered grid)
    without needing the agent -- or its per-shot candidate simulation --
    live at render time.

    The combo chain is the number of merges triggered by a single shot
    (`play_shot`'s return value); the longest one across the whole
    playthrough is a proxy for "did any one shot set off a big cascade" --
    0 if no shot ever merged anything.
    """
    state = start_round(level)
    shots: list[tuple[float, float]] = []
    max_combo = 0
    with contracts_disabled():
        while not state.is_over:
            angle, speed = agent.choose_shot(state)
            shots.append((angle, speed))
            merged_levels = play_shot(state, angle, speed)
            max_combo = max(max_combo, len(merged_levels))
    return shots, state.score, max_combo


def record_shots(level: LevelDefinition, agent: Agent) -> list[tuple[float, float]]:
    """Like `record_playthrough`, but for callers that only need the shots."""
    return record_playthrough(level, agent)[0]
