# News-Hash

News-Hash ist ein lokales Nachrichtenarchiv mit überprüfbarer Historie. Die Anwendung liest konfigurierte Nachrichtenquellen ein, normalisiert neue Meldungen und speichert sie dauerhaft in einer append-only Datenstruktur. Jede Meldung bleibt mit ihrer zeitlichen Einordnung, Quelle und Hash-Historie nachvollziehbar.

English version: [README.md](README.md)

Die Python-Anwendung liegt unter `app/`. Die statische GitHub-Pages-Website liegt unter `docs/`. Die verbindliche Projekt- und Produktdokumentation befindet sich unter `project-docu/`.

Besonders wichtig sind die externen Nachweise und die Betriebsüberwachung: Hash-Manifeste werden über OpenTimestamps in der Bitcoin-Blockchain verankert und zusätzlich mit ihren `.ots`-Proofs per Git in einem GitHub-Repository veröffentlicht. Der laufende Betrieb kann über einen optionalen Heartbeat und über Prometheus-Metriken überwacht werden.

> ✦ Mit KI gebaut, mit Liebe verfeinert, für neugierige Menschen ♥

## Inhaltsverzeichnis

- [Architektur](#architektur)
- [Verzeichnisstruktur](#verzeichnisstruktur)
- [Voraussetzungen](#voraussetzungen)
- [Installation und Start](#installation-und-start)
- [Konfiguration](#konfiguration)
- [Datenfluss](#datenfluss)
- [Speicherung und Shards](#speicherung-und-shards)
- [Hash-Ketten](#hash-ketten)
- [Codecs](#codecs)
- [Daemon und WebUI](#daemon-und-webui)
- [Integritätsnachweise](#integritätsnachweise)
- [Monitoring](#monitoring)
- [Anchoring und GitHub-Synchronisierung](#anchoring-und-github-synchronisierung)
- [Docker](#docker)
- [Tests und Qualitätssicherung](#tests-und-qualitätssicherung)
- [Entwicklungsregeln](#entwicklungsregeln)

## Architektur

News-Hash besteht aus einem CLI-Programm, einer Import- und Normalisierungsschicht, austauschbaren Quellen-Codecs, zwei parallelen Speichern und einer eingebetteten HTTP-WebUI.

Die Anwendung arbeitet ohne öffentliche Blockchain und ohne externe Konsensmechanismen. Die interne Kette ist eine append-only Folge von Datensätzen. Jeder neue Datensatz referenziert den Hash des vorherigen Datensatzes. Dadurch lassen sich nachträgliche Änderungen an Inhalt oder Reihenfolge erkennen.

JSONL und SQLite werden bewusst parallel geführt. Beide Speicher verwenden dasselbe Hash-Material, besitzen aber jeweils eine unabhängige Kette. Das erlaubt eine konsistente Wiederherstellung, wenn ein Prozess beispielsweise zwischen zwei Schreibvorgängen beendet wird.

## Verzeichnisstruktur

```text
app/
├── data/                    Laufzeitdaten, Settings und Credentials
├── src/newshash/            Anwendungscode
├── tests/                   Unit- und Integrationstests
├── pyproject.toml           Paketmetadaten und Tool-Konfiguration
└── uv.lock                 Reproduzierbare Abhängigkeiten
docs/                        Statische GitHub-Pages-Website
project-docu/                Verbindliche Projekt- und Produktdokumentation
anchors/                     Öffentlich synchronisierte Anchor-Dateien
docker-compose.yml           Container-Deployment
```

Die Laufzeitdaten unter `app/data/` enthalten unter anderem SQLite-Dateien, JSONL-Dateien, Bilder und lokale Anchor-Dateien. Credentials werden aus `app/data/credentials.env` gelesen und nicht protokolliert.

## Voraussetzungen

- Python 3.14 oder kompatibel
- `uv`
- Für `SCREENv0`: Playwright mit installiertem Chromium
- Für OpenTimestamps: der Befehl `ots`
- Für GitHub-Synchronisierung: ein GitHub-Token und ein Repository in `data/credentials.env`

Die Python-Abhängigkeiten werden über `pyproject.toml` und `uv.lock` verwaltet. Die Anwendung nutzt unter anderem `requests`, `markdown`, `playwright` und `opentimestamps-client`.

## Installation und Start

Alle Python- und Testbefehle werden aus `app/` ausgeführt:

```bash
cd app
uv sync --dev
uv run newshash
```

Ein einmaliger Lauf ruft jede konfigurierte Quelle genau einmal ab. Für den dauerhaften Betrieb wird der Daemon gestartet:

```bash
uv run newshash --daemon
```

OpenTimestamps kann bei einem einmaligen Lauf explizit aktiviert werden:

```bash
uv run newshash --ots
```

Verfügbare CLI-Optionen:

- `--settings <pfad>` lädt eine alternative TOML-Datei.
- `--daemon` startet den dauerhaften Polling-Betrieb mit WebUI.
- `--ots` aktiviert Anchoring bei einem einmaligen Lauf.
- `--host <adresse>` setzt die Bind-Adresse der WebUI.
- `--port <nummer>` setzt den HTTP-Port der WebUI.
- `--version` zeigt die installierte App-Version.

Standardmäßig bindet die WebUI im Daemon-Modus auf `0.0.0.0:8000`. Für lokale Tests kann die Bind-Adresse eingeschränkt werden:

```bash
uv run newshash --daemon --host 127.0.0.1 --port 8000
```

Hash-Ketten können unabhängig vom Feedabruf geprüft werden. Standardmäßig wird nur der letzte nichtleere Shard geprüft:

```bash
uv run newshash-validate --settings data/settings.toml --data-dir data
```

Für eine vollständige Prüfung aller Shards wird `--all-shards` ergänzt. Mit `--source <storage_name>` kann die Prüfung auf eine Quelle eingeschränkt werden. Die Prüfung umfasst JSONL und SQLite und endet bei einer ungültigen Kette mit Status 1.

## Konfiguration

Die Standarddatei ist `app/data/settings.toml`. Sie muss mindestens einen `[[sources]]`-Block enthalten. Ein vollständiger Quellenblock sieht so aus:

```toml
[[sources]]
name = "Tagesschau"
feed_url = "https://example.org/feed.json"
storage_name = "tagesschau"
codec_name = "RSSv0"
poll_interval_seconds = 300
```

Die Felder haben folgende Bedeutung:

- `name` ist der Anzeigename in der WebUI.
- `feed_url` ist die URL des JSON- oder XML-Feeds.
- `storage_name` bestimmt die Dateinamen der JSONL- und SQLite-Shards.
- `codec_name` wählt die quellspezifische Verarbeitung. Standard ist `RSSv0`.
- `poll_interval_seconds` bestimmt das individuelle Polling-Intervall im Daemon.

Für neue Quellen werden die versionierten Codecs `RSSv1`, `TAZv1` und `SCREENv1` empfohlen. Sie legen `schema-v0/v1.json`, `codecs-v0/v1.json` und `hash-functions-v0/v1.json` in `app/data/` ab und speichern deren Hashes im Record. Bei der täglichen Manifestbildung werden SQLite-Shards unter `app/data/sqlite-backups/` mit gleichbleibenden Dateinamen überschrieben. Manifest und `.ots`-Proof werden zusätzlich in der Tabelle `anchor_artifacts` der SQLite-Datei gespeichert.

Optional kann auf oberster Ebene ein Heartbeat-Ziel angegeben werden:

```toml
heartbeat_url = "https://example.org/heartbeat"
```

Ist `heartbeat_url` nicht gesetzt oder leer, wird kein Heartbeat gesendet. Die Anwendung verwendet keine fest eingebaute Heartbeat-Adresse.

## Datenfluss

Bei jedem Quellenlauf durchläuft eine Meldung diese Schritte:

1. Der konfigurierte Feed wird per HTTP abgerufen.
2. JSON oder XML wird in das interne Feed-Format überführt.
3. Der ausgewählte Codec normalisiert Titel, Inhalt, URL, Autor und Zeitstempel.
4. Bereits bekannte `source_id`s werden vor teuren Verarbeitungsschritten übersprungen.
5. Verlinkte Bilder oder quellspezifische Inhalte werden geladen, sofern der Codec dies vorsieht.
6. Für JSONL und SQLite wird jeweils der nächste Hash anhand der eigenen Kette berechnet.
7. Die neuen Datensätze werden in beide Speicherformate geschrieben.
8. Optional wird ein Tagesmanifest erzeugt, verankert und synchronisiert.

Fehler bei einer Quelle werden gezählt, nach `stderr` geschrieben und im laufenden Prozess für Dashboard und Metriken vorgehalten. Ein Fehler soll die Verarbeitung anderer Quellen nicht stoppen.

## Speicherung und Shards

Pro Quelle entstehen unter `app/data/` Dateien nach diesem Muster:

```text
<storage_name>.0.jsonl
<storage_name>.0.sqlite3
```

Erreicht eine Datei 1 GB, wird der nächste nummerierte Shard angelegt. JSONL enthält einen JSON-Datensatz pro Zeile. SQLite speichert die Records in `records` und deduplizierte Bilddaten in `record_images`.

Die JSONL-Bildverweise zeigen auf relative Dateien unter `data/images/`. SQLite speichert dieselben Bilddaten zusätzlich als BLOB, damit Detailansichten auch unabhängig von der JSONL-Datei auf die Archivdaten zugreifen können.

Die Dublettenprüfung liest nur den jeweils neuesten Shard je Speicherformat. Kennzahlen und Detailzugriffe arbeiten dagegen über alle Shards. Die Dashboard-Liste verwendet aus Performancegründen nur den neuesten SQLite-Shard.

Wenn sich das Schema einer vorhandenen SQLite-Tabelle ändert, wird die alte Tabelle nach `<tabelle>_legacy_<zeitstempel>` umbenannt. Sie wird nicht gelöscht und nicht automatisch überschrieben.

## Hash-Ketten

Für jeden Datensatz wird zunächst ein kanonisches Hash-Material als JSON-Objekt aufgebaut. Die Schlüssel werden sortiert, es werden keine zusätzlichen Leerzeichen verwendet und die UTF-8-Darstellung wird gehasht. Der Algorithmus ist SHA-256.

Das Hash-Material von `RSSv0` umfasst:

- `author_name`
- `content`
- `codec_name`
- `images`
- `previous_hash`
- `published_at`
- `source_id`
- `source_url`
- `title`

Der erste Datensatz verwendet 64 Nullen als `previous_hash`. Jeder folgende Datensatz referenziert den Hash des vorherigen Datensatzes. `retrieved_at` wird gespeichert, fließt aber nicht in den Hash ein, damit derselbe veröffentlichte Inhalt bei einem späteren Abruf nicht nachträglich einen anderen Inhalts-Hash erhält.

Ein Datensatz ist gültig, wenn `previous_hash` auf den erwarteten Vorgänger zeigt und `hash` dem neu berechneten Wert entspricht. Die Prüflogik steht im Codec und wird durch Tests abgedeckt.

## Codecs

Codecs kapseln quellspezifische Verarbeitung, ohne die allgemeine Importlogik mit Hostnamen oder Sonderfällen zu belasten:

- `RSSv0` verarbeitet allgemeine JSON-Feeds und klassischen XML-RSS. Zeitstempel werden nach UTC normalisiert und Bilder aus HTML-Inhalten geladen.
- `TAZv0` ruft zusätzlich den vollständigen TAZ-Artikel über den Feed-Link ab und übernimmt den strukturierten Artikeltext.
- `SCREENv0` öffnet den Feed-Link mit Chromium und speichert einen vollständigen PNG-Seitenscreenshot. Bekannte Consent- und Cookie-Banner werden vor der Aufnahme entfernt.

Neue Quellen werden über zusätzliche `[[sources]]`-Blöcke und einen vorhandenen oder neuen Codec eingebunden.

## Daemon und WebUI

Der Daemon verarbeitet jede Quelle nach ihrem eigenen Intervall und startet parallel den eingebetteten HTTP-Server. Die WebUI bietet:

- Quellenkarten mit Meldungs-, Bild-, Fehler- und Anchor-Status
- Quellenfilter und zehn Meldungen pro Seite
- Detailseiten mit Inhalt, Hashes, Zeitstempeln und gespeicherten Bildern
- lokale Browser-Zeiten bei intern gespeicherten UTC-Zeitstempeln
- fünf Themes: `Comic`, `DarkMode`, `LightMode`, `Papier` und `News`
- Laufzeit-Log und flüchtige Fehleranzeige
- kontrolliertes Beenden des Daemons
- Prometheus-Metriken unter `/metrics`

Wichtige Endpunkte sind `/`, `/hilfe`, `/metrics`, `/meldung/<storage>/<source_id>`, `/media/<pfad>`, `/anchor/<storage>/<datum>/<art>`, `/fetch` und `/shutdown`.

Die WebUI besitzt keine Benutzerverwaltung und keine Authentifizierung. Sie sollte deshalb nicht ungeschützt in ein öffentliches Netz exponiert werden.

## Integritätsnachweise

News-Hash bietet zwei voneinander unabhängige Wege, die Existenz und Herkunft der Archivnachweise nachzuvollziehen:

1. OpenTimestamps verankert die Hash-Manifeste über Bitcoin. Das Manifest enthält die aktuellen Hashes der JSONL- und SQLite-Ketten, aber keine Nachrichteninhalte. Der OpenTimestamps-Proof kann später prüfen, dass diese Hashes spätestens zum bestätigten Zeitpunkt existiert haben.
2. GitHub veröffentlicht die zugehörigen Manifest- und `.ots`-Dateien versioniert in einem Repository. Damit bleiben die Nachweise öffentlich auffindbar und über die Git-Historie nachvollziehbar. Unveränderte Dateien werden nicht erneut hochgeladen.

Die beiden Wege erfüllen unterschiedliche Aufgaben: Bitcoin liefert die externe Zeitverankerung, während GitHub die Nachweisdateien zugänglich und historisch sichtbar macht. Keine der beiden Ablagen veröffentlicht die archivierten Nachrichteninhalte.

## Monitoring

Für den laufenden Betrieb stehen zwei Monitoringmöglichkeiten zur Verfügung:

- Der optionale `heartbeat_url` wird im Daemon nach den Polling-Schritten aufgerufen und meldet den Prozessbetrieb an einen konfigurierten Monitoringdienst. Ohne Eintrag wird kein Heartbeat gesendet.
- `/metrics` stellt Prometheus-Metriken für konfigurierte Quellen, gespeicherte Meldungen, Bilder und Quellenfehler bereit. Die Metriken können von Prometheus oder einem kompatiblen Monitoringdienst regelmäßig abgefragt werden.

Beispiel für den Heartbeat in `app/data/settings.toml`:

```toml
heartbeat_url = "https://example.org/heartbeat"
```

Der Heartbeat ersetzt keine fachliche Integritätsprüfung. Er zeigt, dass der Daemon läuft; die Hash-Ketten, OpenTimestamps-Proofs und GitHub-Dateien ermöglichen dagegen die spätere Prüfung der archivierten Historie.

## Anchoring und GitHub-Synchronisierung

Nach einem erfolgreichen Quellenlauf kann für den UTC-Tag ein Manifest unter `data/anchors/<datum>/` erzeugt werden. Das Manifest enthält die jeweils letzten JSONL- und SQLite-Hashes, aber keine Nachrichteninhalte. `ots stamp` übergibt das Manifest an OpenTimestamps und erzeugt daraus die zugehörige `.ots`-Datei für die Bitcoin-basierte Zeitverankerung.

Der Status unterscheidet zwischen keinem Anchor, fehlender `.ots`-Datei, ausstehender Attestation und vollständiger Bestätigung. Bestehende Anchor-Dateien werden vor dem GitHub-Upload inhaltlich verglichen. Unveränderte Dateien werden nicht erneut per `PUT` hochgeladen, damit keine unnötigen Git-Commits entstehen.

Für die Synchronisierung werden in `app/data/credentials.env` folgende Werte erwartet:

```text
GITHUB_TOKEN=<token>
GITHUB_REPOSITORY=<owner>/<repository>
```

Der Token wird nicht geloggt. Ohne vollständige Credentials findet keine GitHub-Synchronisierung statt.

## Docker

`docker-compose.yml` baut ein Image auf Basis von Python 3.14, installiert die Abhängigkeiten und Chromium und startet den Daemon. Die Projektdokumentation wird als `project-docu/` und der Anwendungscode als `src/` in das Image kopiert.

Die Laufzeitdaten werden über ein Volume nach `/app/data` eingebunden. Die Werte für Containername, Image, Datenpfad und Netzwerk werden über die Compose-Umgebung gesetzt. Der Container bindet standardmäßig auf Port 8000 innerhalb des Containers.

## Tests und Qualitätssicherung

Die Tests werden aus `app/` ausgeführt:

```bash
uv run pytest
uv run ruff check .
uv run ruff format . --check
```

Die Tests decken unter anderem Settings-Validierung, Feed-Normalisierung, Hash-Ketten, Sharding, SQLite-Schema, Anchoring, GitHub-Synchronisierung, Daemon-Polling und WebUI-Rendering ab. Screenshot-Tests benötigen Chromium; sie laden Seiten mit `domcontentloaded` und einer kurzen Render-Wartezeit statt mit `networkidle`.

## Entwicklungsregeln

- Bei jeder Code-Änderung wird das Patchlevel erhöht.
- Die Versionsnummer in `app/pyproject.toml`, `app/src/newshash/__init__.py` und `app/uv.lock` bleibt synchron.
- Reine Änderungen an der statischen Website unter `docs/` erhöhen das App-Patchlevel nicht.
- Abgeschlossene Änderungen werden jeweils in einem eigenen Commit festgehalten.
- Architekturentscheidungen und relevante Anforderungen werden in `project-docu/` nachgeführt.

## Weitere Dokumentation

- `project-docu/architecture.md` beschreibt Architektur und Hash-Berechnung.
- `project-docu/requirements.md` beschreibt Muss-, Soll- und Nicht-Scope-Anforderungen.
- `project-docu/webui.md` beschreibt Bedienung und Endpunkte der WebUI.
- `project-docu/description_for_enduser.md` ist die ausführliche deutschsprachige Hilfe für Anwender.
- `docs/` enthält ausschließlich die statische GitHub-Pages-Website.

## Lizenz

News-Hash steht unter der [MIT-Lizenz](LICENSE).
