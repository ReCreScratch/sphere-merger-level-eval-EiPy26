# Highlights

Besondere Ereignisse, Erkenntnisse und Entscheidungen, die über den normalen
`docs/ki_log.md`-Eintrag hinaus für den Bericht relevant sein könnten — hier
ausführlicher festgehalten, statt im laufenden KI-Log unterzugehen. Neue
Einträge oben anhängen.

---

## 2026-08-02 — Coding Agent schlug Rust/C++ nicht von sich aus vor

Kontext: `docs/physics_optimizations.md`, Performance-Session zur
Agenten-Laufzeit.

### Was ist passiert

Auf die offene Frage "was sind die größten Bottlenecks und Hebel für die
Agenten-Performance?" identifizierte der Coding Agent mehrere Hebel
(Winkelauflösung, `deepcopy`-Ersatz, `deal`-Contracts abschalten,
Executor-Pooling, Alpha-Pruning) -- alle innerhalb der bestehenden
Python-Architektur. Erst auf die explizite Nutzerfrage "ist es möglich,
die Simulation auf der GPU laufen zu lassen, oder die Physik auf C++/Rust
umzuschreiben?" wurde diese Option überhaupt diskutiert -- und stellte
sich dann als der mit Abstand größte Hebel heraus (~18-90x, gegenüber
niedrigen einstelligen Prozentgewinnen der zuvor selbst vorgeschlagenen
Optimierungen).

### Warum bemerkenswert

Die eigene Bottleneck-Analyse des Agents blieb an der Grenze der
bestehenden Implementierung stehen -- optimiert wurde *innerhalb* der
gegebenen Sprache/Architektur, nicht die Sprache/Architektur selbst als
Stellschraube in Betracht gezogen. Der eigentlich wirksamste Hebel kam
nur zustande, weil ein Mensch explizit nach einer radikaleren Option
gefragt hat.

### Mögliche Erklärung

Naheliegend: ein Sprachwechsel ist ein großer, teurer, schwer
rückgängig zu machender Schritt (neues Toolchain, doppelte
Implementierung, neue Korrektheits-Infrastruktur) -- genau die Art
Vorschlag, die ein Agent von sich aus eher zurückhält, wenn die Frage
offen nach "Hebeln" statt nach "was auch immer nötig ist" gestellt wird.
Die selbst vorgeschlagenen Optimierungen waren durchweg klein, reversibel
und passten zum "kleine Schritte"-Arbeitsstil dieses Projekts -- ein
Sprachwechsel passt strukturell nicht in dieses Muster, selbst wenn er in
der Sache der bei weitem wirksamere Hebel gewesen wäre.

---

## 2026-07-30 — `deal`-Contract fängt echten Bug (Meilenstein 3, Stresstest)

Kontext: `docs/ki_log.md`, Commit `d16bf46`.

### Was ist passiert

Beim Beheben des Stapel-Jitter-Problems (siehe `ki_log.md`) wurde die
Kontaktnormale zwischen zwei Kugeln bei (nahezu) exakt vertikaler Ausrichtung
absichtlich leicht Richtung +x gekippt (`contact_normal` in `collision.py`),
damit Schwerkraft-getriebene Stapel seitlich ausbrechen können, statt in
einem stabilen, unrealistischen Gleichgewicht zu jittern.

Diese gekippte Normale wurde zunächst sowohl vom Geschwindigkeits-Solver
(`_resolve_velocity`) als auch vom Overlap-Solver (`resolve_overlap`)
verwendet. `resolve_overlap` hat aber eine Postcondition:

```python
@deal.ensure(lambda a, b, result: distance(a, b) >= a.radius + b.radius - OVERLAP_EPSILON)
def resolve_overlap(a: Sphere, b: Sphere) -> None: ...
```

`OVERLAP_EPSILON = 1e-9` — bewusst sehr eng, weil "nach dem Solver berühren
sich die Kugeln gerade noch/nicht mehr" eine exakte geometrische Garantie
sein soll, keine ungefähre.

Ein Hypothesis-generierter Testfall (Stresstest mit einem einzelnen Schuss,
vier Kugeln, u.a. eine Kollision mit größerem Overlap ~0.043) ließ den Test
mit `deal.PostContractError` abbrechen: nach `resolve_overlap` betrug der
Abstand 0.83331291 statt der geforderten 0.83333333 — eine Abweichung von
ca. 2e-5, weit über der 1e-9-Toleranz.

### Ursache

