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
- `rendering/renderer.py` (pygame, Weltkoordinaten -> Bildschirm, Höhe via
  Schatten+Vertikalversatz, Level-Farbe/-Zahl toggle-bar über `RenderConfig`)
  generiert und per Demo-Skript (`scripts/demo_render.py`) visuell geprüft.
  Dabei fiel beim Anschauen auf: Kugeln hüpften unaufhörlich, über beliebig
  viele Simulationsschritte hinweg konstant, nie abklingend. Analyse ergab
  einen "Zeno-Bouncing"-Diskretisierungsfehler (stabiler Fixpunkt ungleich
  Null bei elastischem/teilelastischem Bodenkontakt ohne Ruhezustand) - kein
  Bug in der Impuls-/Energieformel selbst (nachweislich korrekt, siehe
  test_energy.py), sondern ein fehlender "rest velocity threshold". Fix:
  Schwelle proportional zu gravity*dt (hergeleitet, siehe Docstring
  PhysicsConfig.rest_threshold_factor), zusätzlich Default-Restitution von
  1.0 (unrealistisch, endloses Hüpfen) auf <1 gesenkt.
- Schattendarstellung mehrfach über Sichtprüfung + Rückfrage iteriert: erst
  kleiner mit Höhe (Spielkonvention, keine physikalische Herleitung - auf
  Nachfrage offengelegt statt behauptet), dann Ellipse statt Kreis,
  Mittelpunkt leicht angehoben, zweimal Größe nachjustiert. Gutes Beispiel
  für rein geschmacklich/iterativ getriebene Anpassungen ohne "richtige"
  Antwort.
- UI-Steuerung (Reset/Random-Buttons, Klick-Drag-Schuss) ergänzt. Dabei
  `game/shooting.py::shoot(sphere, angle_degrees, speed)` extrahiert statt
  die Velocity-Berechnung direkt im Renderer zu bauen -- auf Wunsch, damit
  dieselbe Funktion später headless von Agenten (Winkelsweep) genutzt werden
  kann, ohne Maus. Nach visueller Prüfung mehrfach nachgebessert: Schusslinie
  zeigte zunächst die Zugrichtung statt der (gespiegelten) Schussrichtung;
  Feldränder waren durch nicht-zentriertes Seitenverhältnis ungleichmäßig
  sichtbar (Viewport-Klasse mit zentrierenden Rändern behebt das); Zuglinie
  zeigte zunächst nur die Zuglänge statt der tatsächlich simulierten
  Flugweite (inkl. Reibung) -- jetzt eine isolierte Vorschau-Simulation
  über die echte `step()`-Funktion statt einer separaten Formel, um nicht
  aus der Physik-Engine zu laufen. Reibungs-Default halbiert (0.1 -> 0.05).
- `rendering/grid_view.py::run_angle_sweep()` ergänzt: viele unabhängige
  Kopien eines Szenarios gleichzeitig, je mit anderem Startwinkel (Winkel-
  sweep, wie im Projektplan für Agenten vorgesehen) -- Machbarkeits-/
  Performance-Check vor echtem Agenten-Batch-Testing. `Viewport` dafür von
  `window_size`+Margins auf `origin_x`/`origin_y_bottom` umgebaut, damit
  dieselbe Zeichenlogik sowohl ein Vollbild als auch einzelne Gitterzellen
  bedienen kann, ohne Code zu duplizieren. Gitter-/Kraft-/Reibungswerte über
  mehrere Runden nach visueller Prüfung angepasst (Verrechnungen bei der
  Zellenzahl, Felder zu klein, Bewegung kaum sichtbar) -- typisches
  Trial-and-Error bei rein visuellen Parametern, siehe Verlauf im Chat.
  Vollbildmodus ergänzt (Auflösung automatisch vom Betriebssystem), Esc zum
  Beenden, da im Vollbild kein Fenster-X existiert.
- Meilenstein 3 (Stresstest) begonnen. Nutzerfrage brachte einen weiteren
  Zeno-artigen Diskretisierungsfehler zutage: `_resolve_velocity`
  (Kugel-Kugel-Kollision) hatte -- anders als `resolve_boundary` -- keine
  Ruheschwelle. Bei gestapelten Kugeln (eine liegt auf einer anderen, die
  selbst auf dem Boden ruht) drückt die Schwerkraft jeden Schritt erneut
  eine winzige Annäherungsgeschwindigkeit in den Kontakt; ohne Ruhefall
  ergab das ein endloses Jittern. Fix (analog zum Boden-Fix): unterhalb der
  Schwelle wird effektiv mit Restitution 0 aufgelöst (vollständig inelastisch
  entlang der Normalen) statt mit dem konfigurierten Wert reflektiert. Nach
  dem Fix bleibt bei Stapeln ein **beschränkter periodischer Grenzzyklus**
  (Geschwindigkeit oszilliert stabil, z.B. zwischen ca. -0.11 und +0.05
  units/s, keine Explosion, aber kein exaktes Nullwerden) -- Boden- und
  Kugel-Ruhemechanismus stoßen sich im selben Schritt gegenseitig wieder an,
  ein bekanntes Problem bei gestapelten Objekten in Echtzeit-Physik-Engines.
  Ein echter "Sleep"-Mechanismus (Einfrieren nach mehreren Schritten unter
  Schwelle) wäre der robuste Fix, aber auf Wunsch zurückgestellt: "kommt zur
  Ruhe" wird stattdessen als Geschwindigkeit unter einer kleinen Toleranz
  definiert statt exakt Null (siehe `tests/physics/test_stress.py`).
- Performance-Profiling (30 Kugeln, cProfile): ~76 Schritte/Sekunde, 85% der
  Zeit in `find_colliding_pairs` (O(n²)-Vollscan, Vector3-Objektallokationen
  pro Distanzberechnung), `deal`-Contracts vernachlässigbar (~0.2%). Auf
  Wunsch zunächst Optimierung des bestehenden Ansatzes untersucht, bevor
  über ein Spatial Grid entschieden wird.
