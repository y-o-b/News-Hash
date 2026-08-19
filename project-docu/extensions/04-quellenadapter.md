# Erweiterte Quellenadapter

**Status: nach Beispieldaten weiterverfolgen**

## Ziel

Weitere Nachrichtenquellen sollen ohne Änderungen an der allgemeinen Importlogik angebunden werden können. Der Daemon soll Änderungen oder ungültige Antworten einer Quelle als Fehler melden, ohne die Verarbeitung der übrigen Quellen zu stoppen.

## Möglicher Umfang

- Adapter für weitere Feed-Formate oder APIs
- Quellenspezifische Extraktion von Artikeltext, Bildern und Veröffentlichungszeitpunkten
- Testdatensätze pro Adapter ohne Netzwerkzugriff

## Offene Fragen

- Soll eine Quelle mehrere Fallback-Adapter besitzen dürfen?
- Wie werden Änderungen an einer externen Quelle erkannt und als Fehler versioniert?
- Sollen Adapter als Python-Code oder als deklarative Konfiguration definiert werden?

## Kommentar / Fragen

- Für weitere Formate und APIs werden zunächst konkrete Beispielquellen und repräsentative Testdaten benötigt. Erst danach soll die Adapter-Schnittstelle festgelegt werden.
