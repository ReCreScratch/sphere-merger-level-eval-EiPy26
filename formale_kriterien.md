Die Note für das Modul wird über die eingereichte Hausarbeit gebildet. Dazu wurde vorab eine Projektskizze eingesammelt und die Hausarbeit besteht aus einem Programmierprojekt (Quelltext) sowie einem Projektbericht (PDF).

Geplanter Bearbeitungszeitraum: 4 Wochen, z.B. ca. 28.7. bis 25.8. oder auch 1-2 Wochen später.

Wir bewerten den Programmcode und den Bericht anhand formaler Kriterien und bewerten außerdem, wie viel, wie gut der Plan inhaltlich umgesetzt und beschrieben wurde.

Dabei bekommt eine 2,0 wer die formalen Kriterien im Wesentlichen knapp umgesetzt hat und die in der Projektskizze beschriebene Minimalanforderung ebefalls knapp umgesetzt hat. Wer Teile des ursprünglichen Plans nicht umsetzt, obwohl das möglich gewesen wäre, oder auch gröbere Fehler in der Programmlogik o.ä. hat, kann entsprechend auch leicht eine 3,0 bekommen auch wenn die formalen Kriterien erfüllt sind. Bei Nichterfüllen der formalen Kriterien ist es leicht möglich, durchzufallen, oder aber (bei nur geringen Verstößen und einer sonst guten Arbeit) nur eine 4,0 zu bekommen. Wenn das Projekt die Minimalanforderungen, die geplant waren, erfüllt, aber insgesamt einen sehr geringen Umfang aufweist, kann auch das zu einer 4,0 führen (wenngleich wir das im Vorfeld durch unsere intensive Diskussion der Projektskizzen weitgehend vermieden haben sollten).

Eine 1,0 gibt es, wenn über die Erfüllung der formalen Kriterien und der selbst gesetzten Mindestanforderungen hinaus erfolgreich gearbeitet wurde.

Formale Kriterien Code
Alles ist in einem Git Repository, nach Möglichkeit echte Commit History.

Projekt kann bei anderen durch pyproject.toml und eventuellen Installation-guides in einer README.md lauffähig gemacht werden

Es gibt mindestens einen Unit Test und mindestens einen Doctest (die auch nicht fehlschlagen).

es wurde Exception-Handling betrieben oder begründet, warum nicht notwendig

Type-Hints wurden genutzt an mindestens einer Stelle

Beim Ausführen des Type Checkers mypy werden keine oder höchstens ein Fehler angezeigt

Code-Formatierung enspricht einem Style-Guide

der Linter ruff zeigt keine oder einen Hinweise/ Fehler an

Beim Ausführen des Formatters ruff gibt es keine Änderungen mehr oder höchstens ein-zwei sehr kleine

Interrogate zeigt an, dass mindestens 20% des Codes dokumentiert ist

Projekt enthält eine pyproject.toml, in der alle benötigten Abhängigkeiten erfasst werden

auch falsche Nutzereingaben werden behandelt und führen nicht zum Absturz des Programms

Nice-to-have

Alle Variablen und Methoden tragen vollständige Typeninformationen, sodass mypy --strict keine Fehler anzeigt

Beim Ausführen des Linters ruff gibt es keine Warnhinweise

Interrogate zeigt an, dass mindestens 80% des Codes dokumentiert ist und nahezu jede Methode trägt einen Doctest

Auseinandersetzung mit der Möglichkeit, Code von LLMs/Agenten generieren zu lassen

Einsatz von Design-by-Contract oder verwandten Techniken oder auch generell Einsatz der in der Vorlesung (im Skript) besprochenen Techniken wie z.B. auch Profiling.

Formale Kriterien Bericht
Dateiname Matrikelnummer_XYZ.pdf mit frei wählbar XYZ (darf Name, Projekttitel o.ä. sein). Bei Teamabgabe beide Matrikelnummern mit “_” getrennt im Dateinamen aufführen.

Seitenzahl 2-12, ideal 6-10, aber Anhang (Appendix) erlaubt. Deckblatt nicht mitgezählt.

Zitierweise (falls zitiert wird): einheitlich, am liebsten [Abckey26] oder [n] im Text. In der Bibliographie entweder nach Zitierreihenfolge oder Erscheinungsjahr.

