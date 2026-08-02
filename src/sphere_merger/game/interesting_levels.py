"""Persistent store of "interesting" randomly generated levels -- e.g. ones
where different agents' scores diverge notably -- found while batch-testing
agents, so they can be revisited without re-running the search that found
them.

Stores generation parameters (seed + whatever else the caller wants
alongside it), not the level itself: `generate_random_level` is
deterministic, so the seed and its parameters reproduce the exact same
level again. Schema-agnostic on purpose -- callers decide what a record
holds; this module only knows how to load/dedupe/save it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "interesting_levels.json"


def load(path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    """Every record currently stored at `path` (`[]` if it doesn't exist yet)."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_level(record: dict[str, Any], path: Path = DEFAULT_DB_PATH) -> None:
    """Add `record` at `path`, replacing any existing record with the same
    (`seed`, `source_script`).

    Keeps reruns of the same batch script from piling up duplicate entries
    for the same level -- the newest scores for a given (seed, script)
    combination win.
    """
    key = (record["seed"], record["source_script"])
    records = [r for r in load(path) if (r["seed"], r["source_script"]) != key]
    records.append(record)
    records.sort(key=lambda r: (r["source_script"], r["seed"]))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
