# Projekt-Setup: Sphere Merger (Hausarbeit)

## Kontext

Es existieren bereits `Projektplan.md` (Spielkonzept, MVP, Meilensteine) und
`formale_kriterien.md` (Bewertungskriterien des Moduls). Bearbeitungszeitraum ist knapp
4 Wochen (28.7.–25.8.2026). Die Note ergibt sich aus **Code + Bericht (PDF)**, bewertet
nach formalen Kriterien (Git-Historie, pyproject.toml, Tests, Type-Hints, mypy, ruff,
Doku-Coverage, Exception-Handling) und inhaltlicher Umsetzung des Plans.

Ziel dieses Setups: von Anfang an so aufsetzen, dass die formalen Kriterien "nebenbei"
erfüllt werden, statt sie am Ende nachträglich zu erfüllen — insbesondere echte,
kontinuierliche Commit-Historie und durchgängig laufende Lint/Type/Test-Tools.

Entscheidungen des Users: Remote-Repo auf **GitHub (privat)**, **Solo**-Abgabe.
Verfügbare Tools: `git` (2.36) vorhanden, `gh` CLI **nicht** installiert (GitHub-Repo
muss daher manuell auf github.com angelegt werden). Python 3.11 ist über
`py -3.11-64` (Anaconda) verfügbar und wird als Ziel-Interpreter empfohlen (Python 3.9
im PATH ist zu alt für moderne Type-Hint-Syntax `X | Y`).

**Repo-Name-Vorschlag:** `sphere-merger` (klar, matcht den Projekttitel aus dem
Projektplan, kein akademisches "Hausarbeit"-Präfix nötig — das steht ohnehin im
Bericht). Alternativen falls Kollision/Präferenz: `sphere-merger-eval` (betont den
Fokus auf Level-Evaluation) oder `rune-sphere-merger` (Bezug zum Vorbild RUNE DICE).

Tatsächlich gewähltes Repo: `sphere-merger-level-eval-EiPy26-` (GitHub, privat).

---

## 1. Git-Repo aufsetzen

1. `git init` im Projektordner.
2. `.gitignore` für Python anlegen (`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`,
   `.mypy_cache/`, `.ruff_cache/`, `.hypothesis/`, `dist/`, `*.egg-info/`, ggf.
   IDE-Ordner `.vscode/` außer einer geteilten `settings.json`).
3. Ersten Commit mit den vorhandenen Planungsdokumenten (`Projektplan.md`,
   `formale_kriterien.md`) sowie den neu angelegten Grundgerüst-Dateien (siehe Abschnitt 2).
4. Remote: User legt manuell ein leeres privates Repo auf GitHub an (kein `gh` CLI
   verfügbar); danach `git remote add origin <url>` und `git push -u origin main`.
5. Commit-Konvention: kleine, thematisch abgeschlossene Commits statt einem
   Mammut-Commit am Ende — das ist explizit Teil der formalen Kriterien
   ("nach Möglichkeit echte Commit History"). Empfehlung: Commit pro
   Produktionsmeilenstein-Teilschritt (siehe `Projektplan.md`, Abschnitt
   "Produktionsmeilensteine").

## 2. Vorab anzulegende Dateien/Dokumente

Projektstruktur (src-Layout, üblich für installierbare Python-Pakete). Das Paket wird
von Anfang an nach fachlicher Domäne unterteilt statt als eine große Datei/ein
flaches Modul — Details und Begründung dazu in Abschnitt 3 (Code-Guide):

```
eipy26_Hausarbeit/
├── .gitignore
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── Projektplan.md            (bereits vorhanden)
├── formale_kriterien.md      (bereits vorhanden)
├── docs/
│   ├── milestones.md         (Meilensteine aus Projektplan als Checkliste)
│   └── ki_log.md             (laufendes Log der KI-Nutzung für den Bericht)
├── src/
│   └── sphere_merger/
│       ├── __init__.py
│       ├── py.typed
│       ├── physics/          # Sphere-Objekt, Kollision/Overlap-Solver, Zustandsupdate
│       │   └── __init__.py
│       ├── game/              # Level-Generierung, Merge-Logik, Punkte/Rundenablauf
│       │   └── __init__.py
│       ├── agents/            # gemeinsames Agent-Interface + random/greedy/lookahead
│       │   └── __init__.py
│       ├── rendering/         # pygame Rendering/Input
│       │   └── __init__.py
│       └── metrics/          # Auswertung/Vergleich der Agenten-Ergebnisse
│           └── __init__.py
└── tests/
    ├── test_placeholder.py
    └── ...                    # später ein Testmodul pro Submodul (test_physics.py, ...)
```