Quelltext im Bericht verlinken, wenn öffentlich (z.B. GitHub oder Uni-Gitlab), ansonsten vorab in Sciebo-Uploadfolder ein ZIP hochladen.

PDF sollte nicht größer als 20 MB sein.

Eigenständigkeitserklärung (die darauf verweist, dass nur genau die Werkzeuge genutzt wurden, die im Bericht auch erwähnt werden; insb. soll im weiteren Text für KI-Werkzeuge spezifisch der Umfang der Nutzung erklärt werden).

Tipps zum Schreiben des Projektberichts:
Fangen Sie direkt damit an, nicht erst, wenn Sie etwas programmiert haben.

Fassen Sie sich kurz und vermeiden Sie Adjektive, die Sie nicht begründen können (typisches LLM-Sprech).

Begründen Sie Ihre Entscheidungen (ggf. geben Sie zu, dass Sie willkürlich etwas ausgewählt haben).

Ordnen Sie ein, was leicht ging und was schwer fiel.

Vermeiden Sie es, den Code Zeile für Zeile nachzuerzählen. Erklären Sie stattdessen konzeptionelle Entscheidungen, die Programmlogik und den Umgang mit spezifischen Datenstrukturen.

Ergebnisse visualisieren: Nutzen Sie Outputs, Plots oder Screenshots aus dem Programm, um die Funktionalität im Bericht zu belegen.

Formale Kriterien nochmal lesen und prüfen, ob Code und Bericht diese erfüllen.

Mögliche Gliederung
Einleitung

Motivation,

Zielsetzung (Variante der Projektskizze)

Theoretische Grundlagen & Werkzeuge

Technologien,

Bibliotheken,

Welche Pakete/Bibliotheken kamen zum Einsatz?

Mensch vs. KI: Die Rolle von AI Assistance

Konzept & Implementierung

Programmstruktur,

Kernlogik,

Datenverarbeitung

Warum so?

Warum wurde die Software genau so strukturiert (z. B. Wahl bestimmter Entwurfsmuster, OOP-Strukturen oder funktionaler Ansätze)? Welche Alternativen wurden verworfen und warum?

KI-Konsultation bei Design-Entscheidungen: Wurde die KI bereits bei der Planung und Architektur des Projekts um Rat gefragt? Wenn ja, welche Vorschläge der KI wurden übernommen und wo wurde bewusst von der KI-Empfehlung abgewichen, weil menschliche Intuition/Logik besser passte?

Code-Generierung (Was wurde wie programmiert?):

KI-generiert: Welche Module, Funktionen oder Tests wurden maßgeblich mit KI-Unterstützung (z. B. ChatGPT, Copilot) erstellt? Warum war hier der KI-Einsatz sinnvoll (z. B. Boilerplate-Code, Standard-Algorithmen, Regex)?

Selbst programmiert: Welche Kernlogiken, komplexen Workarounds oder spezifischen Features wurden komplett selbst geschrieben? Warum war hier die eigene Programmierleistung notwendig (z. B. weil die KI den Kontext nicht verstand oder zu fehlerhaftem Code neigte)?

Prompt-Engineering & Iteration: Wie sah die Zusammenarbeit mit der KI aus? Wurde Code blind übernommen oder gab es kritische Iterationsschleifen, in denen KI-Fehler (Halluzinationen, veraltete Syntax) manuell korrigiert werden mussten?

Ergebnisse

Funktionsnachweis,

Beispiel-Durchlauf

Diskussion & Fazit

Inwiefern wurde das Ziel erreicht?

Herausforderungen,

Kritische Reflexion,

Abweichung vom ursprünglichen (Implementierungs)Plan?

Kritische Würdigung: Was lief gut, wo gab es unerwartete Probleme (entweder technischer Natur oder in der Zusammenarbeit mit der KI)? Was würde man beim nächsten Mal anders machen?

Ausblick (darf auch subjektiv sein)

Literatur- & Quellenverzeichnis

falls etwas zitierfähiges genutzt wurde (sonst kann das weg)

Anhang (wenn etwas zu lang für den Haupttext ist)

Ggf. Bedienungsanleitung,

ausgewählte Code-Snippets (nichts länger als eine Seite)