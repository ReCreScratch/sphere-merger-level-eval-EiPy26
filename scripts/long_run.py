"""Long unattended batch run across several regimes at once, abortable at
any moment without losing what it has already computed.

Four differences to `agent_batch_timing.py`, all of them consequences of
running for hours rather than minutes:

**One worker task is one whole level, not one candidate angle.** An
earlier version of this script fanned a single level's candidate sweeps
(greedy's, lookahead's, each random sample's) out across the whole pool
and synchronised the main process after every shot -- measured at only
~44-53% CPU utilisation, because every shot, every agent phase and every
shrink pass was its own barrier (a 4-shot level has a dozen or more of
these), and each one leaves the *entire* pool idle waiting for the
slowest straggler before the next phase can even be dispatched.
`play_level_task` instead computes an entire level -- baseline, greedy,
lookahead, shrink -- sequentially inside one worker process with no
executor of its own (`GreedyAgent`/`LookaheadAgent` already support this:
no executor means a sequential sweep). Parallelism now comes from many
*different* levels running in different workers at once, via
`run_workload`'s rolling window of in-flight level tasks, kept full by
submitting a replacement the instant one finishes. Measured directly
against the barrier-per-shot design on the same regimes: +43% throughput
on a cheap 2-shot regime, +29% on an expensive 4-shot one -- confirming
this is a real win, not just busier-looking cores (an earlier estimate
that guessed the 4-shot regime wouldn't benefit was wrong; it had
extrapolated the old design's cost from a different regime instead of
measuring it, and undercounted how many synchronisation barriers a
longer round accumulates).

**Interleaved, not sequential.** The regimes take turns in rounds of a few
hundred levels each instead of running one to completion before the next
starts. A run that is stopped when its operator gets home would otherwise
leave the later regimes with nothing at all, and regimes that cannot be
compared to each other are worth much less than a smaller set that can.
Within one sphere count the shot counts get 45/30/25 percent of the round
(`SHOT_SPLIT`), so the shorter, cheaper rounds accumulate the most levels.
A round's items are shuffled across regimes before being fed into the
rolling window, so an expensive 4-shot level never blocks a worker that
could otherwise be finishing several cheap 2-shot ones.

**Checkpointed, not held in memory.** Every finished level is appended to
its regime's checkpoint (`game.checkpoint`) the moment it is done. Peak
memory is therefore flat no matter how long the run goes, and an abort
costs at most the handful of levels still in flight in the rolling
window (bounded by the worker count) rather than the whole round.

**It expects to be interrupted.** Ctrl-C, or creating the file
`data/STOP`, stops submitting new level tasks, lets the ones already in
flight finish, finalises every regime's checkpoint into its normal data
file, and exits. A crashed worker is caught, the pool rebuilt, and every
level that was in flight on the dead pool is re-queued with a fresh seed
(the seed it was given is simply burned rather than tracked for retry --
simpler, and one wasted seed out of a billion costs nothing). Windows is
asked to stay awake for the duration -- an unattended run is lost just as
thoroughly to a sleeping laptop as to a crash.

Shrinking runs per level too, right alongside the level it belongs to, so
the shrink dataset is never behind the batch one and both stay consistent
at whatever point the run is stopped.

Seeds are drawn fresh per level from a per-regime pool, and already-used
seeds are tracked so a long run never plays the same level twice within a
regime.

Usage: `python scripts/long_run.py [regime ...]` -- without arguments it
runs the nine regimes of `LONG_RUN_GRID`.
"""

from __future__ import annotations

import ctypes
import os
import random
import signal
import sys
import time
from concurrent.futures import BrokenExecutor, Future, ProcessPoolExecutor, wait
from datetime import date, datetime
from pathlib import Path
from types import FrameType

