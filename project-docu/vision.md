# Vision

## Problem

Nachrichten aus einer externen Quelle sollen automatisch erfasst, dauerhaft nachvollziehbar gespeichert und später unverändert auswertbar sein.

## Herausforderungen

Die RSS-Feeds enthalten in der Regel keine vollständigen Nachrichten; daher müssen die eigentlichen Inhalte je nach Quelle als vollständiger Text oder als Screenshot nachgeladen werden.

## Zielbild

Das Projekt liest regelmäßig Nachrichten aus konfigurierten JSON- und XML-Feeds ein und speichert jede Nachricht in einer internen unveränderlichen Kette von Datensätzen.

Die Kette dient als nachvollziehbares Archiv mit historischer Integrität.
Ein integriertes Dashboard macht Quellen, Kennzahlen, Meldungen, gespeicherte Bilder und Laufzeitinformationen direkt zugänglich.
Tägliche Hash-Manifeste werden zusätzlich öffentlich mit OpenTimestamps verankert, ohne Nachrichteninhalte zu veröffentlichen.

## Erfolgskriterien

- Der Feed wird regelmäßig abgefragt.
- Neue Nachrichten werden eindeutig erfasst.
- Bereits gespeicherte Datensätze bleiben unverändert.
- Das Dashboard zeigt Daten quellenbezogen, seitenweise und in lokalen Zeitangaben an.
- Screenshots und TAZ-Artikelinhalte werden über quellspezifische Codecs archiviert.
- Der öffentliche Anchor erlaubt den späteren Nachweis, dass eine Hash-Kette zu einem bestimmten Zeitpunkt existierte.