- Nutzer-Gegenfrage zum Grenzzyklus: warum kein sauberes Nullwerden? Analyse
  ergab, dass eine exakt vertikale Kontaktnormale (Stapel exakt übereinander)
  nie horizontal ausbricht, da Schwerkraft nie eine horizontale Komponente
  einbringt -- ein stabiles, aber unrealistisches Gleichgewicht. Fix: Normale
  wird bei (nahezu) exakt vertikaler Ausrichtung leicht Richtung +x gekippt
  (`contact_normal`), analog zu echten physikalischen Systemen, die nie
  perfekt symmetrisch sind und deshalb kippen statt endlos zu jittern.
  Empirisch bestätigt (2-Kugel-Stapel kippt jetzt seitlich weg und settled).
  Dabei entdeckt: der Tilt darf NICHT auf `resolve_overlap` angewendet
  werden -- Verschieben entlang einer nicht exakt an der wahren Distanz
  ausgerichteten Normalen um den (skalaren) Overlap-Betrag verfehlt die
  Zieldistanz geometrisch, was `deal.ensure`s Postcondition
  (`OVERLAP_EPSILON=1e-9`, sehr eng) tatsächlich verletzte -- via Hypothesis
  gefunden. Sauberer Fix: `_raw_normal` (exakt, für `resolve_overlap`) von
  `contact_normal` (gekippt, nur für `_resolve_velocity`) getrennt.
  Ausführliche Fallstudie (für den Bericht, DbC-Abschnitt) in
  `docs/highlights.md`.
- Zweite Nutzer-Beobachtung: der ursprüngliche Hypothesis-Settle-Test gab
  JEDER Kugel eine unabhängige Zufallsgeschwindigkeit -- deutlich mehr
  Energie als das echte Spiel je einbringt (nur ein Schuss, Rest ruht).
  Test umgebaut: alle Kugeln ruhen, nur eine bekommt über `game.shooting.shoot`
  einen Schuss (Winkel/Stärke gefuzzt). Damit wurde der Settle-Test sowohl
  realistischer als auch praktisch testbar (vorher: Hypothesis brauchte
  wiederholt >5 Minuten zum Shrinken degenerierter Vielkugel-Fälle, die im
  echten Spiel nie vorkommen würden).
- Performance-Optimierung (vor Spatial-Grid-Entscheidung): `is_colliding`
  umgebaut auf quadrierten Distanzvergleich ohne `Vector3`-Allokation/sqrt
  (Profiling hatte das als Hauptkosten identifiziert). Ergebnis: 30 Kugeln
  von ~76 auf ~188 Schritte/Sekunde (2.7x), komfortabel über dem
  60fps-Ziel. Skalierungstest (10/20/30 Kugeln) + erneutes Profiling zeigen:
  der O(n²)-Scan bleibt Flaschenhals (44-64% der Zeit, wachsend mit n), ein
  Spatial Grid würde bei dieser Kugelanzahl aber nur noch ~1.5-2x zusätzlich
  bringen (Amdahl: der O(n)-Anteil bleibt unverändert) -- Entscheidung über
  Spatial Grid vorerst zurückgestellt.
- `scripts/stress_benchmark.py` auf dem Hauptrechner (statt Laptop) laufen
  lassen: 5260 Schritte/Sekunde bei 30 Kugeln (0.190 ms/Schritt) -- deutlich
  über dem Laptop-Wert (~188 Schritte/s). Invarianten weiterhin erfüllt
  (0 Kugeln außerhalb Feld, max. Endgeschwindigkeit 0.059).
- Meilenstein 4 (Game-Loop) begonnen. `game/level.py` (`LevelDefinition` +
  geseedete `generate_random_level`) umgesetzt: sowohl handdesignte
  baseline-Level (feste Werte) als auch Zufallslevel (eigener
  `random.Random(seed)`, rührt den globalen `random`-State nicht an) landen
  im selben Typ. `radius_for_level` leitet die Kugelgröße pro Level aus
  Massenerhaltung her (2 gleich große Kugeln mergen -> doppelte Masse ->
  Radius skaliert mit `2**(level/3)`), damit später gemergte und
  handplatzierte Kugeln gleichen Levels immer gleich groß sind.
  Anschließend `game/merge.py` (`merge_spheres`, `resolve_merges`)
  ergänzt: kombiniert massen- und impulserhaltend zwei gleich-level
  Kugeln zu einer Level+1-Kugel. Dafür `physics/engine.py::step` um einen
  optionalen `collision_filter`-Parameter erweitert (Default `None`,
  bestehende Tests unverändert grün), über den die Game-Loop
  gleich-level Paare von der Physik-Bounce-Auflösung ausnimmt, damit
  `resolve_merges` sie stattdessen übernehmen kann.
- Beim Testen nebenbei einen bestehenden, von Meilenstein 4 unabhängigen
  Bug in `test_stress.py::test_many_spheres_stay_in_bounds_and_never_explode`
  gefunden: Hypothesis fand einen Fall (4 exakt übereinanderliegende
  Kugeln, eine mit `vz=1.0`), in dem eine Kugel bis zu ~3.4e-4 unter den
  Boden sinkt -- über der mit 1e-6 sehr engen Toleranz. Per `git stash`
  bestätigt, dass der Fall identisch auch ohne die heutigen Änderungen
  auftritt, also ein latenter Randfall aus Meilenstein 3 ist, den
  Hypothesis erst jetzt zufällig fand. Auf Wunsch zurückgestellt (Fokus
  bleibt auf Meilenstein 4); Test vorerst mit `pytest.mark.xfail(strict=False)`
  markiert statt einfach entfernt, damit er als offener Punkt sichtbar
  bleibt und automatisch wieder auffällt (als "unerwartet bestanden"),
  falls der Fix mal nebenbei passiert.

## 2026-08-02
- Performance-Session zu Agenten-Laufzeit (1000-Level-Batch-Ziel), volles
  Entscheidungslog in `docs/physics_optimizations.md`. Kurzfassung: `deepcopy`
  in `simulate_shot` durch gezielten Klon ersetzt (~12%), `deal`-Contracts
  in Batch-Läufen abgeschaltet (~2-3%), Winkelauflösung/Alpha-Pruning
  bewusst abgelehnt (Combo-Scoring verhindert eine sinnvolle Schranke).
  Erster Perf-Vergleich war fehlerhaft (`git stash` mischte versehentlich
  einen unabhängigen älteren Lookahead-Stand rein) -- korrigiert durch
  isolierten Vergleich, im Doc als Lehre festgehalten.