Der Overlap-Betrag (`overlap = radius_sum - distance`) ist ein **Skalar**,
berechnet entlang der **wahren** Verbindungsachse zweier Kugelmittelpunkte.
Verschiebt man beide Kugeln stattdessen entlang einer **gekippten** Normalen
um genau diesen Skalarbetrag, landet man geometrisch nicht mehr exakt auf
`radius_sum` — der Fehler wächst mit dem Kippwinkel und mit der Größe des
Overlaps. Bei kleinem Overlap (frühere Testfälle) war der Fehler zu klein,
um die Toleranz zu verletzen; bei diesem Fall (größerer Overlap) nicht mehr.

### Fix

`_raw_normal` (exakte Verbindungsachse, keine Kippung) von `contact_normal`
(gekippt, nur für den Geschwindigkeits-Solver) getrennt. `resolve_overlap`
nutzt jetzt ausschließlich `_raw_normal` — bleibt damit geometrisch exakt,
wie vor der Kipp-Änderung. Die Symmetriebrechung wirkt weiterhin, aber nur
über die Geschwindigkeit (die sich über mehrere Schritte in eine seitliche
Positionsänderung überträgt), nicht über einen einzelnen Positionssprung.

### Warum war das eine sinnvolle Anwendung von Design-by-Contract

- **Die Contract-Bedingung war die eigentliche Spezifikation der Funktion.**
  `resolve_overlap`s ganzer Zweck ist "danach überlappen sich die Kugeln
  nicht mehr" — das als `@deal.ensure` zu formulieren heißt, die Funktion
  gegen ihre eigene Daseinsberechtigung zu prüfen, nicht gegen einen
  Nebenaspekt.
- **Der Bug wäre ohne Contract wahrscheinlich unbemerkt geblieben.** Eine
  Abweichung von 2e-5 Einheiten ist optisch/im Rendering nicht sichtbar und
  hätte keinen der bestehenden Tests ausgelöst (weder die
  Grenzen-Invariante noch die Geschwindigkeits-Sanity-Prüfung prüfen
  "überlappen sich zwei Kugeln nach der Auflösung noch"). Es wäre eine
  stille numerische Drift geblieben, die sich erst viel später — z.B. als
  unerklärliches Ineinanderrutschen von Kugeln nach vielen Kollisionen —
  bemerkbar gemacht hätte, und dann kaum auf diese eine Zeile
  zurückzuführen gewesen wäre.
- **Contract + Hypothesis zusammen ergaben einen automatischen
  Bug-Finder.** Der eigentliche Test (`test_single_shot_eventually_settles`)
  prüft nur "kommt zur Ruhe" am Ende — nichts darin hätte diesen Bug
  explizit gesucht. Erst weil `resolve_overlap` selbst bei **jedem** Aufruf
  innerhalb der 700 Simulationsschritte gegen ihre Postcondition geprüft
  wird, ist der Fehler exakt an der Stelle aufgeflogen, an der er entstand
  — mit exakten Eingabewerten (dank Hypothesis-Shrinking), nicht als vages
  Endergebnis-Symptom.

### Hätte man es besser machen können?

- **Ja, vermeidbar durch sauberere Trennung von Anfang an.** Hätte
  `_raw_normal`/`contact_normal` von Beginn an als zwei getrennte Funktionen
  mit unterschiedlicher Garantie existiert (statt eine Funktion für zwei
  Zwecke wiederzuverwenden), wäre der Bug nie entstanden. Das ist aber genau
  der Punkt: der Contract hat nicht verhindert, dass der Fehler geschrieben
  wurde — er hat verhindert, dass er unbemerkt blieb. Design-by-Contract
  ersetzt kein sauberes Design, ist aber ein Sicherheitsnetz für genau die
  Fälle, in denen man (oder eine KI) eine Funktion leicht außerhalb ihrer
  eigentlichen Garantie wiederverwendet.
- **Toleranz lockern wäre der falsche Fix gewesen.** `OVERLAP_EPSILON` auf
  z.B. 1e-4 hochzusetzen hätte den Fehler kaschiert statt behoben und die
  Aussagekraft des Contracts für zukünftige echte Bugs geschwächt. Die
  richtige Reaktion auf eine Contract-Verletzung ist fast immer, den Code an
  die Spezifikation anzupassen, nicht die Spezifikation an den Code.
- **Ohne `deal`, nur mit Hypothesis:** hätte man den Bug vermutlich auch
  gefunden, aber erst, wenn man explizit einen Test "keine zwei Kugeln
  überlappen sich nach `resolve_overlap`" geschrieben hätte — was man erst
  schreibt, wenn man den Bug schon vermutet. Der Contract macht diese
  Prüfung implizit bei jedem Aufruf, ganz ohne dass man an genau diesen
  Testfall gedacht haben muss.
