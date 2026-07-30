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