- Beim 20-Level-Timing-Test (neues `scripts/agent_batch_timing.py`) einen
  echten Bug gefunden statt gesucht: `GreedyAgent`s Tiebreak-Fallback
  (greift bei Gain-Gleichstand) lief ohne `executor`, obwohl er bei vielen
  Ties denselben teuren 2-Ply-Sweep macht wie Lookahead -- einzelne Level
  brauchten dadurch bis zu 20s statt <1s. Nutzer-eigener Testlauf deckte
  das auf, nicht Analyse im Voraus.
- `game/interesting_levels.py` (neu): schema-agnostischer JSON-Store für
  Level, bei denen Agenten-Scores stark divergieren -- speichert nur Seed
  + Generierungsparameter (Determinismus macht Neuspeichern des Levels
  selbst unnötig).
- Combo-Ketten-Metrik (`agents/runner.py::record_playthrough`) und
  Level-Shrinking ergänzt, volles Entscheidungslog zum Shrinking in
  `docs/level_shrinking.md`. Kurzfassung: erster Ansatz (Delta-Debug mit
  Gap-Erhaltung) zu teuer (~11-13s/Level) und konnte Level durch eine
  komplett andere, bessere Agenten-Strategie "verbessern" statt sie nur zu
  verkleinern. Beim Anschauen im eigens gebauten Level-Browser
  (`rendering/level_browser.py`) fiel eine scheinbar nie getroffene Kugel
  auf, die trotzdem nicht entfernt wurde -- erste eigene Diagnose kam
  fälschlich zum Schluss, es gäbe nie unberührte Kugeln (Bug: Identitätsvergleich
  gegen die falsche Objektliste, `start_round` deep-copied). Nutzer hatte
  recht; nach Fix bestätigt, aber gezeigt, dass "unberührt vom gewählten
  Schuss" nicht "irrelevant" heißt (Entfernen kann eine andere,
  bessere Strategie freilegen). Auf Nutzer-Entscheidung durch einen
  neuen, deutlich günstigeren Ansatz ersetzt: Kugeln entfernen, die
  kein "cleverer" Agent (alles außer Random) je berührt, iterativ bis
  zum Fixpunkt -- keine Gap-Erhaltung mehr als Kriterium, ein sinkender
  Gap gilt als informativ ("Level war leichter als gedacht"), keine
  Suche nach besseren Alternativ-Strategien mehr. Alter Ansatz (`game/shrink.py`,
  zugehörige Tests, `scripts/shrink_interesting_level.py`, alte
  `data/shrunk_levels.json`) komplett gelöscht statt parallel gehalten.
- Perf-Bug in `shrink_top_levels.py` gefunden (v2 lief trotzdem "extrem
  lange"): drei der vier Playthroughs pro Level (Original-Greedy,
  Original-Lookahead, finales Shrunk-Greedy) wurden ein zweites Mal
  simuliert, obwohl `shrink_to_used_spheres` genau die schon intern
  berechnet -- verdoppelte dabei ausgerechnet Lookaheads teuren
  2-Ply-Sweep. Fix: `shrink_to_used_spheres` (`agents/runner.py`) gibt
  jetzt ein `ShrinkResult` zurück, das diese Playthroughs mitliefert,
  statt sie zu verwerfen -- kein Verhaltensunterschied, nur die
  dreifache Neuberechnung entfernt. Details in `docs/level_shrinking.md`.
- `rendering/level_compare.py` (neu) + `scripts/browse_interesting_levels.py`:
  Side-by-Side-Ansicht (pygame) für Original- vs. geshrinktes Level auf
  einer handverlesenen Seed-Liste aus `data/shrunk_levels.json` -- Auswahl
  nach Auffälligkeit (höchster Gap, größte Gap-Zunahme/-Abnahme,
  aggressivstes Shrinking, Combo-Rekord), nicht nach einer einzelnen
  Metrik sortiert.

## 2026-08-03
- `scripts/agent_batch_timing.py` / `scripts/shrink_top_levels.py` auf
  mehrere Kugelanzahlen parametrisiert (`SPHERE_COUNTS = (8, 5)`, statt
  bisher fest 10), je eigene Output-Datei
  (`data/interesting_levels_<n>b.json`, `data/shrunk_levels_<n>b.json`) --
  ein `save_run` ersetzt sein Ziel komplett, verschiedene Kugelanzahlen
  sind verschiedene Schwierigkeitsregime, keine Zeilen derselben Tabelle.
  Level-Seeds werden jetzt zufällig gezogen (`random.sample`) statt
  `range(LEVEL_COUNT)`, pro Level weiterhin einzeln gespeichert (bereits
  ausreichend für späteren Abgleich, da `generate_random_level`
  deterministisch ist). Finale interaktive Grid-Ansicht per
  `SPHERE_MERGER_NO_GRID=1` überspringbar gemacht, für unbeaufsichtigte
  Batch-Läufe -- Daten sind zu dem Zeitpunkt schon gespeichert, die
  Grid-Ansicht ist reine Sichtprüfung. Vor dem vollen 1000er-Lauf je
  Kugelanzahl ein 5-Level-Proberun gemacht (Nutzerwunsch), erst danach den
  vollen Lauf gestartet.

