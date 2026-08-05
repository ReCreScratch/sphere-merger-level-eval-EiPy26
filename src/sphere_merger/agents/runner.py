"""Headless agent-vs-level runner: repeatedly ask an agent for a shot and
play it out until the round is won or lost."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

import deal

from sphere_merger.agents.base import Agent
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import RoundState, play_shot, start_round, touched_sphere_indices
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


Playthrough = tuple[list[tuple[float, float]], int, int]
"""One `record_playthrough` result: shots, score, longest combo chain."""


@dataclass(frozen=True)
class ShrinkResult:
    """`shrink_to_used_spheres`'s return value.

    Carries the iterated agents' playthroughs the shrink already recorded
    internally (`original_iterated_playthroughs`/`final_iterated_playthroughs`,
    before vs. after shrinking) so callers wanting before/after scores don't
    need to re-simulate them. `fixed_playthroughs` isn't echoed back here --
    the caller already had those (see `shrink_to_used_spheres`).
    """

    level: LevelDefinition
    original_iterated_playthroughs: list[Playthrough]
    final_iterated_playthroughs: list[Playthrough]


def shrink_to_used_spheres(
    level: LevelDefinition,
    iterated_agents: list[Agent],
    fixed_playthroughs: list[Playthrough],
) -> ShrinkResult:
    """Iteratively drop initial spheres that none of `iterated_agents` ever
    touch, nor any of `fixed_playthroughs`.

    `iterated_agents` are cheap agents (e.g. greedy) that get re-simulated
    fresh every removal pass, since dropping a sphere can change which
    shots they pick on the smaller field -- a touched-set computed before
    the drop can't be trusted for what comes after (see
    docs/level_shrinking.md). `fixed_playthroughs` are already-recorded
    `record_playthrough` results *on `level`, unmodified* for expensive
    agents (e.g. lookahead's near-exhaustive 2-ply search) -- passed in
    rather than re-simulated here, since a caller processing many levels
    from a prior batch run (see `agent_batch_timing.py`) already has these
    shots and re-running the search again would repeat its most expensive
    part for nothing. Their touched set is carried forward across removal
    passes (remapped through the index shifts each drop causes) instead of
    being recomputed every time, trading the small risk of missing a
    sphere that only becomes newly safe to drop after several rounds of
    `iterated_agents`-driven shrinking for a large speed win.

    Keeps going until a pass finds nothing left to drop. Doesn't check
    whether the score gap changed at all: a shrinking gap here just means
    the level was easier than its original score suggested, not a failure
    -- and an agent finding a genuinely different, better strategy on the
    smaller field is an accepted side effect, never searched for.
    """
    current = level
    fixed_touched: set[int] = set()
    for shots, _score, _combo in fixed_playthroughs:
        fixed_touched |= touched_sphere_indices(level, shots)

    original_iterated_playthroughs: list[Playthrough] | None = None
    while True:
        touched = set(fixed_touched)
        pass_playthroughs: list[Playthrough] = []
        for agent in iterated_agents:
            shots, score, combo = record_playthrough(current, agent)
            touched |= touched_sphere_indices(current, shots)
            pass_playthroughs.append((shots, score, combo))
        if original_iterated_playthroughs is None:
            original_iterated_playthroughs = pass_playthroughs

        untouched = set(range(len(current.initial_spheres))) - touched
        if not untouched:
            return ShrinkResult(
                level=current,
                original_iterated_playthroughs=original_iterated_playthroughs,
                final_iterated_playthroughs=pass_playthroughs,
            )

        kept_indices = [i for i in range(len(current.initial_spheres)) if i not in untouched]
        spheres = [current.initial_spheres[i] for i in kept_indices]
        fixed_touched = {
            new_index
            for new_index, old_index in enumerate(kept_indices)
            if old_index in fixed_touched
        }
        current = replace(current, initial_spheres=spheres)
