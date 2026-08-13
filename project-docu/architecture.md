# Architektur

## Technische Leitplanken

- Python mit `uv`
- Externe Nachrichtenquelle wird per HTTP abgefragt.
- Interne Blockchain bedeutet eine append-only Kette von Datensätzen.
- Jeder Datensatz referenziert den vorherigen, um Manipulationen erkennbar zu machen.
- Es wird zunächst lokal und ohne externe Knoten gearbeitet.
- Speicherung erfolgt gleichzeitig als JSONL und SQLite unter `data/`.
- Die Quellen werden in `data/settings.toml` konfiguriert.
- Ein optionaler Top-Level-Wert `heartbeat_url` in `data/settings.toml` steuert den Daemon-Heartbeat; ohne Wert wird kein Ping gesendet.
- Pro Quelle kann ein `codec_name` gewählt werden.
- `RSSv0` verarbeitet allgemeine JSON- und XML-RSS-Feeds; `TAZv0` lädt zusätzlich den vollständigen TAZ-Artikel über dessen Link.
- `SCREENv0` folgt jedem Feed-Link mit Chromium und speichert einen vollständigen PNG-Seiten-Screenshot als Bild-Record.
- Nach einem erfolgreichen Quellenlauf wird pro UTC-Tag ein Manifest mit den aktuellen JSONL- und SQLite-Hashes erzeugt und als OpenTimestamps-Proof unter `data/anchors/` verankert.
- Erfolgreich erzeugte Anchor-Dateien werden mit `GITHUB_TOKEN` und `GITHUB_REPOSITORY` aus `data/credentials.env` synchronisiert.
- `--daemon` startet zusätzlich den eingebauten HTTP-Webserver; Standard-Bind-Adresse ist `0.0.0.0:8000`.
- Bilder aus Feed-Einträgen werden für JSONL unter `data/images/` abgelegt und für SQLite zusätzlich als BLOB gespeichert.

## Laufmodi

- Jede Quelle wird als `data/<storage_name>.<N>.jsonl` und `data/<storage_name>.<N>.sqlite3` gespeichert, beginnend bei `0`.
- Die Dashboard-Vorschau liest Meldungen ausschließlich aus dem neuesten SQLite-Shard; aggregierte Kennzahlen werden über alle Shards gebildet.
- `--daemon`: startet einen Endlosschleifen-Modus, der jede Quelle nach ihrem eigenen `poll_interval_seconds` erneut verarbeitet.
- `/metrics`: liefert Prometheus-Metriken für Quellen, Datensätze, Bilder und Laufzeitfehler.
- Quellenfehler und die letzten Fehlermeldungen werden nur im Prozessspeicher gehalten, nach `stderr` geloggt und über Dashboard sowie `/metrics` bereitgestellt; Netzwerk- und Interpretationsfehler stoppen die übrigen Quellen nicht.
- Bilder bekommen Dateinamen mit Veröffentlichungszeitpunkt und laufender Nummer.
- Ein neues Shard wird erstellt, sobald eine Datei 1 GB erreicht.
- Bei jedem Verbindungsaufbau zu einer SQLite-Shard-Datei wird das Schema von `records` und `record_images` geprüft. Weicht es ab, wird die bestehende Tabelle nach `<tabelle>_legacy_<zeitstempel>` umbenannt und eine frische Tabelle mit dem aktuellen Schema angelegt.

## Settings

- Jede Quelle hat einen `name`, eine `feed_url`, einen `storage_name`, einen `codec_name` und einen `poll_interval_seconds`.
- Der Dateiname wird unter `data/` abgelegt.
- Ein Lauf verarbeitet alle in `data/settings.toml` definierten Quellen nacheinander.
- Bereits bekannte `source_id`s werden übersprungen, wobei nur der jeweils letzte Shard je Speicherformat geprüft wird.

## Nutzung

- Mit `--daemon` kann die App als Polling-Dienst laufen.
- Das Dashboard filtert nach Quelle, paginiert mit zehn Meldungen pro Seite und zeigt gespeicherte Meldungsdetails inklusive Bilder.
- Zeitstempel werden intern in UTC verarbeitet und in der lokalen Browser-Zeitzone angezeigt.
- Verfügbare Themes: `Comic`, `DarkMode`, `LightMode`, `Papier` und `News`.
- Zusätzliche Quellen werden durch neue `[[sources]]`-Einträge in `data/settings.toml` ergänzt.

## Feldzuordnung

- `source_id` -> `items[].id`
- `title` -> `items[].title`
- `source_url` -> `items[].url`
- `author_name` -> `items[].author.name` falls vorhanden
- `codec_name` -> Codec-Name der Anwendung
- `content` -> `items[].content_html`
- `published_at` -> `_rssbridge.dc.date`, `_rssbridge.pubDate`, `_rssbridge.published` oder `_rssbridge.updated`; `items[].date_modified` wird nicht verwendet
- `images` -> Bildmetadaten als Dict mit `image_hash` als Schlüssel
- `image_data` -> Bild-BLOB in `record_images`

JSONL und SQLite führen getrennte Hash-Ketten: `previous_hash`, bekannte `source_id`s und der jeweils letzte Hash werden pro Speicherformat unabhängig ermittelt.
Beide Ketten nutzen dasselbe kanonische Material und denselben Algorithmus, können aber unterschiedliche Werte ergeben, wenn ein Speicherformat dem anderen voraus ist (z. B. nach einem Absturz).
`retrieved_at` wird gespeichert, aber nicht gehasht.

### Hash-Berechnung

Für jeden neuen Datensatz wird zuerst das Hash-Material als JSON-Objekt gebaut und dann kanonisch serialisiert.

`RSSv0` verwendet dabei diese Felder in genau dieser Form:

- `author_name`
- `content`
- `codec_name`
- `images`
- `previous_hash`
- `published_at`
- `source_id`
- `source_url`
- `title`


Die Serialisierung erfolgt mit sortierten Schlüsseln, ohne zusätzliche Leerzeichen, und mit UTF-8.
Aus diesem String wird dann direkt `sha256` gebildet.

Die Kette selbst hängt an `previous_hash` an:

- Erster Eintrag: `previous_hash = "0" * 64`
- Jeder weitere Eintrag: `previous_hash` ist der Hash des vorherigen Datensatzes
- Ein Datensatz ist nur gültig, wenn gespeichertes `previous_hash` und neu berechneter `hash` übereinstimmen

## Datenfluss

1. Feed abrufen.
2. JSON oder XML parsen.
3. Nachrichten normalisieren.
4. Neue Einträge je Speicherformat getrennt gegen dessen eigene Kette prüfen.
5. Datensatz an die jeweilige Kette anhängen.

## Struktur

- `app/src/newshash/`: Anwendungscode
- `project-docu/`: Projekt- und Produktdokumentation
- `project-docu/webui.md`: Bedienung und Endpunkte der WebUI
