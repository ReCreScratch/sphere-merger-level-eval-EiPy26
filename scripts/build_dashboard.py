"""Inline `data/dashboard_data.json` into `scripts/dashboard_template.html`
and write the finished page to `build/dashboard.html`.

The build step exists because the published page cannot fetch anything: a
strict CSP blocks every external request, so the data has to be part of
the document. Generating the page instead of hand-editing it is the whole
point -- the first version of this dashboard had its numbers typed into
the JavaScript by hand and silently went stale the moment the batch was
re-run.

Run `scripts/build_dashboard_data.py` first; this script only assembles.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "scripts" / "dashboard_template.html"
DATA_PATH = ROOT / "data" / "dashboard_data.json"
OUTPUT_PATH = ROOT / "build" / "dashboard.html"

PLACEHOLDER = "/*__DATA__*/"


def build() -> Path:
    """Write the assembled page and return where it landed.

    Raises:
        FileNotFoundError: if the aggregate has not been built yet.
        ValueError: if the template lost its data placeholder.
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH.name} fehlt -- erst build_dashboard_data.py laufen lassen"
        )

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise ValueError(f"Platzhalter {PLACEHOLDER} nicht im Template gefunden")

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # separators=(",", ":") keeps the inlined payload compact; the page is a
    # single self-contained file and nobody reads this copy by hand -- the
    # readable one stays in data/.
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    # `</script>` inside a string literal would end the host <script> block
    # early; no such sequence exists in this data today, but escaping it is
    # a one-character insurance against a future field carrying markup.
    payload = payload.replace("</", "<\\/")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")
    return OUTPUT_PATH


if __name__ == "__main__":
    path = build()
    print(f"-> {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
