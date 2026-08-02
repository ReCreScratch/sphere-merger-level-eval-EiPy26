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