## 2026-08-05
- Läufe als Konfiguration statt als Skript-Konstanten: `RunConfig` +
  `RUNS` + `select_runs` in `game/interesting_levels.py` (neu), die vier
  produzierenden/lesenden Skripte (`agent_batch_timing.py`,
  `shrink_top_levels.py`, `build_dashboard_data.py`,
  `browse_batch_shrink.py`) beziehen Kugelanzahl, Schusszahl und
  Dateipfade von dort, statt je ein eigenes `SPHERE_COUNTS` und ein
  hartkodiertes `shot_count=2` zu halten. Anlass war der neue Lauf mit
  3 Schüssen: die Schusszahl gehört damit in den Dateinamen
  (`<n>b_<s>s`), die beiden bestehenden Läufe sind per `slug` auf ihre
  alten Namen (`8b`, `5b`) festgenagelt -- Umbenennen hätte nur Diff
  erzeugt (Nutzerentscheidung: nur Neues neu benennen).
  Skript-Argumente wählen einzelne Läufe aus; ohne Argument laufen alle,
  was die vorhandenen Daten der anderen Regimes überschreiben würde --
  der Grund, warum die Auswahl überhaupt existiert.
- Vor dem Start eine 30-Level-Kalibrierung gefahren, um die Laufzeit zu
  schätzen (Nutzerfrage): 1.33 s/Level -> ~22 min, tatsächlich 22.0 min
  (Batch 1041 s + Shrink 280 s). Der Lauf mit 3 Schüssen kostet Lookahead
  zwei volle 2-Ply-Sweeps statt einem, was die kleinere Kugelzahl (6
  statt 8) gerade wieder ausgleicht.
- Dashboard-Umschalter auf `name` statt `sphere_count` umgestellt und um
  die Schusszahl beschriftet -- „6 Kugeln" allein unterscheidet den neuen
  Lauf nicht mehr eindeutig von einem künftigen 6-Kugel-Lauf mit anderer
  Schusszahl.
- `scripts/long_run.py` (neu) plus `game/checkpoint.py` (neu): langer,
  unbeaufsichtigter Lauf über neun Regime (5/8/10 Kugeln × 2/3/4
  Schüsse). Drei Eigenschaften, die alle aus "läuft Stunden statt
  Minuten" folgen: (1) die Regime laufen **verschränkt** in Runden statt
  nacheinander, weil ein Abbruch sonst die späteren Regime leer ließe --
  45/30/25 % der Runde je Schusszahl; (2) jedes fertige Level wird sofort
  als JSONL-Zeile weggeschrieben, Speicher bleibt damit konstant und ein
  Abbruch kostet höchstens das laufende Level; (3) Ctrl-C und die Datei
  `data/STOP` beenden geordnet mit Finalisierung, ein gestorbener
  Worker-Pool wird neu aufgesetzt statt den Lauf zu beenden, und Windows
  wird per `SetThreadExecutionState` am Einschlafen gehindert.
- `ShotRecord` um `spheres_after` erweitert: Feldzustand nach jedem
  Schuss (x, y, level; Radius folgt aus dem Level, Geschwindigkeit ist
  nach dem Settle ~0). Nutzerwunsch, für spätere Analysen von
  Mittrunden-Stellungen. Beim Prüfen der Nutzerannahme "damit kriegen wir
  die 2-Schuss-Lösung gratis" kam heraus: nur zur Hälfte richtig --
  Schuss 1 ist bei gleichem Seed identisch (Queue-Präfix stimmt überein),
  Schuss 2 nicht, weil er in der kurzen Runde der letzte ist und auf
  Sofortgewinn zurückfällt. Aus dem gespeicherten Zustand ist er aber für
  ~1 % der Kosten nachrechenbar. In `docs/data_schema.md` festgehalten.
- `agents/base.py`: `EXECUTOR_CHUNKSIZE = 4` für beide Agenten-Sweeps,
  Random-Samples in `long_run.py` parallelisiert statt sequenziell im
  Hauptprozess. Anlass: der laufende long_run nutzte nur 44 % der 16
  Threads. Gemessen statt vermutet -- `executor.map` ohne chunksize
  verschickte bei Greedy jeden Kandidaten einzeln; der Pickle-Overhead pro
  Simulation machte den parallelen Sweep *langsamer* als denselben Sweep
  sequenziell im Aufrufer (0.089s vs. 0.062s), mit chunksize=4 dann
  0.018s. Die 20 Random-Samples liefen komplett sequenziell (0.418s),
  parallel 0.087s. Zusammen 1.10 -> 0.70 s/Level im laufenden Betrieb.
  Dazu ein `--resume`-Modus für `long_run.py`/`checkpoint.py`, damit der
  Wechsel mitten im Lauf die schon gerechneten Level nicht verwirft.
- **Langer Lauf abgeschlossen** (`long_run.py`, 2026-08-05 16:23 bis
  2026-08-06 00:07, einmal für den Optimierungswechsel unterbrochen und
  per `--resume` fortgesetzt): 26091 Level über neun Regime (5/8/10
  Kugeln × 2/3/4 Schüsse), plus die vorher separat gelaufenen 1000 Level
  von `6b_3s`. Ergebnisse nur lokal in `data/*.json` (~200 MB,
  nicht gepusht), Checkpoints in `data/checkpoints/` (gitignored).

  | Regime | Kugeln | Schüsse | Level |
  |---|---|---|---|
  | `5b` | 5 | 2 | 4050 |
  | `8b` | 8 | 2 | 4050 |
  | `10b_2s` | 10 | 2 | 3949 |
  | `5b_3s` | 5 | 3 | 2610 |
  | `8b_3s` | 8 | 3 | 2610 |
  | `10b_3s` | 10 | 3 | 2522 |
  | `6b_3s` | 6 | 3 | 1000 |
  | `5b_4s` | 5 | 4 | 2100 |
  | `8b_4s` | 8 | 4 | 2100 |
  | `10b_4s` | 10 | 4 | 2100 |

  Negative Gaps (Lookahead schlägt Greedy nicht) traten in keinem der
  12000+ 2-Schuss-Level auf, aber in 9-10 % der 3- und 4-Schuss-Level --
  bestätigt an großer Stichprobe, dass Lookaheads 2-Ply-Suche ab
  `shot_count > 2` nicht mehr bis zum Rundenende reicht und `depth_gap`
  dort keine Optimalitätsaussage mehr ist. Der `aha`-Einbruch bei mehr
  Schüssen (846 bei `5b` -> 71 bei `5b_4s`, trotz *steigendem*
  Gap-Median) bestätigt sich als überwiegend Artefakt der absoluten
  `PAYOFF_CONC_MIN`-Schwelle -- Normierung auf `1/shot_count` steht noch
  aus.
