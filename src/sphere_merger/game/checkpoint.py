"""Append-only checkpoint for long batch runs, and finalising one into the
normal `{"meta": ..., "levels": [...]}` file the rest of the code reads.

A run lasting hours must not hold its results in memory until the end,
where any abort would discard all of them. Every finished level is instead
appended to a JSON Lines file and flushed at once, costing a few hundred
microseconds against a level that took seconds -- so the worst an abort
can cost is the level currently in flight.

Two files per run:

* `<name>.jsonl` -- one finished level per line, appended as it completes.
* `<name>.meta.json` -- the run's shared generation parameters, written
  once at the start. Kept beside the lines rather than as line 1, so
  appending never has to care about position and a truncated last line can
  be dropped without losing the header.

`finalize` holds the finished levels in memory while `save_run`
serialises them into one JSON document -- a bounded, one-off cost at the
very end, unlike accumulating them throughout.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sphere_merger.game.interesting_levels import save_run

CHECKPOINT_DIR = Path(__file__).resolve().parents[3] / "data" / "checkpoints"


class Checkpoint:
    """An append-only run checkpoint, identified by `name` inside `directory`."""

    def __init__(self, name: str, directory: Path = CHECKPOINT_DIR) -> None:
        """Prepare (but do not yet create) the checkpoint files for `name`."""
        self.name = name
        self.directory = directory
        self.lines_path = directory / f"{name}.jsonl"
        self.meta_path = directory / f"{name}.meta.json"

    def start(self, meta: dict[str, Any], resume: bool = False) -> None:
        """Write `meta` and, unless resuming, clear any previous lines.

        Truncating matters: since this class only ever appends, a new run
        of the same regime would otherwise continue the previous one's
        file and finalise a dataset mixing two runs under a `meta`
        describing only the newer.

        `resume=True` is the deliberate exception, for the same run
        continuing after an interruption. Nothing here can verify that the
        parameters really are unchanged, so the caller has to mean it.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        if not resume:
            self.lines_path.write_text("", encoding="utf-8")

    def seeds(self) -> set[int]:
        """Seeds already recorded -- so a resumed run does not replay them."""
        return {record["seed"] for record in self.records()}

    def append(self, record: dict[str, Any]) -> None:
        """Append one finished level and flush it to disk.

        Opened and closed per call rather than keeping a handle open for
        hours, so that every line reported as done is genuinely on disk
        even if the interpreter dies.
        """
        line = json.dumps(record, separators=(",", ":"))
        with self.lines_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def records(self) -> Iterator[dict[str, Any]]:
        """Every complete level recorded so far, in order.

        A trailing partial line, left behind when the process died
        mid-append, is skipped rather than raised on -- losing the level
        in flight beats writing every record twice for atomicity.
        """
        if not self.lines_path.exists():
            return
        with self.lines_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError:
                    return

    def count(self) -> int:
        """How many complete levels are recorded so far."""
        return sum(1 for _ in self.records())

    def finalize(self, path: Path) -> int:
        """Write the recorded levels to `path` in the standard run format.

        Returns how many levels were written. Safe to call on a run that
        was aborted -- the result is simply a shorter dataset, which every
        consumer already handles, rather than a broken one.

        Raises:
            FileNotFoundError: if the run was never started (no meta file).
        """
        if not self.meta_path.exists():
            raise FileNotFoundError(f"kein Checkpoint-Meta fuer {self.name}: {self.meta_path}")
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        levels = list(self.records())
        meta["level_count"] = len(levels)
        meta["seeds"] = [level["seed"] for level in levels]
        save_run(meta=meta, levels=levels, path=path)
        return len(levels)
