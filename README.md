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

## Spielen und Läufe starten

```
python scripts/play_seed.py 44 6b_3s   # ein Level selbst spielen
python scripts/long_run.py 8b          # Batch-Lauf eines Regimes
```

Beide Skripte adressieren ein Level über **Regime + Seed**. Ein Regime ist die
Kombination aus Kugelanzahl und Länge der Schuss-Queue und heißt
`<Kugeln>b_<Schüsse>s` -- `6b_3s` sind also 6 Startkugeln und 3 Schüsse. Die
beiden ältesten Läufe stammen aus der Zeit mit fest zwei Schüssen und heißen
darum nur `8b` und `5b` (8 bzw. 5 Kugeln, 2 Schüsse); die Namen auf `_fm` sind
die konstruierten, vollständig verschmelzbaren Level.

Die gültigen Namen stehen in `RUNS` (`game/interesting_levels.py`), zusammen mit
Feldgröße, Spawn-Position, Schussgeschwindigkeit und Zielpunktzahl -- alles, was
ein Seed sonst noch braucht. Freie Parameter nimmt keines der Skripte: jedes
Regime besitzt sein eigenes Dateipaar in `data/`, und Läufe mit anderer Kugel-
oder Schusszahl sind untereinander ohnehin nicht vergleichbar. `play_seed.py`
ohne Argumente spielt Seed 44 in `6b_3s`; `long_run.py` ohne Argumente rechnet
alle neun Zufallsregime und **ersetzt dabei deren vorhandene Daten**.

## Tests & Checks

```
pytest
ruff check .
ruff format --check .
mypy src
interrogate src
```

## Optionale Rust-Beschleunigung (native/)

Einzelne heiße Pfade (Physik-Settle-Schleife) gibt es optional auch als
Rust-Erweiterung (`native/sphere_merger_native/`, PyO3) -- rein additiv,
per Backend-Parameter zuschaltbar, die Python-Implementierung bleibt
Standard und Referenz. Begründung/Entscheidung: siehe
`docs/physics_optimizations.md`.

Toolchain ist bewusst projekt-lokal (kein globales `rustup`, keine
Visual-Studio-Abhängigkeit -- GNU statt MSVC-Host):

```
# einmalig, in .toolchain/ (per .gitignore ausgeschlossen)
Invoke-WebRequest -Uri "https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe" -OutFile ".toolchain\rustup-init.exe"
$env:RUSTUP_HOME = "$PWD\.toolchain\rustup"
$env:CARGO_HOME = "$PWD\.toolchain\cargo"
& ".toolchain\rustup-init.exe" -y --no-modify-path --default-host x86_64-pc-windows-gnu --profile minimal

# bei jeder Shell-Session vor dem Bauen:
$env:RUSTUP_HOME = "$PWD\.toolchain\rustup"
$env:CARGO_HOME = "$PWD\.toolchain\cargo"
$env:PATH = "$PWD\.toolchain\cargo\bin;" + $env:PATH

# Extension bauen + ins aktive venv installieren:
cd native\sphere_merger_native
maturin develop
```
