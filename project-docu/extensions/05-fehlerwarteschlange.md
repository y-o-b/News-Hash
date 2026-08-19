# Wiederholungs- und Fehlerwarteschlange

**Status: zurückgestellt**

## Ziel

Fehlgeschlagene Artikelabrufe sollen gezielt erneut verarbeitet werden können, ohne die gesamte Quelle manuell neu zu starten.

## Möglicher Umfang

- Persistente Warteschlange für Netzwerk- und Interpretationsfehler
- Exponentielle Wiederholungen mit Obergrenze
- Dashboard-Aktion für erneuten Versuch und endgültiges Verwerfen
- Trennung zwischen vorübergehenden und dauerhaften Fehlern

## Aktueller Stand

Die Umsetzung wird zurückgestellt, bis mehr unterschiedliche Fehlerfälle bekannt sind. Für die bisher beobachteten Fehler gibt es bereits eine Fehlerbehandlung im Importpfad.

## Kommentar / Fragen

- Die Erweiterung soll erst nach einer Auswertung weiterer Fehlermöglichkeiten geplant werden.