Jedes Submodul bekommt erst dann eigene Dateien (`sphere.py`, `collision.py`, ...),
wenn der jeweilige Meilenstein ansteht — die leeren `__init__.py` legen jetzt nur die
Grenzen fest, damit von Anfang an klar ist, wo neuer Code hingehört.

- **README.md**: Kurzbeschreibung des Spiels (aus Projektplan übernehmen),
  Installationsanleitung (`pip install -e .`), wie man es startet, aktueller
  Stand/Status. Wird laut formalen Kriterien explizit gefordert, damit Dritte das
  Projekt lauffähig bekommen.
- **pyproject.toml**: Paketmetadaten + Dependencies (`pygame`, `pytest`, `hypothesis`,
  `mypy`, `ruff`, `interrogate`, optional `deal`) UND direkt die Tool-Konfiguration
  für `ruff`, `mypy`, `pytest`, `interrogate` als `[tool.*]`-Sektionen — so laufen
  die Checks von Anfang an mit denselben Regeln statt später nachgezogen zu werden.
- **docs/ki_log.md**: Fortlaufende Kurz-Einträge, wann/wofür KI-Unterstützung genutzt
  wurde und wo bewusst abgewichen wurde. Der Bericht verlangt explizit ein Kapitel
  "Mensch vs. KI" mit genau dieser Information — das nachträglich aus dem Gedächtnis
  zu rekonstruieren ist nach 4 Wochen unnötig fehleranfällig, ein laufendes Log ist die
  einfachere Lösung.
- **docs/milestones.md**: Die "Produktionsmeilensteine" aus `Projektplan.md` als
  abhakbare Liste, um Fortschritt sichtbar zu halten und dient später als Grundlage
  für das Bericht-Kapitel "Diskussion & Fazit" (Abweichung vom Plan).
- **tests/test_placeholder.py**: Ein einfacher lauffähiger Test gegen das leere Paket,
  damit `pytest`, `mypy`, `ruff` von Commit 1 an grün sind und nie "kaputt" waren.
- **src/sphere_merger/__init__.py**: enthält eine Beispielfunktion mit Type-Hint UND
  Doctest, damit die formale Mindestanforderung (≥1 Unit-Test, ≥1 Doctest,
  Type-Hint an mind. einer Stelle) technisch von Anfang an erfüllt ist und im Zuge
  der Entwicklung nur noch ausgebaut werden muss.

## 3. Verhaltensweisen & Code-Guide (`CLAUDE.md`)