- `scripts/browse_interesting_levels.py`: Sidebar zeigt je Kategorie die
  Top `TOP_PER_CATEGORY` (=6) Level statt nur des einen extremsten --
  Nutzerwunsch ("eine Liste mit interessanten für alle Kategorien"), da
  ein Einzelbeispiel nur den Extremfall zeigt, nicht ob die Kategorie ein
  echtes Muster ist. Dabei auch einen Text-Bug behoben: die
  "Lookahead verliert"-Begründung nannte hartkodiert "3 Schüsse" statt
  der tatsächlichen `shot_count` des Laufs.
- `scripts/compare_top_gaps.py` (neu): Top-5-nach-Gap über *alle* Regime
  in einer gemeinsamen Sidebar (mit `[regime]`-Präfix), statt mehrerer
  Kategorien für ein Regime wie `browse_interesting_levels.py` -- für
  den Vergleich, wie der Gap mit Kugel-/Schusszahl skaliert.

## 2026-08-06
- `scripts/long_run.py`: Architektur umgestellt, ein Worker-Task = ein
  komplettes Level statt ein Kandidat-Winkel. Anlass: die alte
  per-Schuss-Architektur (Kandidaten-Sweep ueber den Pool verteilt,
  Barriere nach jedem Schuss/jeder Agenten-Phase) mass nur 44-53%
  CPU-Auslastung -- ein 4-Schuss-Level durchlaeuft ueber ein Dutzend
  solcher Barrieren, jede laesst den gesamten Pool stillstehen.
  `play_level_task` rechnet jetzt ein Level komplett sequenziell in
  einem Worker (`GreedyAgent`/`LookaheadAgent` faellt ohne Executor
  ohnehin auf sequenzielle Sweeps zurueck), Parallelitaet kommt aus
  vielen gleichzeitig laufenden *verschiedenen* Level statt aus dem
  Verteilen eines einzelnen. `run_workload`: rollierendes Fenster von
  `MAX_WORKERS` gleichzeitigen Level-Tasks.

  Eine erste Einschaetzung (auf Nutzerfrage zur Auslastung hin) hatte
  behauptet, das lohne sich nur bei kurzen Runden und sei bei 4 Schuessen
  ungefaehr ein Nullsummenspiel -- verifiziert durch eine Hochrechnung
  statt einer echten Messung, deshalb daraufhin erstmal auf die alte
  Architektur zurueckgesetzt. Der Nutzer hat zurecht nachgehakt ("40+
  compute bringt nicht aehnliche Beschleunigung, das kommt mir komisch
  vor"), woraufhin eine echte Messung (statt Hochrechnung) der alten
  Architektur auf `8b_4s` zeigte: 0.57 Level/s, nicht die geschaetzten
  ~0.77 -- die Hochrechnung hatte unterschaetzt, wie viele
  Synchronisationsbarrieren mit der Schusszahl mitwachsen. Echter
  Vergleich beider Architekturen auf denselben Regimen: `8b` (2 Schuss)
  1.43 -> 2.04 Level/s (+43%), `8b_4s` (4 Schuss) 0.57 -> 0.73 Level/s
  (+29%) -- Gewinn auf beiden Seiten bestaetigt, die neue Architektur
  danach erneut eingebaut. Lehre: Kapazitaetsaussagen auf hochgerechneten
  statt gemessenen Zahlen sind bei diesem Codebestand mehrfach schiefgegangen
  (siehe auch den Analyse-Draft zu `payoff_conc`) -- lieber kurz nachmessen.
- Beim Verifizieren versehentlich die echten `5b_3s`-Daten (2610 Level
  aus dem langen Lauf vom Vortag) geloescht: ein Smoke-Test verwendete
  eine `RunConfig(5, 3)` ohne eigenen `slug`, deren Name ("5b_3s") mit
  dem echten Regime kollidierte, `Checkpoint.start()` trunkiert dort
  standardmaessig. Alle anderen acht Regime sind unberuehrt (Zeilenzahlen
  gegen das Lauf-Log geprueft). Neuerhebung von `5b_3s` auf Nutzerwunsch
  zurueckgestellt, noch offen.

## 2026-08-27
- **Reduktion auf den Kern begonnen.** Anlass: der Code soll vollstaendig
  gelesen und verstanden werden, ohne Zeit in Code zu stecken, der ohnehin
  entfernt wird. Vorgeschlagene und uebernommene Reihenfolge: erst Zweck
  klaeren (welche Teile traegt der Bericht?), dann mechanisch schneiden,
  **erst dann** lesen. Begruendung: zuerst lesen verschwendet Aufwand auf
  ~40 % der Zeilen, zuerst schneiden ohne geklaerten Zweck loescht
  irgendwann das, wovon der Bericht einen Screenshot gebraucht haette.
- Messung als Entscheidungsgrundlage statt Bauchgefuehl: `rendering/` ist
  1759 Zeilen (41 % von `src/`) und **topologisches Blatt** -- kein Modul
  ausserhalb importiert es. Damit ist der Schnitt nicht nur billig,
  sondern risikofrei: er kann `physics`/`game`/`agents` nicht brechen.
  `scripts/` ist mit 2644 Zeilen mehr als halb so gross wie `src/` und
  faellt beim "ich lese das Projekt" reflexhaft unter den Tisch.
- Views auf einen reduziert (Nutzerentscheidung): behalten wird die
  Sidebar-Ansicht `rendering/level_compare.py` -- sie hat die klickbare
  Liste mit `CompareEntry.reason` ("a one-line, human-written note on why
  this seed made the list"), also genau die gewuenschte Kurzbeschreibung
  je Level. `level_browser.py` (aeltere Vor/Zurueck-Variante, null
  Sidebar), `agent_grid.py` und `grid_view.py` entfernt (765 Zeilen), dazu
  9 abhaengige Skripte und 2 Testdateien.
- `scripts/agent_batch_timing.py` ist Datenproduzent *und* nutzte
  `agent_grid`, wurde deshalb nicht geloescht sondern operiert: nur der
  `SHOW_GRID`-Block raus. Ungefaehrlich, weil `save_run(...)` im Code vor
  dem Grid-Block steht -- die Daten sind geschrieben, bevor die Anzeige
  beginnt. `_build_level` und `random_records` gehoeren zum Rechenpfad und
  blieben unangetastet.
- **Rust bleibt.** Erste Claude-Annahme war, die Extension solle mit
  entfernt werden -- Missverstaendnis; der Nutzer meinte, er werde sie
  sich nicht *ansehen*. Sie wird im Bericht erwaehnt, aber nicht
  begruendet (Python-Kurs). Unabhaengig davon war der Rust-Schnitt ohnehin
  nicht als erster Schritt vorgeschlagen worden, weil die gemessenen ~18x
  von `simulate_shot_native` genau auf dem Pfad der noch geplanten
  Datenerhebung liegen.
- Vorgabe "das Projekt muss genauso laufen wie vorher, der Kern darf sich
  nicht aendern" wurde nachgewiesen statt behauptet: Baseline vorher
  gemessen (132 Tests), nachher 129 -- die Differenz ist exakt die Zahl
  der Testfunktionen in den zwei geloeschten Testdateien (1 + 2, aus dem
  Tag verifiziert). Diff gegen `physics`/`game`/`agents`/`metrics`/`native`
  ist leer, alle 12 verbliebenen Skripte importieren sauber,
  ruff/mypy/format gruen.
- Fehler dabei: ein `git add -A` waehrend der Verifikation stagede
  versehentlich ~370 MB lokale Rohdaten aus `data/` mit (bewusst nicht im
  Repo, siehe Eintrag vom 2026-08-05). Vor dem Commit bemerkt und per
  `git restore --staged data/` zurueckgenommen -- `data/*.json` steht
  nicht in `.gitignore`, nur die Checkpoints, was solche Unfaelle
  beguenstigt.
- Tag `vor-reduktion` vor dem ersten Schnitt gesetzt, damit jeder
  entfernte Teil mit einem Befehl zurueckholbar ist.
- **Skripte durchgesehen und von 12 auf 8 reduziert** (1996 -> 1403
  Zeilen). Statt zu raten, welche ueberholt sind, wurden sie nach
  Pipeline-Stellung sortiert (Erhebung / Auswertung / Ansicht / manuell /
  Messung) -- daraus fiel die Redundanz von selbst heraus:
  `long_run.py` deckt `agent_batch_timing.py` funktional vollstaendig ab
  (gleiches `select_runs`-CLI, gleicher `interesting_path`) und shrinkt
  zusaetzlich inline mit, womit auch `shrink_top_levels.py` (der
  Nachlauf-Shrinker) seinen Zweck verliert. `demo_render.py` erklaerte
  sich im eigenen Docstring als veraltet ("No real level generation yet
  -- that's a later milestone", laengst erledigt), `demo_round.py` ist
  eine schwaechere Variante von `play_seed.py` (Zufallslevel statt eines
  echten Lauf-Seeds).
- Die drei Browse-Skripte teilen sich `level_compare` und `_build_entry`
  und unterscheiden sich nur in der Seed-Kuratierung (Kategorien je
  Regime / fm-Kollaps / Gap ueber alle Regime). Zusammenlegen auf ein
  Skript mit `--mode` waere moeglich (~200 Zeilen Duplikat), wurde aber
  auf Nutzerentscheidung verworfen: es ist genau der Screen, auf dem
  weitergearbeitet werden soll, und ein Umbau daran kostet Zeit ohne
  Erkenntnisgewinn.
- Beim Loeschen kamen zwei Dinge hoch, die vorher nicht sichtbar waren.
  Erstens zitierten **fuenf Kern-Docstrings** `agent_batch_timing.py` /
  `shrink_top_levels.py` als Schema-Quelle (`interesting_levels.py`,
  `level_metrics.py`, `runner.py`) -- reine Prosa, aber ein Verweis auf
  eine geloeschte Datei genau in den Dateien, die als naechstes gelesen
  werden sollen. Auf Nutzerentscheidung angepasst (kein Verhalten
  beruehrt, Tests/mypy unveraendert). Zweitens tragen die getrackten
  Datendateien `"agent_batch_timing.py[rust]"` bzw. `"shrink_top_levels.py"`
  im `source_script`-Feld: die geloeschten Skripte leben als
  Herkunftsangabe in den Daten weiter, weshalb `docs/data_schema.md`
  jetzt **beide** Werte dokumentiert statt den alten zu ersetzen -- die
  Dateien sind unveraendert gueltig und werden weiter gelesen.
- Trennung beim Nachziehen der Dokumentation: `docs/data_schema.md` ist
  ein *lebendes* Dokument (haelt sich laut eigener Vorgabe am Code) und
  wurde aktualisiert; `ki_log.md`, `level_shrinking.md` und
  `physics_optimizations.md` sind *datierte Verlaufsprotokolle* und
  blieben unangetastet -- sie beschreiben, was zu jenem Zeitpunkt galt,
  und nachtraeglich umzuschreiben wuerde ihren Zweck zerstoeren.
- `play_seed.py`s Docstring behauptet jetzt "gleiche Parameter wie
  long_run.py". Vor dem Schreiben geprueft statt behauptet: `FIELD`,
  `SPAWN_MARGIN`, `SPAWN` und `LEVEL_RANGE = (0, 2)` stimmen ueberein,
  6 Kugeln / 3 Schuesse ist das Regime `6b_3s` aus `RUNS`.
- Stand nach beiden Schnitten: 129 Tests gruen, ruff/format/mypy sauber,
  interrogate 81.6 % (ueber dem Nice-to-have von 80 %), alle 8
  verbliebenen Skripte importieren fehlerfrei, keine toten Verweise mehr.
- **Docstrings im Kern gekuerzt, beginnend mit `physics/`.** Messung
  vorab: der Kern hat mehr Docstring- als Code-Zeilen (1023 zu 1005).
  Groesster streichbarer Posten ist historische Rechtfertigung -- Saetze
  wie "unlike the old 3D/gravity model" oder "replaces the old 'only
  while resting on the floor' special case" erklaeren Code, der seit
  Commit `96a4d0c` nicht mehr existiert. Das gehoert in Git-Historie und
  `docs/`, nicht in einen Docstring. Erhalten bleiben Zweck, Kontrakt,
  nicht-offensichtliches *aktuelles* Verhalten und **alle Doctests** (die
  sind Tests und laufen ueber `--doctest-modules` mit).
- Kuerzen ist bei `interrogate` gratis: das Werkzeug zaehlt das
  *Vorhandensein* eines Docstrings, nicht seine Laenge -- 81.6 % blieben
  exakt gleich.
- Als Nachweis statt Behauptung, dass sich das Verhalten nicht aendert,
  ein kleines Werkzeug gebaut: AST parsen, alle Docstrings entfernen,
  `ast.dump` hashen. Gleicher Fingerabdruck vor und nach der Aenderung =
  ausfuehrbarer Code beweisbar identisch. Zweite Schranke gegen einen
  versehentlich geloeschten Doctest ist die Testzahl (129 muss 129
  bleiben), denn ein entfernter Doctest wuerde vom AST-Vergleich nicht
  erfasst -- er steckt ja im Docstring.
- Ergebnis fuer `physics/`: 430 -> 402 Zeilen (-7 %), Docstrings -19 %,
  praktisch alles davon in `engine.py` (190 -> 162, Docstrings -42 %).
  Die Schaetzung vorab lautete "-90 Zeilen" und war deutlich zu
  optimistisch. Grund: `physics/` ist mit 32-45 % Doc-Anteil der
  *schlankste* Teil des Kerns; die Masse sitzt in `game/` und `metrics/`
  (47-64 %, Extremfall `scoring.py` mit 2 Zeilen Code zu 18 Zeilen
  Docstring). Als Startpunkt wurde `physics/` gewaehlt, weil es gerade
  gemeinsam durchgegangen worden war -- nicht, weil dort am meisten zu
  holen war.
- Bei der Gelegenheit zwei tote oeffentliche Funktionen gefunden, die
  nirgends aufgerufen werden: `agents/runner.py::play_round` und
  `::record_shots` (letztere nur noch in einem Docstring *erwaehnt*).
  Entfernung steht aus, kommt in der `agents/`-Runde.
- **`game/` nachgezogen**: 1112 -> 1033 Zeilen (-7 %), Docstrings -15 %.
  Wieder unter der eigenen Schaetzung (angekuendigt waren 100-150
  Zeilen). Der Grund ist inzwischen klar und kein Ausrutscher: die
  Vorgabe "Docstrings sollen trotzdem sinnvoll sein" und das Ziel
  "auf das Noetigste" ziehen gegeneinander, und beide Runden sind bewusst
  auf der Seite von "sinnvoll" gelandet. Wer haerter kuerzen will, muss
  die *Warum*-Absaetze ganz streichen und sich darauf verlassen, dass die
  Begruendung in Git-Historie und `docs/` steht.
- Beim Lesen ein **sachlich falscher Docstring** gefunden:
  `radius_for_level` behauptete, die level-skalierte Formel
  (`base_radius * 2**(level/3)`) sei "still what `merge_spheres` computes
  from conserved mass on every merge, so merged spheres already grow
  regardless". `merge_spheres` ruft aber genau dieses
  `radius_for_level(a.level + 1)` auf, das konstant 0.5 liefert --
  gemergte Kugeln wachsen nicht. Empirisch geprueft (Level 2+2 -> 3,
  Radius 0.5 -> 0.5) statt nur gelesen. Das ist die zweite Doku-Aussage
  in diesem Durchgang, die eine laengst ersetzte Implementierung
  beschrieb; die erste war `find_colliding_pairs`.
- Ausserdem zeigten mehrere Stellen in `round.py` auf inzwischen
  geloeschten Code: der `DT`-Kommentar auf `rendering.agent_grid`,
  `ShotReplay` auf `agents.runner.record_shots` und auf "grid,
  single-level browser". Damit ist auch der tote Verweis geschlossen, der
  beim View-Schnitt bewusst stehen geblieben war, weil der Kern damals
  nicht angefasst werden durfte.
- Eine echte Doppelung entfernt: der Kommentar an
  `SETTLE_SPEED_THRESHOLD` und der Docstring von `is_settled` erklaerten
  wortgleich dasselbe.
- **`agents/` und `metrics/` abgeschlossen** (966 -> 937 Zeilen). Dabei
  die beiden toten Funktionen `play_round` und `record_shots` entfernt,
  plus den damit verwaisten `RoundState`-Import. Nutzerentscheidung
  zwischendurch: das *Warum* darf in den Docstrings bleiben, laenger ist
  nicht schlimm -- gestrichen wird nur Historie, Doppelung und
  Falschaussage. Der Kuerzungsgewinn faellt damit bewusst kleiner aus.
- **Zwei weitere veraltete Doku-Aussagen gefunden**, beide an inhaltlich
  wichtigen Stellen. `LevelMetrics.depth_gap` behauptete, der Gap sei
  "never negative in practice (checked: 0 of 2000 levels)" -- der lange
  Lauf hat aber in 9-10 % der 3- und 4-Schuss-Level negative Gaps
  gefunden. Jetzt steht dort die tatsaechliche Gueltigkeitsgrenze: bei
  2 Schuessen reicht die 2-Ply-Suche bis zum Rundenende und der Gap ist
  eine Optimalitaetsaussage, darueber nicht mehr. `PAYOFF_CONC_MIN`
  behauptete, unabhaengig vom Batch dasselbe zu bedeuten; dokumentiert
  ist jetzt, dass die absolute Schwelle laengere Runden untertaggt
  (`aha` faellt von 846 auf 71 zwischen 2- und 4-Schuss-Regime, obwohl
  der Gap-Median steigt) und die Normierung auf `1/shot_count` aussteht.
- Vierter toter Verweis: `metrics/level_metrics.py` zeigte auf
  `docs/interesting_levels.md`, das nie existiert hat.
- **Luecke im eigenen Pruefwerkzeug gefunden und geschlossen.** Der
  AST-Fingerprint meldete Aenderungen an `base.py` und `archetypes.py`,
  obwohl dort nur Docstrings angefasst wurden. Ursache: `EXECUTOR_CHUNKSIZE`
  und `PAYOFF_CONC_MIN` tragen *Attribut*-Docstrings (nackte Strings nach
  einer Zuweisung, PEP 258), die `ast.get_docstring` nicht als Docstring
  erkennt -- das Werkzeug strippte nur `body[0]`. Statt die Abweichung
  wegzuerklaeren wurde das Werkzeug korrigiert (jedes nackte
  String-Statement wird entfernt, egal an welcher Position); danach
  bestaetigte sich, dass ausser `runner.py` keine Datei einen echten
  Code-Unterschied hat. Lehre fuers Verfahren: ein Nachweiswerkzeug ist
  selbst pruefbedurftig, ein "grüner" Beweis mit falscher Annahme ist
  schlechter als gar keiner.
- Stand nach der gesamten Kern-Reduktion: 129 Tests gruen,
  ruff/format/mypy sauber, interrogate 81.4 % (leicht unter den 81.6 %
  vorher, weil die zwei entfernten Funktionen dokumentiert waren), alle
  8 Skripte importieren, und im gesamten `src/` gibt es keinen Verweis
  mehr auf geloeschten Code.
- **Physik-Durchgang, Datei fuer Datei, in Abhaengigkeitsreihenfolge**
  (`vector` -> `sphere` -> `boundary` -> `collision` -> `engine`).
  Beim Lesen von `boundary.py` faellt auf, dass sein Docstring behauptet,
  es brauche keinen Ruhekontakt-Sonderfall, weil "nothing pushes a sphere
  back into a wall between steps". Das stimmt nicht: `step` laeuft in der
  Reihenfolge Integration -> Boundary -> Kollisionen, und `resolve_overlap`
  schiebt Positionen **bedingungslos** auseinander -- auch in eine Wand
  hinein, nachdem der Boundary-Pass dieses Steps schon durch ist.
  `_resolve_velocity` hat dagegen einen `approach_speed <= 0`-Guard.
  Diese Asymmetrie erzeugt den Zustand "Kugel steckt in der Wand, bewegt
  sich aber von ihr weg", und `resolve_boundary` drehte die
  Geschwindigkeit dort um, statt zu pruefen, ob sie ueberhaupt zur Wand
  zeigt.
- Nicht behauptet, sondern nachgestellt (Kugel an der linken Wand, zweite
  rechts daneben, beide nach rechts): `A.vx` kippt in Step 2 von `+0.491`
  auf `-0.290`, obwohl A sich von der Wand wegbewegt. Nach dem Fix bleibt
  es `+0.483`. Praktische Wirkung vorher war harmlos -- wegen
  `restitution < 1` *daempfte* jeder Fehl-Flip -- also kein
  Stabilitaetsproblem, sondern eine Ungenauigkeit mit falscher Begruendung
  im Docstring.
- Fix: Richtungs-Guard pro Wand (`if vx < 0` bzw. `if vx > 0`), analog zu
  `_resolve_velocity`. **Musste doppelt landen** -- `native/.../lib.rs`
  spiegelt `resolve_boundary` eins zu eins, und `test_native_step_parity`
  vergleicht beide Backends. Erst nach `maturin develop --release` ist der
  Parity-Test aussagekraeftig; vorher lief er gegen die alte Binary und
  waere gruen geblieben, ohne die Aenderung je gesehen zu haben.
- `PhysicsConfig` validiert jetzt `friction`, `sphere_restitution` und
  `boundary_restitution` auf `[0, 1]`. Vorher haette
  `boundary_restitution = 1.5` bei jedem Wandkontakt Energie zugefuegt,
  ohne dass irgendetwas gewarnt haette. Bewusst im Config-Konstruktor
  (einmal pro Lauf, laut CLAUDE.md die Systemgrenze) und nicht in
  `resolve_boundary` (einmal pro Kugel pro Step). `not 0.0 <= v <= 1.0`
  faengt NaN gleich mit, weil jeder NaN-Vergleich falsch ist.
- Danach: 117 Tests gruen inkl. Parity gegen die neu gebaute Rust-Binary,
  ruff/format sauber, mypy unveraendert bei 1 (vorbestehend,
  `tests/game/test_level.py:104`).
- **Regressionstest nach dem Boundary-Fix, mit Entscheidung.** Statt zu
  behaupten, der Guard sei folgenlos, wurden die gespeicherten
  Shot-Sequenzen des neuesten Runs (`3b_5s_fm`, 9662 Level) mit der
  *jetzigen* Physik nachgespielt und gegen die gespeicherten Scores
  gehalten: **4 Abweichungen in 19324 Replays (0,021 %)**, betroffen sind
  4 Seeds (343316186, 302150925, 814841048, 258867417). Dass der Fix die
  Ursache ist, wurde nicht vermutet, sondern isoliert: mit der alten
  `resolve_boundary` per Monkeypatch liefert Seed 343316186 wieder die
  gespeicherten 36, mit der neuen 8 -- der Bruch sitzt in Schuss 4,
  danach laeuft die Merge-Kaskade auseinander.
- Keiner der vier Seeds ist unter den 47 kuratierten Leveln des Runs
  (Schnittmenge programmatisch geprueft, nicht per Augenschein), die
  Bericht-relevante Auswahl ist also unberuehrt.
- Entscheidung: **Datensaetze bleiben, wie sie sind.** Sie stammen damit
  aus einer Physik, die es so nicht mehr gibt -- das steht hier, statt
  stillzuschweigen. Begruendung gegen ein Neurechnen: 0,04 % der Level
  betroffen, und der Physik-Durchgang ist noch nicht durch. Kaeme jede
  weitere Aenderung mit einem eigenen Neulauf, waere der Aufwand
  vielfach; ein einziger Neulauf am Ende des Durchgangs erledigt alle
  Aenderungen auf einmal. Wer die Daten spaeter neu erzeugt, muss mit
  genau diesen vier Seeds rechnen.