from sphere_merger.agents.greedy_agent import GreedyAgent
from sphere_merger.agents.lookahead_agent import LookaheadAgent
from sphere_merger.agents.random_agent import RandomAgent
from sphere_merger.agents.runner import (
    ShotRecord,
    final_score,
    max_combo,
    prepare_native_batch_worker,
    record_playthrough,
    shots_of,
    shrink_to_used_spheres,
)
from sphere_merger.game.checkpoint import Checkpoint
from sphere_merger.game.interesting_levels import RUNS, RunConfig, select_runs
from sphere_merger.game.level import LevelDefinition, generate_random_level
from sphere_merger.physics.boundary import Boundary
from sphere_merger.physics.engine import native_backend
from sphere_merger.physics.vector import Vector2

FIELD = Boundary(x_min=-6.0, x_max=6.0, y_min=-6.0, y_max=6.0)
SPAWN_MARGIN = 1.0
SPAWN = Vector2(FIELD.x_min + SPAWN_MARGIN, FIELD.y_min + SPAWN_MARGIN)
SHOT_SPEED = 25.0
RANDOM_SAMPLE_COUNT = 20
TARGET_SCORE = 999
LEVEL_RANGE = (0, 2)

SPHERE_COUNTS = (5, 8, 10)
LEVELS_PER_SPHERE_COUNT = 300
SHOT_SPLIT = {2: 0.45, 3: 0.30, 4: 0.25}
"""Share of each sphere count's round per shot count. Weighted towards the
shorter rounds deliberately: they are the cheapest levels *and* the
baseline the longer ones are read against, so they should be the least
noisy of the three."""

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STOP_FILE = DATA_DIR / "STOP"
LOG_PATH = DATA_DIR / "long_run.log"

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

LONG_RUN_GRID = tuple(
    run for run in RUNS if run.sphere_count in SPHERE_COUNTS and run.shot_count in SHOT_SPLIT
)

_stop_requested = False


def _request_stop(signum: int, frame: FrameType | None) -> None:
    """Ask the run to wind down at the next level boundary."""
    global _stop_requested
    _stop_requested = True
    log("Abbruch angefordert -- beende das laufende Level und finalisiere.")


def should_stop() -> bool:
    """Whether the run has been asked to stop, by signal or by STOP file."""
    return _stop_requested or STOP_FILE.exists()


def log(message: str) -> None:
    """Print `message` with a timestamp and append it to the run log."""
    stamped = f"[{datetime.now():%H:%M:%S}] {message}"
    print(stamped, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(stamped + "\n")


def keep_awake(enable: bool) -> None:
    """Ask Windows not to sleep while the run is going (no-op elsewhere).

    A multi-hour unattended run is lost to a sleeping machine as surely as
    to a crash, and unlike a power-plan change this needs no cleanup by
    the operator -- the request dies with the process.
    """
    if sys.platform != "win32":
        return
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enable else 0)
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


MAX_WORKERS = os.cpu_count() or 4
"""Worker count for the pool, and the rolling window's target number of
in-flight level tasks (see `run_workload`) -- one task per worker keeps
every worker continuously busy without overprovisioning the queue."""


def round_size(run: RunConfig) -> int:
    """How many levels of `run` one round plays."""
    return max(1, round(LEVELS_PER_SPHERE_COUNT * SHOT_SPLIT[run.shot_count]))


def build_level(seed: int, run: RunConfig) -> LevelDefinition:
    """The level `seed` denotes under `run`'s parameters."""
    return generate_random_level(
        seed=seed,
        boundary=FIELD,
        spawn_position=SPAWN,
        target_score=TARGET_SCORE,
        initial_sphere_count=run.sphere_count,
        shot_count=run.shot_count,
        level_range=LEVEL_RANGE,
    )


def meta_for(run: RunConfig) -> dict[str, object]:
    """The shared generation parameters stored once per regime."""
    return {
        "source_script": "long_run.py[rust]",
        "field": {
            "x_min": FIELD.x_min,
            "x_max": FIELD.x_max,
            "y_min": FIELD.y_min,
            "y_max": FIELD.y_max,
        },
        "spawn_margin": SPAWN_MARGIN,
        "target_score": TARGET_SCORE,
        "initial_sphere_count": run.sphere_count,
        "shot_count": run.shot_count,
        "level_range": list(LEVEL_RANGE),
        "shot_speed": SHOT_SPEED,
        "random_sample_count": RANDOM_SAMPLE_COUNT,
        "found_at": date.today().isoformat(),
    }


