Level Evaluation - Sphere Merger
---------------------------------------------------------------------------------

Sphere Merger ist ein Spiel, bei dem man durch geschicktes Schießen einer Kugel
andere so anstoßen muss, dass zwei gleiche Kugeln sich berühren und verschmelzen.
Man kann sich das so ähnlich wie Billard vorstellen, nur dass man versucht,
möglichst viele Verschmelzungen über 3 Runden zu erzielen und Punkte zu sammeln.
Die Gameplay-Elemente sind fast eins zu eins von dem Spiel RUNE DICE übernommen.
Hauptbestandteil des Projektes soll dabei sein, die zufällig generierten Level
automatisch zu charakterisieren.
Ist es ein schwieriges Level oder kann man sehr einfach viele Punkte sammeln?
Gibt es nur eine gute Strategie oder mehrere? Muss man sehr genau zielen oder
hat man Spielraum? Der Antwort auf diese Frage soll sich mit systematischem Auswerten 
durch verschiedene Spieleragenten genähert werden.

---------------------------------------------------------------------------------

Verwendete Python Pakete:

- pygame            - Fenster, Rendering, Input
- random	    - Zufallszahlen generieren
- math		    - Matheoperationen
- pytest/hypothesis   - Tests	
- (json)	    - speichern/laden

---------------------------------------------------------------------------------

MVP:

- Random generiertes Spielfeld (mit maximal 20 Sphären)
- (headless) Physik-Engine (3D)
	- Kollisionserkennung und Overlap-Solver
	- Berechnung von Geschwindigkeit und Richtung bei Kollision
	- Berechnung von Schwerkraft und Reibung
	- Objekte werden als Kugeln repräsentiert
- Merge-Logik: gleiche Level + nahe genug
    	beide Kugeln verschwinden, neue Kugel (Level+1) erscheint mit der
    	kombinierten Restgeschwindigkeit und hüpft weiter
- Punktesystem: Punkte durch Merges und ggf. Multiplier; Partie endet bei Zielpunktzahl
- Gameover wenn Anzahl an Slingshots aufgebraucht
- simulieren vorgegebener Spielparameter (Kugelpositionen, Schusswinkel/ -geschwindigkeit) 
- Minimal-UI: simples Rendern der Physik-Simulation
- 3 Agenten, die das Spiel selbstständig spielen können (per Winkelsweep):
	1. random Züge
	2. greedy den nächstbesten Zug
	3. vorausschauend die beste Option aus den nächsten beiden Zügen
- Metrik daraus ableiten:
	- random vs. greedy Punktzahl (Schwierigkeitsmaß)
	- greedy vs. vorausschauend Punktzahl (gibt es clevere Lösungen)
	- machen kleine Winkeländerungen einen großen Unterschied? (Levelstabilität)
	- usw.
- 3 manuell designte baseline-Level
	- Lösung und Zielpunktzahl

Der MVP sollte eine Runde (Kugeln schießen, Mergen und Punkte sammeln, Gewinnen/Verlieren)
abbilden und die Agenten finden mindestens so gute Lösungen wie für die baseline-Level 
konzipiert. Dabei soll der vorausschauende Agent mindestens die Zielpunktzahl erreichen
und der random Agent (im Schnitt) deutlich darunter bleiben.
Außerdem muss die Simulation immer dasselbe Ergebnis liefern und die Agenten dieselbe
Strategie bei mehrmaligen Ausführen finden.
---------------------------------------------------------------------------------

Nice-to-haves:

- MAP-Elites Verfahren basierend auf Level Charakterisierung
- Spatial Grid für Kollisionserkennung
- Level Editor
- Extra Merge Ereignisse:
	- Wenn Sphären kombiniert werden, alle drumrum liegenden weggestoßen
	- usw.
- VFX und SFX
- Vergleich mehrerer Spielmodi/-anpassungen

---------------------------------------------------------------------------------

pytest/hypothesis   - Tests
cProfile/SnakeViz   - Performance Analyse
(mypy)              - statische Typprüfung (wahrscheinlich sehr überschaubar)
pyproject.toml      - Paketdefinition
deal		    - Invarianten (Score nicht negativ,...)
		    - Preconditions (Abschusswinkel gültig,...)
		    - Postconditions (Nach merge eine Kugel weniger,...)
IDE: VS Code mit    - ruff
		    - Pylance
		    - Claude Code

---------------------------------------------------------------------------------

Offene Entscheidungen und ihre Grundlagen:

Die Physik-Engine ist der Flaschenhals des Projektes. 
Ein früher Stresstest kann helfen zu entscheiden, ob man früh Optimierungen priorisieren
muss und ein Spatial Grid z.B. notwendig und nicht nur nice-to-have ist.

Dabei ist Determinismus sehr wichtig. Das Spiel hat einen sehr chaotischen Charakter,
was zu Problemen führen kann. Beim Stresstest muss auch das beobachtet werden und
ggf. Anpassungen/Vereinfachungen der Physik-Engine vorgenommen werden.
(Diskretisierung von Werten, feste Reihenfolge von Ereignis-Solving, usw.)

Winkelsweep Auflösung muss nach Performance gerichtet werden und ggf. gröber eingestellt 
werden, falls die Simulation zu langsam ist.

---------------------------------------------------------------------------------

Produktionsmeilensteine:
  
  1. erste Physics-Engine Iteration:
	- bekommt einen Physics-Zustand und berechnet nächsten Zustand
		- Geschwindigkeit Solver
		- Overlap Solver
		- (Kugel-)Kollisionserkennung
		- Kräfteübertragung
  2. Einfache Objekt Klasse + Rendern an beliebiger Stelle
  3. Physics Test + Stresstest (kleines Feld und 30 Kugeln, eigener Laptop):
	- Eigenschaften festlegen, die nicht verletzt werden dürfen
		- Geschwindigkeit nie > X
		- Objekte nie außerhalb Spielfeld
		- Objekt kommt nach X Sekunden zum Stillstand
	- randomisiert testen, ob diese Eigenschaften immer erfüllt sind
	- Render + Simulation laufen lassen, subjektiv einschätzen ggf. MVP überarbeiten.
  (X. Überarbeitung der Physics Engine und Designs
	- nur Kugeln updaten, die sich bewegen
	- Spatial Grid
	- weniger Kugeln
	- ...) 	
  4. Game loop mit Kugelschuss und Interaktion
  	- zufällig generiertes Level
	- Merge Logik hinzufügen
	- Punkte und Sieg-/Niederlagebedingung
	- kleinere Gameplaydesign Anpassungen
	- Simulation einer Runde  
  5. 3 baseline-Level designen
  6. 3 Agenten implementieren und baseline-Level spielen lassen
  7. Metriken errechnen und auswerten

--------------------------------------------------------------------------------

Der Erfolg des Projektes hängt vor allem vom Design des Spiels ab und weniger
von der Implementierung selber. Mir ist noch unklar, ob man mit diesem Verfahren 
für das Spiel überhaupt "sinnvolle" Ergebnisse finden kann.
	- Die Agenten Scores charakterisieren die baseline-Level nicht richtig
	- wie diskretisiere ich am besten
	- passe ich Gameplayelemente an
	- die Physik-Simulation ist zu langsam für vorausschauende Suche

Ein Hauptteil der Zeit wird in Parametertuning und Gamedesignanpassungen 
fließen.

Wirklich spannend wird das Projekt erst nach Erreichen des MVPs. Ich kann schwer ein-
schätzen, wie schnell ich in der Implementierung mit KI-Unterstützung voran komme und
habe den MVP eher etwas kleiner geplant, als ich gerne tatsächlich erreichen würde.



