# Persistentes Betriebs- und Fehlerprotokoll

**Status: nicht geplant**

## Ziel

Ein persistentes Betriebs- und Fehlerprotokoll ist derzeit nicht notwendig. Fehler werden nach `stderr` geschrieben; in einem Docker-Betrieb übernimmt Docker die Protokollierung.

## Möglicher Umfang

- Weiterhin flüchtige Anzeige der Laufzeitfehler im Dashboard
- Nutzung des Container- oder Prozess-Logs für dauerhafte Betriebsprotokolle

## Aktueller Stand

Eine spätere Neubewertung ist nur erforderlich, wenn die externe Logverwaltung nicht ausreicht.

## Kommentar / Fragen

- Nicht erforderlich: Fehler werden über `stderr` ausgegeben; im Docker-Betrieb kann Docker diese Ausgaben übernehmen.
