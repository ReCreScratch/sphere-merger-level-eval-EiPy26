# Datenschema: `data/*.json`

**Muss aktuell gehalten werden.** Sobald sich ein `save_run(...)`-Aufruf in
`scripts/long_run.py` ändert (Feld hinzugefügt/entfernt/umbenannt), dieses
Dokument im selben Commit nachziehen -- nicht aus dem Gedächtnis, sondern
durch erneutes Lesen des tatsächlichen
`save_run(meta=..., levels=[...])`-Aufrufs im Code. Stand: 2026-08-27,
verifiziert gegen den Code zu diesem Zeitpunkt.

`long_run.py` ist seit 2026-08-27 der einzige Produzent. Vorher schrieben
`agent_batch_timing.py` (Rohdaten) und `shrink_top_levels.py` (Shrink) --
beide entfernt, weil `long_run.py` beides in einem Durchlauf erledigt.
Ihre Namen stehen aber weiterhin im `source_script`-Feld der damals
erzeugten Dateien, die unverändert gültig und lesbar sind; genau dafür
gibt es das Feld.

Beide Dateifamilien nutzen `game/interesting_levels.py`s generisches
`{"meta": ..., "levels": [...]}`-Format: `meta` einmal pro Datei (geteilte
Generierungsparameter), `levels` eine Liste mit einem Eintrag pro Level.
`save_run` ersetzt die Zieldatei komplett (kein Merge) -- ein neuer Lauf
überschreibt den alten vollständig.

## Läufe und Dateinamen

Welche Läufe es gibt, steht an einer Stelle: `RUNS` in
`game/interesting_levels.py`. Ein Lauf (`RunConfig`) ist durch Kugelanzahl
und Länge der Schuss-Queue definiert -- beides ändert das
Schwierigkeitsregime, macht die Ergebnisse also unvergleichbar mit denen
davor, weshalb jede Kombination ihr eigenes Dateipaar bekommt statt den
letzten Lauf zu überschreiben.

| `name` | Kugeln | Schüsse | Level (Stand 2026-08-06) |
|---|---|---|---|
| `8b` | 8 | 2 | 4050 |
| `5b` | 5 | 2 | 4050 |
| `6b_3s` | 6 | 3 | 1000 |
| `10b_2s` | 10 | 2 | 3949 |
| `5b_3s` | 5 | 3 | 2610 |
| `8b_3s` | 8 | 3 | 2610 |
| `10b_3s` | 10 | 3 | 2522 |
| `5b_4s` | 5 | 4 | 2100 |
| `8b_4s` | 8 | 4 | 2100 |
| `10b_4s` | 10 | 4 | 2100 |
| `4b_2s_fm` | 4 | 2 | - |
| `3b_3s_fm` | 3 | 3 | - |
| `2b_4s_fm` | 2 | 4 | - |
| `3b_5s_fm` | 3 | 5 | - |

Die vier `*_fm`-Regime (`full_mergeable=True`, siehe
`docs/full_merge_experiment.md`) nutzen `generate_full_mergeable_level`
statt `generate_random_level` -- `merge_popcount` ist dort immer `1` by
construction, nicht wie bei den übrigen Regimen nur zufällig manchmal.
Gemessen wird hier, wie oft der Agent den garantiert möglichen
Komplett-Merge tatsächlich schafft. 4-/5-Schuss-Regime darunter (`3b_3s_fm`,
`2b_4s_fm`, `3b_5s_fm`): `LookaheadAgent`s 2-Ply-Suche ist dort nicht
nachweislich nah-optimal (siehe unten) -- die gemessene Quote ist eine
Untergrenze, keine echte Erreichbarkeits-Quote.

Die Level-Zahlen von `8b`/`5b`/`10b_2s`/`5b_3s`/`8b_3s`/`10b_3s`/`5b_4s`/
`8b_4s`/`10b_4s` stammen aus einem `scripts/long_run.py`-Lauf
(2026-08-05, ~7.6h, siehe `docs/ki_log.md`) und sind größer als die
1000-Level-Stichproben der früheren Einzelläufe -- ein späterer erneuter
`long_run.py`-Lauf verändert diese Zahlen. Von den Datendateien liegen
nur die kleinen frühen Läufe (`5b`, `8b`, `6b_3s`, je ~1 MB) plus
`dashboard_data.json` im Repo; die Rohdaten des langen Laufs und der
fm-Regime bleiben lokal (~400 MB, einzelne Dateien bis 82 MB) und sind
per `.gitignore` ausgeschlossen.

