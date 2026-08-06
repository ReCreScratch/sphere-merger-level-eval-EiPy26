# Vollständiger Merge -- offene Aufgabe (Chat-Übergabe)

Dieses Dokument ist der Einstiegspunkt für einen neuen Chat, der diese Aufgabe
weiterführt: `Lies docs/full_merge_experiment.md und mach weiter.` reicht als
Eröffnungsnachricht.

## Idee

Nutzerhypothese: Level, die sich vollständig zu **einer einzigen Kugel**
zusammenfügen lassen, sind interessanter/lesbarer für Menschen als die
bisherigen `aha`-Level (die nur batch-relativ definiert sind). Statt das nur
zu hoffen, lässt es sich exakt erzwingen -- und danach messen, wie oft ein
Agent es in der Praxis tatsächlich schafft.

## Die Mathematik (bereits verifiziert, nicht neu herleiten)

`merge_spheres` (`src/sphere_merger/game/merge.py`) kombiniert ausschließlich
zwei gleiche Level zu einem Level höher. Ordnet man jeder Kugel den Wert
`2^level` zu, ist die Summe `total_value` über alle Kugeln, die je auf dem
Feld erscheinen (Start-Kugeln **plus** komplette Schuss-Queue), strikt
invariant -- nichts im Spiel erzeugt/zerstört/dupliziert sonst eine Kugel
(`target_score=999` ist unerreichbar, keine Out-of-Bounds-Löschung).

Daraus folgt: die kleinstmögliche Anzahl übrig bleibender Kugeln ist
`popcount(total_value)`. **Nur bei `popcount == 1` ist ein vollständiger
Merge zu einer Kugel überhaupt möglich** -- notwendig, nicht hinreichend
(Physik/Geometrie/Schuss-Reihenfolge müssen es trotzdem hinbekommen).

## Bereits umgesetzt, in `src/sphere_merger/game/level.py`

- `total_value(levels)`, `merge_popcount(levels)` -- die Kennzahlen oben.
- `generate_full_mergeable_level(...)` -- wie `generate_random_level`, aber
  garantiert `popcount == 1`. **Kein Rejection Sampling** (Nutzer wollte das
  explizit nicht) -- exakte Konstruktion durch Umkehrung von `merge_spheres`:
  ein Ziel-Level `L` wählen, dann rekursiv in genau
  `initial_sphere_count + shot_count` Blätter runterspalten (`_split_to_leaves`,
  `_feasible_target_levels`). Spalten erhält `total_value` exakt, also ist
  das Ergebnis immer korrekt, kein Fehlerfall/Retry nötig.
- `max_target_level` Default `7` (Nutzerwunsch: "ruhig bis L7 hoch").
- Verifiziert: 2000 zufällige Parameterkombinationen (3-10 Kugeln, 2-4
  Schuss), `merge_popcount == 1` in allen Fällen. `ruff`/`mypy`/Doctests grün.
- **Stand: noch nicht committet** -- `git status` zeigt `level.py` als
  modifiziert. Erster Schritt im neuen Chat: reviewen und committen.

## Ebenfalls vorhanden, aber nur ein Wegwerf-Demo

`scripts/demo_find_full_merge_live.py` -- pygame-Live-Suche (6 Kugeln, 2
Schuss), bricht beim ersten Treffer ab, **speichert nichts** außer dem einen
Treffer auf der Konsole. Bei einem Testlauf mit 10000 Versuchen wurde noch
kein Treffer gefunden (Suche wurde manuell abgebrochen, nicht ausgewertet).
Für die eigentliche Messung (Prozentsatz) reicht dieses Skript nicht -- siehe
"Nächste Schritte".

## Wichtige Design-Entscheidungen aus dem vorherigen Chat (nicht neu diskutieren)

- **2 Schuss zuerst.** `LookaheadAgent`s 2-Ply-Suche ist nur bei
  `shot_count=2` nachweislich nahe-optimal (siehe `docs/data_schema.md`,
  `docs/ki_log.md`: negative Gaps traten bei 12000+ 2-Schuss-Leveln nie auf,
  bei 3/4 Schuss in ~9-10%). "Lookahead findet keinen vollen Merge" heißt bei
  mehr Schüssen nicht "unmöglich", sondern könnte auch "Lookahead zu
  kurzsichtig" heißen -- Prozentsätze dort sind **Untergrenzen**, keine
  Erreichbarkeits-Quote. Erst 2 Schuss sauber messen, 3/4 Schuss separat mit
  diesem Vorbehalt.
- **Architektur für große Läufe:** `scripts/long_run.py` nutzt die
  per-Level-Task-Architektur (ein Worker-Task = ein komplettes Level, nicht
  ein Kandidat-Winkel) -- echt gemessen +43%/+29% Durchsatz gegenüber der
  älteren Barriere-pro-Schuss-Variante. **Nicht zurückbauen.**
- **Checkpoint-Namenskollisionen sind gefährlich:** ein Smoke-Test hatte
  versehentlich die echten `5b_3s`-Daten (2610 Level) überschrieben, weil
  eine Test-`RunConfig` ohne `slug` denselben Namen wie ein echtes Regime
  erzeugte (`Checkpoint.start()` trunkiert standardmäßig). Für jeden
  Testlauf **immer** einen eindeutigen `slug` verwenden, der garantiert mit
  keinem Eintrag in `RUNS` kollidiert (z.B. Präfix `_test_`). `5b_3s` ist
  bis heute nicht neu erhoben -- separates offenes Thema, nicht Teil dieser
  Aufgabe, aber beim Wählen von Regime-Namen im Hinterkopf behalten.

## Vorschlag für die nächsten Schritte (nicht blind umsetzen -- kurz Ansatz nennen, Go abwarten, wie im Projekt üblich)

1. `generate_full_mergeable_level` committen (nach Review).
2. Entscheiden, wie es in die `RunConfig`/`long_run.py`-Pipeline
   eingebunden wird -- z.B. neues Feld `RunConfig.full_mergeable: bool`, das
   `play_level_task` zwischen den beiden Generatoren umschalten lässt.
   Vermutlich eigene neue Regime-Namen statt die bestehenden neun zu
   überschreiben.
3. Entscheiden was geloggt wird: die Kollaps-auf-1-Kugel-Prüfung ist aus den
   ohnehin gespeicherten `lookahead_states`/`greedy_states` des letzten
   Schusses ablesbar (`len(states[-1]) == 1`) -- eventuell trotzdem ein
   explizites `merge_popcount`-Feld ergänzen, günstig und für spätere
   Auswertung bequemer.
4. Kleiner Kalibrierungslauf vor jedem größeren (Muster aus dem letzten
   Chat: Zeit/Level und Trefferquote grob abschätzen, bevor unbeaufsichtigt
   gestartet wird).
5. Erst danach ein richtiger, geloggter Lauf (nicht das Wegwerf-Demo-Skript)
   -- mit STOP-Datei/Resume wie gehabt, vorher an einem winzigen Sample
   verifiziert.
6. Auswertung: Prozentsatz „popcount==1 UND Agent erreicht 1 Kugel", pro
   Schusszahl getrennt, mit dem Lookahead-Vorbehalt oben.
