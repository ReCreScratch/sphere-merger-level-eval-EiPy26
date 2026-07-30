# Sphere Merger

Level Evaluation - Sphere Merger. Physik-basiertes Merge-Spiel (ähnlich Billard/Suika):
Kugeln werden angeschossen, gleiche Level verschmelzen bei Kontakt. Kernfrage des
Projekts: lassen sich zufällig generierte Level automatisch charakterisieren
(Schwierigkeit, Lösungsvielfalt, Zielgenauigkeit) — untersucht über den Vergleich
mehrerer Spieleragenten (random, greedy, vorausschauend).

Details zu Spielkonzept, MVP und Meilensteinen: [Projektplan.md](Projektplan.md).

## Status

MVP in Entwicklung. Aktueller Stand: Projektgerüst.

## Installation

```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Tests & Checks

```
pytest
ruff check .
ruff format --check .
mypy src
interrogate src
```
