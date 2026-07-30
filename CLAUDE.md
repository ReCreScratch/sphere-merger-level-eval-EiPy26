## Arbeitsweise
- Kleine Schritte, ein Teilschritt pro Runde, dann zwischenmelden.
- Vor Code mit Design-Spielraum: Ansatz kurz nennen, auf Go warten.
  Ausnahme: triviale, eindeutige Fixes.
- Aufgabe zu groß für einen Commit → nur nächsten sinnvollen Teilschritt umsetzen.
- Kommunikation knapp, keine Füllwörter, nur Wichtiges/Interessantes. Anteasern ok,
  nicht selbst vertiefen.

## Struktur
src/sphere_merger/{physics,game,agents,rendering,metrics}/ — je Domäne, Single
Responsibility. Neuer Code ins passende Submodul, keine Sammel-Dateien.

## Code-Standards
- ruff format + ruff check verbindlich.
- Type-Hints an neuen public Funktionen/Methoden. mypy ≤1 Fehler (Ziel: strict clean).
- Docstrings (Google-Style) an public Code → interrogate ≥20% (Ziel 80%+Doctests).
- pytest für Units, hypothesis für Physik-Invarianten, Doctests für kleine Funktionen.
- Determinismus: feste Seeds, feste Solving-Reihenfolge. Physics-Änderung →
  Determinismus-Tests grün halten.
- Exceptions nur an Systemgrenzen (User-Input, Level-/Config-Dateien).
- Optional: `deal` für Invarianten/Pre-/Postconditions.

## Commits
- Klein, pro Teilschritt. Message: was + warum, bes. bei Plan-Kurswechseln
  (Entscheidungen werden im Verlauf oft überdacht — das soll ablesbar bleiben).
- Nennenswerte KI-Generierung → Eintrag in docs/ki_log.md.
