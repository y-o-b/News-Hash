# TSBLOCK

Projekt für Nachrichten-Import, Hash-Kette und Storage-Modi.

## Start

`uv run newshash`
`uv run newshash --daemon`

## Entwicklung

Bei jeder Code-Änderung wird das Patchlevel der App erhöht. Die Versionsnummer in `pyproject.toml` und `src/newshash/__init__.py` muss dabei synchron bleiben.

## Konfiguration

- `--settings <pfad>`: alternative Settings-Datei laden, Standard ist `data/settings.toml`
- `--daemon`: läuft dauerhaft und fragt jede Quelle nach ihrem eigenen `poll_interval_seconds` erneut ab
- In `data/settings.toml` werden die Quellen mit `name`, `feed_url`, `storage_name`, `poll_interval_seconds` und optional `codec_name` definiert
- JSONL und SQLite werden beide unter `data/` geschrieben und bei 1 GB in nummerierte Shards ab `0` geteilt
- Die Dashboard-Meldungsliste verwendet nur den jeweils neuesten SQLite-Shard; Kennzahlen und Detailzugriffe bleiben shardübergreifend
- Bilder aus den Feeds werden für JSONL in `data/images/` gespeichert und mit relativen Pfaden referenziert
- Bilder werden zusätzlich als BLOBs in SQLite abgelegt
- Der Codec `SCREENv0` folgt Feed-Links mit Chromium und speichert vollständige PNG-Seitenscreenshots
- `--daemon` startet Import-Daemon und HTML-Übersicht gemeinsam auf `0.0.0.0:8000`
- `--ots` aktiviert OpenTimestamps auch bei einem einmaligen Import; im `--daemon`-Modus ist Anchoring automatisch aktiv
- Mit `--host` und `--port` kann die Bind-Adresse des Dashboards angepasst werden
- Prometheus-Metriken sind unter `/metrics` verfügbar
- Der Button `Daemon beenden` im Dashboard beendet Import und Webserver kontrolliert
- Quellenfehler und die letzten Fehlermeldungen gelten nur für die aktuelle Laufzeit, werden nach `stderr` geloggt und nicht gespeichert
- Eine vollständige Beschreibung der WebUI steht in `project-docu/webui.md`
- Meldungen können im Dashboard quellengefiltert, seitenweise und als Detailansicht mit gespeicherten Bildern angezeigt werden
- Das Dashboard bietet die Themes `Comic`, `DarkMode`, `LightMode`, `Papier` und `News`
- Pro Quelle wird täglich ein OpenTimestamps-Manifest unter `data/anchors/<UTC-Datum>/` erzeugt und mit `ots stamp` an die Kalender übergeben
- Vorhandene Manifest- und `.ots`-Dateien werden mit `GITHUB_TOKEN` und `GITHUB_REPOSITORY` aus `data/credentials.env` unter `anchors/<UTC-Datum>/` hochgeladen
- Die Quellenkarten unterscheiden zwischen keinem Anchor, fehlender `.ots`-Datei, ausstehender Attestation und vollständiger Bestätigung