def _states(records: list[ShotRecord]) -> list[list[list[float]]]:
    """Each shot's settled field, rounded to millimetres.

    Three decimals is well below the physics' own resolution and roughly
    halves what the positions cost on disk -- they are the largest part of
    a record now.
    """
    return [
        [[round(x, 3), round(y, 3), level] for x, y, level in record.spheres_after]
        for record in records
    ]


def level_record(
    seed: int,
    random_scores: list[int],
    random_first: list[ShotRecord],
    greedy: list[ShotRecord],
    lookahead: list[ShotRecord],
) -> dict[str, object]:
    """One level as it is stored -- see docs/data_schema.md."""
    return {
        "seed": seed,
        "random_scores": random_scores,
        "random0_shots": shots_of(random_first),
        "random0_states": _states(random_first),
        "greedy_score": final_score(greedy),
        "greedy_shots": shots_of(greedy),
        "greedy_score_per_shot": [r.score_after for r in greedy],
        "greedy_merges_per_shot": [r.merged_levels for r in greedy],
        "greedy_states": _states(greedy),
        "lookahead_score": final_score(lookahead),
        "lookahead_shots": shots_of(lookahead),
        "lookahead_score_per_shot": [r.score_after for r in lookahead],
        "lookahead_merges_per_shot": [r.merged_levels for r in lookahead],
        "lookahead_states": _states(lookahead),
        "gap": final_score(lookahead) - final_score(greedy),
        "lookahead_max_combo": max_combo(lookahead),
    }


def shrink_record(
    seed: int,
    level: LevelDefinition,
    greedy_agent: GreedyAgent,
    lookahead: list[ShotRecord],
) -> dict[str, object]:
    """One level's shrink result, reusing lookahead's recorded playthrough
    instead of re-running its 2-ply search (see shrink_top_levels.py)."""
    result = shrink_to_used_spheres(
        level,
        iterated_agents=[greedy_agent],
        fixed_playthroughs=[(shots_of(lookahead), final_score(lookahead), max_combo(lookahead))],
    )
    kept_ids = {id(sphere) for sphere in result.level.initial_spheres}
    kept = [i for i, sphere in enumerate(level.initial_spheres) if id(sphere) in kept_ids]

    original_greedy_shots, original_greedy_score, _ = result.original_iterated_playthroughs[0]
    shrunk_greedy_shots, shrunk_greedy_score, _ = result.final_iterated_playthroughs[0]
    lookahead_score = final_score(lookahead)

    return {
        "seed": seed,
        "original_sphere_count": len(level.initial_spheres),
        "shrunk_sphere_count": len(result.level.initial_spheres),
        "spheres_removed": len(level.initial_spheres) - len(result.level.initial_spheres),
        "kept_sphere_indices": kept,
        "original_gap": abs(original_greedy_score - lookahead_score),
        "shrunk_gap": abs(shrunk_greedy_score - lookahead_score),
        "gap_increase": abs(shrunk_greedy_score - lookahead_score)
        - abs(original_greedy_score - lookahead_score),
        "original_greedy_score": original_greedy_score,
        "original_lookahead_score": lookahead_score,
        "shrunk_greedy_score": shrunk_greedy_score,
        "shrunk_lookahead_score": lookahead_score,
        "original_greedy_shots": original_greedy_shots,
        "original_lookahead_shots": shots_of(lookahead),
        "shrunk_greedy_shots": shrunk_greedy_shots,
        "shrunk_lookahead_shots": shots_of(lookahead),
    }


