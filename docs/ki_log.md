# KI-Nutzungs-Log

Laufendes Log für den Bericht (Kapitel "Mensch vs. KI"). Kurzeintrag bei
nennenswerter KI-Beteiligung: was wurde generiert, warum sinnvoll/nötig, wo bewusst
abgewichen.

## 2026-07-30
- Projektgerüst (Repo-Struktur, pyproject.toml, CLAUDE.md, docs/) mit Claude Code
  geplant und aufgesetzt. Struktur- und Workflow-Entscheidungen (Domänen-Aufteilung,
  Commit-Granularität, Tooling-Wahl) in Zusammenarbeit erarbeitet, nicht blind
  übernommen — siehe `docs/planning_notes.md`.
- `Vector3`/`Sphere` (physics) generiert. Erster Ansatz nutzte `@deal.inv` für die
  Radius/Level-Invariante auf `Sphere`. Tests deckten auf, dass `deal.inv` bei
  Dataclasses mit mehreren Feldern während der Konstruktion fehlschlägt (prüft nach
  jeder einzelnen Feldzuweisung, nicht erst nach vollständigem `__init__` —
  `AttributeError` auf noch unzugewiesene Felder). Nach Rücksprache: `deal.inv`
  entfernt, Validierung stattdessen in `__post_init__` (`ValueError`); `deal`
  bleibt für Pre-/Postconditions auf Funktionen vorgesehen, wo das Problem nicht
  auftritt (Argumente liegen beim Aufruf vollständig vor).
- `collision.py` (Kollisionserkennung, Overlap-Solver mit `deal.pre`/`deal.ensure`)
  generiert, inkl. Hypothesis-Property-Test für die Invariante "nach dem Solver
  keine Überlappung mehr". Erster Vorschlag für den degenerierten Fall (deckungs-
  gleiche Mittelpunkte) war eine feste x-Achsen-Fallback-Richtung; auf Wunsch
  angepasst auf Relativgeschwindigkeitsrichtung, x-Achse nur als letzter Fallback
  wenn auch die Geschwindigkeiten identisch sind.
- `boundary.py` (Boden+Wände einheitlich als Box, elastisch/einstellbar) und
  `engine.py` (`PhysicsConfig`, `step`) generiert. Zweiter deal-Stolperstein:
  `deal.pre`-Validator bekommt nur tatsächlich übergebene Argumente, nicht die
  per Funktions-Default aufgefüllten — Test mit weggelassenem `config`-Argument
  schlug mit `TypeError` (nicht der erwarteten `PreContractError`) fehl. Fix:
  Default auch in der Validator-Lambda spiegeln (`config=None`).
