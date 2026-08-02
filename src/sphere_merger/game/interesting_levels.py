"""Persistent store of one batch run's levels -- e.g. ones where different
agents' scores diverge notably -- found while batch-testing agents, so
they can be revisited without re-running the search that found them.

Holds a single run's worth of data at a time (a new run replaces it
wholesale, not merged in) -- shared generation parameters (`meta`) are
stored once, per-level records (`levels`) hold only what actually varies
(seed + whatever scores the caller wants alongside it). Reproducing a
level needs only its seed plus `meta`: `generate_random_level` is
deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "interesting_levels.json"


def load_run(path: Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    """`{"meta": ..., "levels": ...}` currently stored at `path`
    (`{"meta": {}, "levels": []}` if it doesn't exist yet)."""
    if not path.exists():
        return {"meta": {}, "levels": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(
    meta: dict[str, Any], levels: list[dict[str, Any]], path: Path = DEFAULT_DB_PATH
) -> None:
    """Replace `path`'s contents with `meta` (shared generation parameters
    for this run) and `levels` (one record per level, minimal per-level
    fields only -- e.g. seed + scores)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "levels": levels}, indent=2) + "\n", encoding="utf-8")
