# Anforderungen

## Muss

- Konfigurierte JSON- und XML-Feeds werden regelmäßig gelesen und normalisiert.
- Jede Nachricht wird append-only als Datensatz in JSONL und SQLite gespeichert.
- Bereits gespeicherte Datensätze dürfen nicht verändert oder gelöscht werden.
- Jede Speicherform führt eine überprüfbare Hash-Kette mit `previous_hash` und `hash`.
- Bekannte `source_id`s werden vor teuren Verarbeitungsschritten übersprungen.
- Der Daemon verarbeitet jede Quelle nach ihrem eigenen `poll_interval_seconds`.
- `SCREENv0` folgt Feed-Links mit Chromium und speichert vollständige PNG-Screenshots.
- Der Daemon startet die WebUI und stellt `/metrics` für Prometheus bereit.
- Das Dashboard bietet Quellenfilter, zehn Meldungen pro Seite, Detailansichten und gespeicherte Bilder.
- Tägliche Hash-Manifeste werden mit OpenTimestamps als `.ots`-Proofs verankert.
- Eine SQLite-Datei enthält die für ihre versionierten Codecverträge notwendigen Definitionen und kann ohne weitere Archiv- oder Metadatendateien validiert werden.

## Sollte

- Bilder werden dedupliziert und lokal sowie als SQLite-BLOB gespeichert.
- Zeitstempel werden in UTC gespeichert und lokal im Browser angezeigt.
- Fehler werden nach `stderr` geloggt und pro Quelle flüchtig gezählt.
- Anchor-Status und Laufzeit-Log werden in der WebUI sichtbar gemacht.

## Nicht im Scope

- Speicherung von Nachrichteninhalten auf einer öffentlichen Blockchain.
- Eine eigene Blockchain, Mining oder Konsens zwischen externen Teilnehmern.
- Öffentliche Benutzerverwaltung oder Authentifizierung.