`name` ist der Dateiname-Stamm und lautet standardmäßig `<n>b_<s>s`. Die
ersten beiden Läufe stammen aus der Zeit, als die Schusszahl noch fix 2
war, und sind per `slug` auf ihre ursprünglichen Namen festgenagelt --
Umbenennen hätte nur Diff erzeugt.

Die erzeugenden und lesenden Skripte nehmen diese Namen als
Kommandozeilenargumente (`python scripts/long_run.py 6b_3s`), um einen
einzelnen Lauf zu wiederholen. **Ohne Argument laufen alle** -- und da
`save_run` die Zieldatei ersetzt und frische Seeds zieht, verwirft das die
vorhandenen Ergebnisse der anderen Regimes.

## `data/interesting_levels_<name>.json` (long_run.py)

### `meta`

| Feld | Typ | Bedeutung |
|---|---|---|
| `source_script` | str | `"long_run.py[rust]"`; ältere Dateien: `"agent_batch_timing.py[rust]"` |
| `field` | dict | `x_min`/`x_max`/`y_min`/`y_max` des Spielfelds |
| `spawn_margin` | float | Abstand Spawn-Position von Feldrand |
| `target_score` | int | aktuell fix `999` (kein echtes Sieg-Kriterium bisher) |
| `initial_sphere_count` | int | Kugelanzahl des Laufs (`RunConfig.sphere_count`) |
| `shot_count` | int | Länge der Schuss-Queue (`RunConfig.shot_count`) |
| `level_range` | [int, int] | Level-Bereich der Startkugeln |
| `shot_speed` | float | feste Schussgeschwindigkeit aller Agenten |
| `found_at` | str | ISO-Datum des Laufs |
| `seeds` | list[int] | alle `LEVEL_COUNT` Level-Seeds dieses Laufs, per `random.sample` gezogen -- Basis für späteren Abgleich/Reproduktion |
| `full_mergeable` | bool | `RunConfig.full_mergeable` -- ob dieses Regime mit `generate_full_mergeable_level` statt `generate_random_level` erzeugt wurde (nur `long_run.py`-Läufe, siehe unten) |

### `levels[]` (ein Eintrag pro Level)

| Feld | Typ | Bedeutung |
|---|---|---|
| `seed` | int | Level-Seed (siehe `meta.seeds`) |
| `merge_popcount` | int | `merge_popcount(initial_spheres + shot_queue)` -- kleinstmögliche Kugelzahl am Ende, egal wie gespielt wird (`1` = vollständiger Merge zu einer Kugel ist grundsätzlich möglich). Bei `full_mergeable`-Regimen immer `1`, bei den übrigen nur zufällig |
| `random_scores` | list[int] | `RANDOM_SAMPLE_COUNT` (=20) unabhängige Random-Playthroughs, je eigener `RandomAgent(seed=seed*20+i)` -- Rohwerte, nicht nur Mittelwert, damit Mittelwert/Std/Min/Max später ohne Neu-Simulation berechenbar sind |
| `greedy_score` | int | finaler Score des Greedy-Playthroughs |
| `greedy_shots` | list[[angle, speed]] | Greedys Schüsse, zum Replay |
| `greedy_score_per_shot` | list[int] | kumulierter Score nach jedem Greedy-Schuss |
| `greedy_merges_per_shot` | list[list[int]] | pro Schuss: Liste der Level-Werte aller dabei entstandenen Merges (leer = kein Merge) |
| `lookahead_score` | int | analog zu `greedy_score` |
| `lookahead_shots` | list[[angle, speed]] | analog zu `greedy_shots` |
| `lookahead_score_per_shot` | list[int] | analog zu `greedy_score_per_shot` |
| `lookahead_merges_per_shot` | list[list[int]] | analog zu `greedy_merges_per_shot` |
| `gap` | int | `abs(greedy_score - lookahead_score)` |
| `lookahead_max_combo` | int | längste Merge-Kette eines einzelnen Lookahead-Schusses |

