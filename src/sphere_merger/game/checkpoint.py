"""Append-only checkpoint for long batch runs, and finalising one into the
normal `{"meta": ..., "levels": [...]}` file the rest of the code reads.

A run that takes hours must not hold its results in memory until the end:
an abort -- deliberate or not -- would throw all of them away, and nothing
about the work done so far is recoverable from a process that no longer
exists. So every finished level is appended to a JSON Lines file and
flushed immediately. The cost is a few hundred microseconds against a
level that took seconds to compute; the benefit is that the worst an abort
can cost is the level currently being played.

Two files per run:

* `<name>.jsonl` -- one finished level per line, appended as it completes.
* `<name>.meta.json` -- the run's shared generation parameters, written
  once when the run starts. Kept beside the lines rather than as line 1 so
  that appending never has to care about position, and so a truncated last
  line (power loss mid-write) can be dropped without losing the header.

`finalize` tolerates a truncated final line -- the only line an
interrupted write can damage. It does hold the finished levels in memory
while `save_run` serialises them, since that is one JSON document; at the
sizes these runs reach (tens of MB) that is a bounded, one-off cost at the
very end, unlike accumulating them for the entire run.
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

    def start(self, meta: dict[str, Any]) -> None:
        """Write `meta` and clear any previous lines for this run.

        Truncating matters more than it looks: appending is the whole
        point of this class, so without it a new run of the same regime
        would silently continue the previous one's file and finalise a
        dataset mixing two runs -- with a `meta` describing only the
        newer. A replaced run replaces both parts or neither, matching
        `save_run`'s wholesale semantics.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        self.lines_path.write_text("", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        """Append one finished level and flush it to disk.

        Opened and closed per call rather than holding a handle open for
        hours: a handle that outlives an interpreter crash guarantees
        nothing, while an explicit `flush` here means every line that was
        reported as done is really on disk.
        """
        line = json.dumps(record, separators=(",", ":"))
        with self.lines_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def records(self) -> Iterator[dict[str, Any]]:
        """Every complete level recorded so far, in order.

        A trailing partial line (written when the process died mid-append)
        is skipped rather than raising: losing the one level in flight is
        the accepted cost of not having to write a second copy of every
        record just to make the last one atomic.
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
