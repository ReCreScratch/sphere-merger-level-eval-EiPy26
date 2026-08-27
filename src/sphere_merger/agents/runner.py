"""Headless agent-vs-level runner: repeatedly ask an agent for a shot and
play it out until the round is won or lost."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

import deal

from sphere_merger.agents.base import Agent
from sphere_merger.game.level import LevelDefinition
from sphere_merger.game.round import play_shot, start_round, touched_sphere_indices
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
    """`ProcessPoolExecutor` `initializer` that disables `deal` contracts
    *and* switches to the native Rust backend for one worker.

    Use instead of `disable_contracts_in_worker` when a batch run should
    run natively. Both switches are per-process state, so both have to be
    set inside the worker rather than inherited from the parent.
    """
    disable_contracts_in_worker()
    enable_native_backend()


@contextmanager
def contracts_disabled() -> Iterator[None]:
    """Turn off `deal` contracts for the duration of the block.

    Scoped to headless batch runs, where contract checking is measurable
    overhead; interactive play never calls this and keeps contracts on as
    a correctness net. Only covers the calling process -- workers need
    `disable_contracts_in_worker` as their `initializer`.
    """
    deal.disable(warn=False)
    try:
        yield
    finally:
        deal.enable(warn=False)


@dataclass(frozen=True)
class ShotRecord:
    """One shot's outcome within a `record_playthrough` run.

    Holds the (angle, speed) fired, the cumulative score once the field
    settled, and which levels merged as a result. `play_shot` computes all
    of it anyway, and keeping it rather than collapsing to a final score
    means per-shot metrics -- score curve, merge cadence, dead shots --
    can be read off later without simulating again.

    `spheres_after` is the settled field left behind, as (x, y, level) per
    sphere. Velocity is dropped because the field is at rest by
    definition, and radius follows from the level, so storing either would
    store a constant. It makes mid-round positions analysable without
    replaying the agent, and lets a shorter round be reconstructed from a
    longer one: the state after shot 1 is the same on the same seed
    whatever the queue length, so a 2-shot answer costs one 1-ply sweep
    from here instead of a full rerun.
    """

    angle: float
    speed: float
    score_after: int
    merged_levels: list[int]
    spheres_after: list[tuple[float, float, int]]


def record_playthrough(level: LevelDefinition, agent: Agent) -> list[ShotRecord]:
    """Play `level` with `agent`, recording every shot's outcome.

    Lets a playthrough be replayed later (`shots_of`) without the agent or
    its expensive candidate search present at render time, and lets
    summary stats (`final_score`, `max_combo`) be read straight off the
    records instead of re-simulating.
    """
    state = start_round(level)
    records: list[ShotRecord] = []
    with contracts_disabled():
        while not state.is_over:
            angle, speed = agent.choose_shot(state)
            merged_levels = play_shot(state, angle, speed)
            records.append(
                ShotRecord(
                    angle,
                    speed,
                    state.score,
                    merged_levels,
                    [(s.position.x, s.position.y, s.level) for s in state.spheres],
                )
            )
    return records


def shots_of(records: list[ShotRecord]) -> list[tuple[float, float]]:
    """Just the (angle, speed) shots, for replaying without the metrics."""
    return [(record.angle, record.speed) for record in records]


def final_score(records: list[ShotRecord]) -> int:
    """The score after the last shot in `records` (0 if there were none)."""
    return records[-1].score_after if records else 0


def max_combo(records: list[ShotRecord]) -> int:
    """Longest single-shot merge chain in `records`, 0 if nothing merged.

    A proxy for whether any one shot set off a big cascade.
    """
    return max((len(record.merged_levels) for record in records), default=0)


Playthrough = tuple[list[tuple[float, float]], int, int]
"""shots, score, longest combo chain -- `shrink_to_used_spheres`'s summary
of one playthrough, thin enough to rebuild from a batch run's saved
scores instead of a live `list[ShotRecord]`."""


@dataclass(frozen=True)
class ShrinkResult:
    """`shrink_to_used_spheres`'s return value.

    Carries the iterated agents' playthroughs from before and after
    shrinking, which the shrink recorded internally anyway, so a caller
    wanting before/after scores need not re-simulate them.
    `fixed_playthroughs` is not echoed back -- the caller passed it in.
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

    `iterated_agents` are cheap ones (greedy) that get re-simulated fresh
    on every removal pass: dropping a sphere can change which shots they
    pick on the smaller field, so a touched set computed before the drop
    says nothing about after (see docs/level_shrinking.md).

    `fixed_playthroughs` are already-recorded results on the *unmodified*
    `level`, for agents too expensive to redo -- lookahead's 2-ply search
    above all. A caller working through a batch run already has them, and
    re-running the search would repeat its costliest part for nothing.
    Their touched set is carried forward across passes, remapped through
    the index shifts each drop causes. That trades the small chance of
    missing a sphere that only becomes droppable after several passes for
    a large speed win.

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
            records = record_playthrough(current, agent)
            shots = shots_of(records)
            touched |= touched_sphere_indices(current, shots)
            pass_playthroughs.append((shots, final_score(records), max_combo(records)))
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
