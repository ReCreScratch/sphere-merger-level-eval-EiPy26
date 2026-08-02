# Performance-Optimierungen: Agenten/Physik

Log zu Entscheidungen rund um Simulationsgeschwindigkeit (Anlass:
1000-Level-Batch-Checks, `LookaheadAgent` ist Flaschenhals).

## 2026-08-02

**Analyse:** `LookaheadAgent` ist O(N²) in der Kandidatenzahl (N=91 bei
1°-Schritt, ~5900 `simulate_shot`-Aufrufe pro Zug), `GreedyAgent` O(N) --
erklärt den Geschwindigkeitsunterschied. Profiling zeigt keine einzelne
Hotspot-Funktion, sondern schiere Menge an Physik-Settle-Arbeit.

- **A (Winkelauflösung senken):** abgelehnt -- feine Auflösung ist
  inhaltlich zentral, nicht verhandelbar.
- **B (`simulate_shot` ohne `copy.deepcopy`):** umgesetzt.
  `_clone_state` (`agents/base.py`) teilt `state.level` per Referenz
  (wird nie mutiert), kopiert nur `spheres`/`remaining_queue`. Gemessen
  (`choose_shot`, 1. Baseline-Level, 3 Läufe): ~6.1s -> ~5.4s Wall-Clock
  (~12%). Kleinerer Gewinn als gedacht -- O(N²)-Struktur bleibt Hauptkosten.
  (Erster Messwert war fehlerhaft durch `git stash`, das versehentlich
  einen älteren Lookahead-Algorithmus mit reinmischte -- Lehre: bei
  Perf-Vergleichen einzelne Zeile toggeln statt stashen.)
- **C (`deal`-Contracts in Sim-Läufen abschalten):** umgesetzt.
  `contracts_disabled()`-Kontextmanager in `agents/runner.py`, umschließt
  `play_round`/`record_playthrough` -- interaktives Spiel (rendert über
  `renderer.py`, nutzt `runner.py` nicht) bleibt mit Contracts.
  `deal`s Schalter ist Prozess-global, greift also nicht in
  Executor-Worker-Prozessen; dafür `disable_contracts_in_worker` als
  `initializer` in den beiden Skripten mit `ProcessPoolExecutor`
  (`demo_find_divergence_live.py`, `demo_agent_grid_random9.py`). Gemessen:
  ~2-3% -- Contracts waren nie der Hauptkostenpunkt (siehe Profiling in
  `docs/ki_log.md`, dort schon mal ~0.2% bei der Physik-Engine).
- **D (Executor-Pooling):** geprüft, kein Bug. `demo_find_divergence_live.py`
  und `demo_agent_grid_random9.py` poolen bereits korrekt (ein Pool über
  alle Level). `demo_agent_grid.py` ohne Executor, aber unkritisch (3 Level).
- **E (Alpha-Pruning im 2-Ply-Search):** abgelehnt. Wäre correctness-mäßig
  möglich (Schranke pro Kandidat auf dessen eigenem Nachfolgefeld, kein
  Greedy-Rückfall), aber Scoring belohnt gezielt punktlose Setup-Züge für
  lange Merge-Kaskaden im Folgeschuss (`combo_index` in
  [scoring.py](../src/sphere_merger/game/scoring.py)) -- eine
  simulationsfreie Schranke dafür wäre zu locker, um nennenswert Arbeit
  zu sparen.

## 2026-08-02 (Fortsetzung): 20-Level-Timing-Test

`scripts/agent_batch_timing.py` (neu, nach D-Muster): 20 Zufallslevel,
greedy vs. lookahead, je einzeln gestoppt. Ergebnis: Lookahead stabil
~7-9s/Level (Hochrechnung 1000 Level ≈ 135 min). Greedy dagegen wild
schwankend (1.1s bis 20.6s) -- teils langsamer als Lookahead.

