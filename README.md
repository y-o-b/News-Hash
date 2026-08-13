# News-Hash

Die Python-Anwendung liegt unter `app/`. Die statische Projekthomepage liegt unter `docs/`.

```bash
cd app
uv run newshash --daemon
```

Die verbindliche Projektdokumentation befindet sich unter `project-docu/`.

## Technische Kurzbeschreibung

News-Hash ist eine Python-3.14-Anwendung, die mit `uv` verwaltet wird. Sie ruft konfigurierte JSON- und XML-Newsfeeds regelmäßig ab, normalisiert neue Meldungen und verarbeitet sie über quellspezifische Codecs. Die Daten werden parallel als JSONL und SQLite gespeichert; beide Speicher führen eine eigene SHA-256-Hash-Kette.

Der Daemon pollt die Quellen nach ihren individuellen Intervallen und stellt zusätzlich eine eingebettete WebUI mit Dashboard, Detailansichten, Bildern und Prometheus-Metriken bereit. Optional werden tägliche Hash-Manifeste mit OpenTimestamps verankert und über GitHub veröffentlicht.