class Pool:
    """The worker pool, rebuilt in place when a worker dies.

    A `BrokenProcessPool` in the middle of a multi-hour unattended run
    would otherwise end it -- and the whole point of this script is that
    it does not end early. `run_workload` re-queues whatever was in
    flight on the dead pool once this has been called.
    """

    def __init__(self) -> None:
        """Start the first pool, sized to `MAX_WORKERS`."""
        self.executor = ProcessPoolExecutor(
            max_workers=MAX_WORKERS, initializer=prepare_native_batch_worker
        )
        self.restarts = 0

    def restart(self) -> None:
        """Replace a broken pool with a fresh one."""
        self.restarts += 1
        log(f"Worker-Pool gestorben -- Neustart Nr. {self.restarts}")
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001 -- a broken pool may fail any way it likes
            pass
        self.executor = ProcessPoolExecutor(
            max_workers=MAX_WORKERS, initializer=prepare_native_batch_worker
        )

    def shutdown(self) -> None:
        """Shut the current pool down."""
        self.executor.shutdown(wait=True)


def play_level_task(seed: int, run: RunConfig) -> tuple[dict[str, object], dict[str, object]]:
    """Compute one whole level -- baseline, greedy, lookahead, shrink --
    entirely inside the calling process. This is the unit of work
    submitted to the pool by `run_workload`: one task, one level, no
    executor of its own.

    `GreedyAgent`/`LookaheadAgent` fall back to a sequential candidate
    sweep when given no executor, which is exactly what running inside an
    already-parallel worker process needs -- handing them this process's
    own (nonexistent) pool would either do nothing or deadlock. Simulating
    all three agents plus the shrink pass here, in one function, means the
    entire level's compute happens without a single round-trip back to the
    main process until it is completely done.
    """
    level = build_level(seed, run)
    greedy_agent = GreedyAgent(speed=SHOT_SPEED)
    lookahead_agent = LookaheadAgent(speed=SHOT_SPEED)

    random_scores: list[int] = []
    random_first: list[ShotRecord] = []
    for i in range(RANDOM_SAMPLE_COUNT):
        sample = RandomAgent(seed=seed * RANDOM_SAMPLE_COUNT + i, speed=SHOT_SPEED)
        records = record_playthrough(level, sample)
        random_scores.append(final_score(records))
        if i == 0:
            random_first = records

    greedy = record_playthrough(level, greedy_agent)
    lookahead = record_playthrough(level, lookahead_agent)

    return (
        level_record(seed, random_scores, random_first, greedy, lookahead),
        shrink_record(seed, level, greedy_agent, lookahead),
    )


def run_workload(
    items: list[RunConfig],
    pool: Pool,
    batch: dict[str, Checkpoint],
    shrunk: dict[str, Checkpoint],
    used: dict[str, set[int]],
    done: dict[str, int],
    rng: random.Random,
) -> dict[str, int]:
    """Play one level per entry in `items` (already one entry per desired
    level, e.g. a regime repeated `round_size` times), through a rolling
    window of `MAX_WORKERS` in-flight level tasks.

    Stops submitting new tasks once `should_stop()` is true, but always
    drains whatever is already in flight rather than cancelling it -- an
    abort loses at most `MAX_WORKERS` levels' worth of work in progress,
    not the level a synchronous loop would have been blocked on anyway.

    A dead worker breaks the whole pool at once (`BrokenExecutor` on every
    future submitted to it, in flight or not); this rebuilds the pool and
    re-queues every item that was in flight, each with a freshly drawn
    seed -- the seed it had been given is simply abandoned rather than
    tracked for exact retry, which would need undoing its `used` entry
    only to redo it identically a moment later.

    Returns how many levels of each regime were completed.
    """
    played: dict[str, int] = {}
    pending: dict[Future[tuple[dict[str, object], dict[str, object]]], RunConfig] = {}
    queue = list(items)

    def submit_one() -> bool:
        if not queue or should_stop():
            return False
        run = queue.pop()
        seed = rng.randrange(1_000_000_000)
        while seed in used[run.name]:
            seed = rng.randrange(1_000_000_000)
        used[run.name].add(seed)
        pending[pool.executor.submit(play_level_task, seed, run)] = run
        return True

    for _ in range(MAX_WORKERS):
        submit_one()

    while pending:
        completed, _ = wait(pending, return_when="FIRST_COMPLETED")
        broken = False
        for future in completed:
            run = pending.pop(future)
            try:
                record, shrink = future.result()
            except BrokenExecutor:
                broken = True
                queue.append(run)
                continue
            batch[run.name].append(record)
            shrunk[run.name].append(shrink)
            done[run.name] += 1
            played[run.name] = played.get(run.name, 0) + 1

        if broken:
            for future, run in pending.items():
                future.cancel()
                queue.append(run)
            pending.clear()
            pool.restart()

        while len(pending) < MAX_WORKERS and submit_one():
            pass

    return played