**Ursache gefunden:** `GreedyAgent`s Tiebreak-Fallback
([greedy_agent.py:70-76](../src/sphere_merger/agents/greedy_agent.py#L70))
bewertet bei Gain-Gleichstand *jeden* getiedeten Kandidaten mit dem vollen
2-Ply-Sweep (`candidate_total_gain`) -- bei häufigen 0-Gain-Ties praktisch
derselbe Aufwand wie Lookahead, aber ohne `executor` in den bisherigen
Skripten liefen die Tiebreaks sequenziell.

**Fix:** `GreedyAgent` bekommt in `agent_batch_timing.py` und
`demo_find_divergence_live.py` denselben `executor` wie `LookaheadAgent`
(Parameter existierte bereits, wurde nur nicht übergeben). Verifiziert an
den beiden Ausreißern: Seed 12 14.9s -> 2.9s, Seed 16 20.6s -> 3.3s,
Scores unverändert.

**Rerun mit Fix (20 Level):** Greedy durchgehend <3.5s (vorher bis 20.6s).
Lookahead stabil ~8.3s/Level -> 1000 Level ≈ 139 min. Gesamt 20 Level:
192.7s.

**Interessante-Level-DB:** `game/interesting_levels.py` (neu) -- JSON-Store
(`data/interesting_levels.json`), schema-agnostisch, dedupliziert nach
(seed, source_script). Speichert nur Seed + Generierungsparameter, nicht
den Level selbst (Determinismus reicht zur Reproduktion). Top 3 nach
Score-Gap aus dem 20er-Lauf gespeichert: Seed 17 (Gap 26), 15 (Gap 22),
9 (Gap 18).

**Offen:** 1000-Level-Lauf.

## 2026-08-02 (Fortsetzung): native Beschleunigung (Rust statt C++/GPU)

Nach B/C/D/E bleibt die O(N²)-Struktur der Lookahead-Suche der Haupt-
kostenpunkt; Profiling zeigt den Löwenanteil als reinen Python-Interpreter-
Overhead über tausende `step()`-Aufrufe pro `choose_shot`. Nächster Hebel:
die komplette Settle-Schleife (`simulate_shot`) als eine native Funktion
statt tausender einzelner Python-Aufrufe.

- **GPU verworfen:** zu wenige Kugeln/Schritt, Kernel-Launch-Overhead
  dominiert. Würde nur bei Batch-Vektorisierung vieler Kandidaten als ein
  Tensor-Op lohnen -- das ist ein Physik-Neubau, kein Umbau.
- **Rust statt C++:** auf Windows braucht ein C++-Python-Extension
  (pybind11) praktisch MSVC/Visual-Studio-Build-Tools (mehrere GB,
  systemweit). Rust hat über `rustup` einen GNU-Host-Target
  (`x86_64-pc-windows-gnu`) mit eigenem Linker, keine VS-Abhängigkeit.
  Dazu: PyO3/`maturin` ergonomischer als pybind11/CMake, memory-safe ohne
  GC (relevant in einer Float-Hot-Loop).
- **Toolchain projekt-lokal:** `rustup`/`cargo` über `RUSTUP_HOME`/
  `CARGO_HOME` in `native/`-nahes `.toolchain/` (gitignored) statt
  systemweit -- kein Admin, nichts global registriert, Ordner löschen
  entfernt alles. Setup-Doku: `README.md`.
- **Additiv, kein Ersatz:** Python-Physik bleibt Standardpfad und
  Referenz-Implementierung (auch fürs Determinismus-Testing gegen die
  native Version noetig). Rust wird über einen `backend`-Parameter
  zuschaltbar (analog zum bestehenden `executor`-Opt-in-Muster der
  Agenten), Default bleibt Python.
- **Machbarkeits-Slice erledigt:** `native/sphere_merger_native/` (PyO3-
  Crate) baut via `maturin develop` und importiert aus dem Projekt-venv
  (`ping() -> "pong"`) -- Pipeline steht, physikalische Portierung folgt
  als nächster Schritt.
