# Level-Shrinking: Entscheidungslog

Ziel: gefundene High-Gap-Level (greedy vs. lookahead) auf eine kleinere,
menschlich leichter lesbare Variante reduzieren, die dieselbe Divergenz
noch zeigt. Verlauf hier festgehalten, weil mehrere Kursänderungen
unterwegs passiert sind -- Kurzfassung in `docs/ki_log.md`.

## Entscheidungspfad

- **v1 (verworfen): Delta-Debug mit Gap-Erhaltung.** `game/shrink.py::shrink_level` --
  entfernt greedy je eine Kugel/einen Schuss, behält die Entfernung nur wenn
  `gap(kandidat) >= gap(original)`. Zwei Simplifikations-Operationen: Kugel
  weglassen, Schuss-Queue kürzen.
- Schuss-Queue-Kürzung hat im echten Top-50-Lauf **kein einziges Mal**
  gegriffen (immer 2->2 Schüsse) -- auf Wunsch entfernt, nur noch
  Kugel-Entfernung.
- Top-50-Lauf (nach Gap sortiert): 589-632s gesamt (~11-13s/Level) -- pro
  Kandidat-Entfernung ein voller Greedy+Lookahead-Durchlauf, macht das für
  alle 1000 Level zu teuer (~3.3h Hochrechnung).
- Browser gebaut (`rendering/level_browser.py` + `scripts/browse_shrunk_levels.py`):
  3 Kategorien (Gap-Zuwachs / Max Shrink / Kaum verändert), alles
  vorberechnet und in `data/shrunk_levels.json` gespeichert -- Browser
  selbst braucht keine Agenten/Executor, öffnet sofort.
- **Nutzer entdeckt beim Anschauen (Seed 389, "kaum verändert"):** eine
  Kugel wird von Lookahead sichtbar nie getroffen, wurde aber nicht
  entfernt -- Verdacht auf Fehler.
- **Erste Diagnose fälschlich "keine einzige Kugel ist je unberührt"** --
  Ursache: Identitätsvergleich gegen `level.initial_spheres` statt gegen
  `state.spheres`; `start_round` deep-copied, Vergleich kann nie treffen.
  Eigener Fehler, nicht Nutzer-Fehleinschätzung.
- Hover-Tooltip im Browser ergänzt (`Sphere`-Identität gegen einen
  Snapshot von `state.spheres` direkt nach Rundenstart, nicht gegen
  `level.initial_spheres`) -- Nutzer hätte damit die exakte Kugel zeigen
  können; Fix hat den Diagnose-Fehler gleichzeitig aufgedeckt und behoben.
- **Korrigierte Diagnose bestätigt Nutzer-Beobachtung:** 36/50 Level haben
  mind. eine von beiden Agenten unberührte Kugel; Seed 389 genau eine
  (Index 6).
- **Aber:** direkter Test zeigt Entfernen von Index 6 lässt Greedy einen
  besseren Schuss finden (28 -> 40), Gap sinkt (64 -> 52) --
  `shrink_level`s Ablehnung war korrekt, kein Bug. "Unberührt vom
  gewählten Schuss" impliziert nicht "irrelevant für den gesamten
  Kandidatenraum".
- **Nutzer-Entscheidung (Kurswechsel):** Fokus auf Lookahead als
  Ziel-Agent; Gap-Erhaltung als Kriterium fallen lassen. Eine Kugel darf
  weg, wenn sie von **keinem** der "cleveren" Agenten (alle außer Random)
  je berührt wird -- unabhängig davon, ob das Entfernen den Gap ändert.
  Ein sinkender Gap ist dabei akzeptables Ergebnis ("Level war leichter
  als der Score suggerierte"), keine Suche nach einer besseren/anderen
  Strategie.
- **v2 (aktuell): iteratives Used-Spheres-Pruning.**
  `game/round.py::touched_sphere_indices` (reine Physik-Simulation: welche
  `initial_spheres` verschmelzen oder bewegen sich) +
  `agents/runner.py::shrink_to_used_spheres` (Fixpunkt-Iteration: Kugeln
  entfernen, die von keinem übergebenen Agenten berührt werden, neu
  simulieren, wiederholen bis nichts mehr gefunden wird). Ein
  Agenten-Paar-Durchlauf pro Runde statt einer pro Einzelkugel-Versuch --
  praktikabel für den ganzen Batch, nicht nur die Top-Seeds.
- Altes `game/shrink.py` (samt Tests), `scripts/shrink_interesting_level.py`
  und die alte `data/shrunk_levels.json` ersatzlos gelöscht -- keine
  Refactor-Leichen, komplett reproduzierbar durch Neulauf von
  `scripts/shrink_top_levels.py`.