def main(runs: tuple[RunConfig, ...], resume: bool = False) -> None:
    """Play rounds across `runs` until asked to stop, then finalise.

    The whole loop runs inside `native_backend()`: the workers get the
    native backend from their initializer, but the main process simulates
    too (every random sample, and each agent's chosen shot), and without
    this it would quietly do that in the slow Python backend.
    """
    batch = {run.name: Checkpoint(f"{run.name}_batch") for run in runs}
    shrunk = {run.name: Checkpoint(f"{run.name}_shrink") for run in runs}
    used: dict[str, set[int]] = {run.name: set() for run in runs}
    done: dict[str, int] = {run.name: 0 for run in runs}

    for run in runs:
        batch[run.name].start(meta_for(run), resume=resume)
        shrunk[run.name].start(
            {**meta_for(run), "source_script": "long_run.py[shrink]"}, resume=resume
        )
        if resume:
            used[run.name] = batch[run.name].seeds()
            done[run.name] = len(used[run.name])

    plan = ", ".join(f"{run.name}x{round_size(run)}" for run in runs)
    if resume:
        log(f"Fortsetzung: {sum(done.values())} Level bereits vorhanden")
    log(f"Start: {len(runs)} Regime, {MAX_WORKERS} Worker, Runde = {plan}")
    log(f"Stoppen mit Ctrl-C oder: New-Item {STOP_FILE}")

    pool = Pool()
    rng = random.Random()
    started = time.perf_counter()
    round_index = 0

    try:
        while not should_stop():
            round_index += 1
            round_started = time.perf_counter()

            round_items: list[RunConfig] = []
            for run in runs:
                round_items.extend([run] * round_size(run))
            rng.shuffle(round_items)

            played = run_workload(round_items, pool, batch, shrunk, used, done, rng)
            for run in runs:
                log(
                    f"  Runde {round_index} {run.name}: "
                    f"+{played.get(run.name, 0)} (gesamt {done[run.name]})"
                )

            elapsed = time.perf_counter() - round_started
            total = sum(done.values())
            log(
                f"Runde {round_index} fertig in {elapsed / 60:.1f} min, "
                f"{total} Level gesamt, {(time.perf_counter() - started) / 3600:.2f} h gelaufen"
            )
    except KeyboardInterrupt:
        log("KeyboardInterrupt -- finalisiere.")
    finally:
        pool.shutdown()
        log("Finalisiere Checkpoints ...")
        for run in runs:
            levels = batch[run.name].finalize(run.interesting_path)
            shrinks = shrunk[run.name].finalize(run.shrunk_path)
            log(f"  {run.name}: {levels} Level -> {run.interesting_path.name} ({shrinks} Shrink)")
        log(f"Fertig. {sum(done.values())} Level in {(time.perf_counter() - started) / 3600:.2f} h")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--resume"]
    resuming = "--resume" in sys.argv[1:]
    selected = select_runs(args) if args else LONG_RUN_GRID
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    signal.signal(signal.SIGINT, _request_stop)
    keep_awake(True)
    try:
        with native_backend():
            main(selected, resume=resuming)
    finally:
        keep_awake(False)