Ein `CLAUDE.md` im Projektroot dient doppelt: als Arbeitsanweisung für Claude Code in
diesem Projekt UND als dokumentierte Konvention, auf die im Bericht ("Warum wurde die
Software so strukturiert?") verwiesen werden kann. Geplanter Inhalt:

- **Kleinschrittiges Arbeiten**: Änderungen in kleinen, in sich abgeschlossenen
  Schritten umsetzen (ein Teilschritt/Meilenstein pro Runde), nicht mehrere
  Baustellen gleichzeitig aufmachen. Nach jedem sinnvollen Schritt committen.
- **Kein ungefragtes Code-Generieren**: Claude schlägt Ansatz/Struktur vor und wartet
  auf Bestätigung, bevor größere Codeteile geschrieben werden. Code nur ohne
  Rückfrage schreiben, wenn es sich um triviale, eindeutige Fälle handelt (z.B.
  offensichtlicher Tippfehler-Fix, exakt vom User benannte Kleinigkeit). Bei allem
  mit Design-Spielraum (neue Klasse, neuer Algorithmus, Architekturentscheidung)
  erst kurz Ansatz umreißen und auf Go warten.
- **Strukturierung nach Domäne/OOP-Prinzipien**: Code wird nach fachlicher
  Zuständigkeit in Submodule aufgeteilt (`physics/`, `game/`, `agents/`,
  `rendering/`, `metrics/`, siehe Abschnitt 2), nicht nach technischer Schicht oder
  als eine große Datei. Jede Klasse hat eine klare Verantwortung (Single
  Responsibility). Ziel: Wer z.B. "das Verhalten der Kugeln anpassen" möchte, geht
  direkt zu `physics/` und hat dort schnell einen Überblick, ohne den Rest der
  Codebase lesen zu müssen. Das hält zusätzlich den Kontext für neue Claude-Code-
  Sessions klein — es muss nur das relevante Submodul geladen werden statt der
  gesamten Codebase.
- **Formatierung/Linting**: `ruff format` + `ruff check` als verbindlich, keine
  manuellen Abweichungen vom Formatter.
- **Type-Hints**: verpflichtend für neue öffentliche Funktionen/Methoden, Ziel
  `mypy` möglichst fehlerfrei (formale Vorgabe: ≤1 Fehler; Nice-to-have: `--strict`
  fehlerfrei).
- **Docstrings**: einheitlicher Stil (Google-Style vorschlagen) für alle
  öffentlichen Funktionen/Klassen, damit `interrogate`-Coverage kontinuierlich
  mitwächst (Ziel ≥20%, Nice-to-have ≥80% + Doctests je Methode).
- **Tests**: `pytest` für Unit-Tests, `hypothesis` für Property-Tests der
  Physik-Invarianten (z.B. "Geschwindigkeit nie > X", "Objekt kommt zur Ruhe"),
  Doctests für kleine, klar demonstrierbare Funktionen.
- **Determinismus**: feste Seeds, feste Reihenfolge bei Event-Solving/Kollisionen —
  das ist im Projektplan explizit als Risiko benannt (chaotisches Systemverhalten).
  Jede Änderung an der Physik-Engine muss die Determinismus-Tests weiter bestehen.
- **Exception-Handling**: Validierung an Systemgrenzen (Nutzereingaben,
  Level-/Config-Dateien), nicht überall defensiv im Kerncode; falls bewusst nicht
  behandelt, kurz im Code/Bericht begründen (ist selbst Kriterium).
- **Design-by-Contract**: optionaler Einsatz von `deal` für Invarianten
  (Score ≥ 0), Pre-/Postconditions (gültiger Schusswinkel; nach Merge eine Kugel
  weniger) — als Nice-to-have im Projektplan bereits vorgesehen.
- **Commit-Stil**: kleine, beschreibende Commits pro Teilschritt/Meilenstein statt
  seltener Großcommits. Commit-Messages sollen nachvollziehbar machen, *was* sich
  geändert hat und *warum* (insb. Plananpassungen/Kurswechsel) — viele Entscheidungen
  werden im Projektverlauf vermutlich nochmal überdacht, das soll in der Historie
  ablesbar bleiben statt verloren zu gehen.
- **Aufgaben selbständig auf Commit-Größe zuschneiden**: Wenn eine vom User
  vergebene Aufgabe größer ist, als in einen sinnvollen Commit passt, nicht alles
  auf einmal umsetzen, sondern nur den nächsten sinnvollen Teilschritt und dann
  zwischenmelden statt durchzuarbeiten.
- **Kommunikationsstil, token-sparend**: knapp und auf den Punkt, nichts
  ausschmücken. Dinge nur erwähnen, wenn wichtig/interessant; Punkte kurz
  anteasern ist ok, aber nicht von selbst vertiefen — der User fragt bei Bedarf
  gezielt nach.
- **KI-Nutzung**: bei nennenswerter KI-Beteiligung (ganze Funktion/Modul generiert
  vs. nur Boilerplate) kurzer Eintrag in `docs/ki_log.md`; hilft direkt beim
  Schreiben des Berichts-Kapitels "Code-Generierung".

## 4. Weitere Empfehlungen

- **Python-Version**: venv mit Python 3.11 (`py -3.11-64 -m venv .venv`) statt des
  im PATH stehenden 3.9, wegen moderner Type-Hint-Syntax und aktuellerer
  `pygame`/`mypy`-Kompatibilität.
- **Stresstest früh einplanen**: Projektplan benennt die Physik-Engine explizit als
  Flaschenhals — Meilenstein 3 (Stresstest) sollte nicht verschoben werden, da er
  über Spatial-Grid-Priorisierung entscheidet.
- **Eigenständigkeitserklärung**: Template dafür gehört in den Bericht (PDF), nicht
  ins Code-Repo — kein Setup-Schritt jetzt, aber als offenen Punkt für später im
  `docs/milestones.md` vermerken.
- **Keine CI vorgesehen**: für ein Solo-Uni-Projekt in 4 Wochen ist eine GitHub-Actions-
  Pipeline vermutlich mehr Aufwand als Nutzen; stattdessen lokale Checks
  (`ruff`, `mypy`, `pytest`, `interrogate`) vor jedem Commit manuell/als Routine.
  Kann bei Bedarf später nachgerüstet werden.

---

## Verifikation

Nach dem Setup:
1. `git log --oneline` zeigt den initialen Commit.
2. Im aktivierten venv: `pytest`, `ruff check .`, `ruff format --check .`,
   `mypy src`, `interrogate src` laufen alle ohne Fehler gegen das leere Grundgerüst.
3. `pip install -e .` funktioniert gemäß README-Anleitung.