**Nicht gespeichert, aber aus `*_merges_per_shot` ableitbar** (siehe
Metriken-Diskussion im Chat): Leerlauf-Schüsse (Einträge mit `[]`),
Erster-Merge-Index, Merges-pro-Schuss-Verteilung. Bewusst nicht redundant
mitgespeichert.

### Zusätzliche Felder aus `long_run.py`

Läufe von `scripts/long_run.py` (alles außer `8b`, `5b`, `6b_3s`)
schreiben zusätzlich den **Feldzustand nach jedem Schuss**. `meta` trägt
dort außerdem `random_sample_count` und `level_count`.

| Feld | Typ | Bedeutung |
|---|---|---|
| `greedy_states` | list[list[[x, y, level]]] | pro Schuss der ausgeruhte Feldzustand danach: eine Liste aller Kugeln als `[x, y, level]`, auf 3 Nachkommastellen gerundet |
| `lookahead_states` | list[list[[x, y, level]]] | analog für Lookahead |
| `random0_shots` / `random0_states` | wie oben | dasselbe für Random-Sample 0. Nur dieses eine der 20 Samples -- alle zu speichern wäre die zehnfache Datenmenge für eine Baseline, bei der nur die Score-Verteilung zählt |

Nicht gespeichert, weil ableitbar oder konstant: **Radius** (folgt aus
`level` über `radius_for_level`) und **Geschwindigkeit** (nach dem Settle
per Definition ~0).

Wozu die Zustände da sind: Mittrunden-Stellungen werden analysierbar
("wie sieht ein Level aus, während ein Schuss vorbereitet wird"), ohne
den Agenten erneut laufen zu lassen. Vor allem aber lässt sich damit eine
*kürzere* Runde aus einer längeren rekonstruieren: Schuss 1 einer
3-Schuss-Runde ist bei gleichem Seed **identisch** mit Schuss 1 der
2-Schuss-Runde (`generate_random_level` zieht die Schuss-Queue der Reihe
nach, der Präfix stimmt also überein, und Lookaheads 2-Ply-Suche stellt
für Schuss 1 exakt dieselbe Frage). Schuss 2 ist es *nicht* -- in der
kurzen Runde ist er der letzte und fällt auf Sofortgewinn zurück. Aus dem
gespeicherten Zustand nach Schuss 1 kostet die echte 2-Schuss-Lösung
aber nur noch einen 1-Ply-Sweep (~91 Simulationen statt ~8400), also
etwa 1 % eines Levels.

## `data/shrunk_levels_<name>.json` (long_run.py)

Enthält **alle** Level des zugehörigen Laufs (kein Top-N-Ausschnitt).
`long_run.py` shrinkt jedes Level direkt neben dem Level, zu dem es
gehört, sodass beide Datensätze nie auseinanderlaufen; die älteren
Dateien entstanden stattdessen in einem eigenen Nachlauf über die fertige
`interesting_levels_<name>.json`.

### `meta`

| Feld | Typ | Bedeutung |
|---|---|---|
| `source_script` | str | `"long_run.py[shrink]"`; ältere Dateien: `"shrink_top_levels.py"` |
| `shrunk_from` | str | Pfad der Quelldatei |
| `field`, `spawn_margin`, `target_score`, `initial_sphere_count`, `shot_count`, `level_range`, `shot_speed` | wie oben | aus den `_build_level`-Konstanten des Skripts, nicht aus der Quelldatei kopiert |

Anders als bei `interesting_levels_<name>.json` fehlen hier `found_at` und
`seeds` -- Asymmetrie, kein bewusstes Design.

### `levels[]`

| Feld | Typ | Bedeutung |
|---|---|---|
| `seed` | int | Level-Seed |
| `original_sphere_count` / `shrunk_sphere_count` | int | Kugelanzahl vor/nach Shrink |
| `original_gap` / `shrunk_gap` | int | Greedy/Lookahead-Gap vor/nach Shrink |
| `spheres_removed` | int | `original_sphere_count - shrunk_sphere_count` |
| `gap_increase` | int | `shrunk_gap - original_gap` |
| `shrink_seconds` | float | Laufzeit des Shrink-Vorgangs für dieses Level |
| `kept_sphere_indices` | list[int] | Indizes (in `original.initial_spheres`), die den Shrink überlebt haben -- Basis, um das geshrinkte Level ohne erneuten Shrink-Lauf aus dem Original zu rekonstruieren |
| `original_greedy_score` / `shrunk_greedy_score` | int | Greedy-Score vor/nach Shrink (beide neu simuliert) |
| `original_lookahead_score` / `shrunk_lookahead_score` | int | **beide identisch** -- Lookahead wird nach dem Shrink nicht neu simuliert, sondern der Original-Score/-Shots wiederverwendet (siehe Modul-Docstring, akzeptierte Ungenauigkeit) |
| `original_greedy_shots` / `shrunk_greedy_shots` | list[[angle, speed]] | Greedy-Schüsse vor/nach Shrink |
| `original_lookahead_shots` / `shrunk_lookahead_shots` | list[[angle, speed]] | **identisch**, siehe oben |

