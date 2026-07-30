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