Kein `greedy_score_per_shot`/`merges_per_shot`-Äquivalent hier -- diese
Datei speichert nur, was `shrink_to_used_spheres` ohnehin zurückgibt
(`Playthrough = (shots, score, combo)`), noch nicht auf `ShotRecord`
umgestellt.

## `data/dashboard_data.json` (build_dashboard_data.py)

Aggregat aller Rohdatensätze, ~37 KB statt je 1.1 MB — das einzige, was
das Dashboard liest. Enthält **keine** Roh-Playthroughs, nur Verteilungen,
Kennzahlen und eine Handvoll Beispiel-Seeds.

```
{
  "generated_at": "<ISO-Datum>",
  "datasets": [ { …ein Eintrag je `RUNS`-Eintrag… } ]
}
```

### `datasets[]`

| Feld | Typ | Bedeutung |
|---|---|---|
| `name` | str | `RunConfig.name` des Laufs, identisch mit dem Dateinamen-Stamm |
| `sphere_count` | int | Kugelanzahl dieses Datensatzes (allein nicht mehr eindeutig, siehe `name`) |
| `level_count` | int | Anzahl Level |
| `meta` | dict | `shot_count`, `target_score`, `shot_speed`, `level_range`, `random_samples_per_level`, `found_at` — Teilmenge der Quell-`meta` |
| `summary` | dict | je Kennzahl ein `{mean, median, min, max}`: `gap`, `greedy_score`, `lookahead_score`, `random_mean`, `random_std`, `skill_gain`, `payoff_conc`, `max_combo`, `spheres_removed` |
| `histograms.gap` | `{labels, counts}` | Gap-Verteilung, Bins à 10 |
| `histograms.scores` | `{labels, series:{random,greedy,lookahead}}` | gemeinsame Achse (Bins à 15), `random` = Mittel der 20 Samples je Level |
| `histograms.payoff_conc` | `{labels, counts}` | 10 Bins à 0.1 |
| `histograms.skill_gain` | `{labels, counts}` | Bins à 2 Sigma |
| `archetypes` | dict | Anzahl Level je Tag (`aha`, `spectacle`, `fair_hard`, `luck`) plus `untagged`. Tags sind nicht exklusiv, die Summe kann `level_count` überschreiten |
| `payoff_by_gap_quartile` | dict | Median-Auszahlungskonzentration je Gap-Quartil (`Q1`…`Q4`) |
| `highlights` | dict | je Tag bis zu 10 Beispiel-Level, sortiert nach der Dimension, die den Tag ausgelöst hat. Je Eintrag: `seed`, `gap`, `greedy_score`, `lookahead_score`, `random_mean`, `payoff_conc`, `skill_gain`, `max_combo`, `tags` |

Kennzahlen-Definitionen (`gap` gerichtet statt `abs`, `skill_gain` als
Effektstärke, `payoff_conc`, Archetyp-Schwellen) stehen im Code:
`src/sphere_merger/metrics/`.

## Level aus Seed + `meta` rekonstruieren

```python
level = generate_random_level(
    seed=entry["seed"],
    boundary=Boundary(**meta["field"]),
    spawn_position=Vector2(
        meta["field"]["x_min"] + meta["spawn_margin"],
        meta["field"]["y_min"] + meta["spawn_margin"],
    ),
    target_score=meta["target_score"],
    initial_sphere_count=meta["initial_sphere_count"],
    shot_count=meta["shot_count"],
    level_range=tuple(meta["level_range"]),
)
```

Deterministisch -- derselbe Seed + dieselben `meta`-Werte ergeben immer
dasselbe Level (`generate_random_level`s Garantie).
