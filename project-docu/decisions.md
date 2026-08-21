# Entscheidungen

## Fachliche und technische Entscheidungen

- Datum: 2026-07-29 bis 2026-08-19
  Entscheidung: News-Hash verwendet eine lokale, append-only Hash-Kette und keine eigene oder direkt betriebene öffentliche Blockchain.
  Begründung: Das Projekt benötigt nachvollziehbare historische Integrität ohne Mining, Konsensmechanismus oder Veröffentlichung der Nachrichteninhalte. Tägliche Hash-Manifeste werden zusätzlich über OpenTimestamps öffentlich verankert.

- Datum: 2026-07-29 bis 2026-08-19
  Entscheidung: Jede Quelle wird parallel in JSONL und SQLite gespeichert. Beide Speicher führen unabhängige Hash-Ketten.
  Begründung: JSONL ist ein einfaches, offenes Archivformat; SQLite ermöglicht effiziente Abfragen für WebUI und Werkzeuge. Unabhängige Ketten bleiben auch nach einem Abbruch zwischen den beiden Schreibvorgängen jeweils prüfbar.

- Datum: 2026-08-04 bis 2026-08-19
  Entscheidung: SQLite speichert zusätzlich zu den Records Bild-BLOBs, Anchor-Artefakte und die vollständigen Definitionen der versionierten Codecverträge in `codec_metadata`.
  Begründung: Bilder sollen ohne externe Dateien verfügbar bleiben. Manifeste und Proofs gehören zum Integritätsnachweis. Eine SQLite-Datei soll mit `newshash-validate --sqlite` ohne JSONL, `settings.toml` oder externe `data/Codec/`-Dateien validierbar sein.

- Datum: 2026-08-04 bis 2026-08-19
  Entscheidung: Bild-BLOBs werden global pro SQLite-Shard über `image_hash` dedupliziert; die Record-Daten referenzieren sie über ihr `images`-Feld.
  Begründung: Derselbe Bildinhalt wird unabhängig von der Quelle nur einmal gespeichert.

- Datum: 2026-08-21
  Entscheidung: JSONL-Shards und zugehörige Bilddateien werden je Quelle unter `data/JSONL/<storage_name>/` beziehungsweise `data/JSONL/<storage_name>/images/` abgelegt. SQLite-Shards liegen unter `data/SQLITE/`. Beim ersten Start werden vorhandene Dateien einmalig in diese Struktur verschoben.
  Begründung: Die Quelldaten bleiben übersichtlich zusammengefasst; die Migration erfolgt nicht destruktiv und die logischen Bildpfade in Records bleiben für die Hashprüfung unverändert.

- Datum: 2026-08-05 bis 2026-08-19
  Entscheidung: SQLite-Shards werden bei Schemaabweichungen nicht destruktiv migriert. Die alte Tabelle wird nach `<tabelle>_legacy_<zeitstempel>` umbenannt und durch das aktuelle Schema ersetzt.
  Begründung: Historische Daten dürfen nicht verloren gehen; das Vorgehen ist nachvollziehbar und vermeidet fehleranfällige Migrationen im Prototyp.

- Datum: 2026-08-04 bis 2026-08-19
  Entscheidung: Die Speicherung ist in nummerierte Shards mit einer Grenze von 1 GB geteilt. Dublettenprüfungen und die Dashboard-Vorschau verwenden nur den neuesten Shard; Zählungen, Details und vollständige Validierung können shardübergreifend arbeiten.
  Begründung: Regelmäßige Läufe und die WebUI sollen auch bei großen Archiven performant bleiben.

- Datum: 2026-08-11 bis 2026-08-19
  Entscheidung: Quellenspezifische Verarbeitung erfolgt über versionierte Codecs. `RSSv2`, `TAZv2` und `SCREENv2` sind die aktuellen Codecs; `v0` und `v1` bleiben ausschließlich für historische Records und deren Validierung erhalten.
  Begründung: Feed-Normalisierung, vollständige TAZ-Artikel und Browser-Screenshots benötigen unterschiedliche Verarbeitung, ohne die allgemeine RSS-Logik mit Hostnamen zu vermischen.

- Datum: 2026-08-11 bis 2026-08-19
  Entscheidung: Der Daemon startet die WebUI im selben Prozess und fragt jede konfigurierte Quelle nach ihrem eigenen `poll_interval_seconds` ab. Ein Heartbeat ist über `heartbeat_url` optional.
  Begründung: Import, Statusanzeige, Quellenaktionen und kontrolliertes Beenden gehören zusammen; externe Betriebsüberwachung muss deaktivierbar bleiben.

- Datum: 2026-08-11 bis 2026-08-19
  Entscheidung: Pro Quelle und UTC-Tag wird ein Manifest mit JSONL- und SQLite-Hash erzeugt, per OpenTimestamps verankert und bei unverändertem Inhalt nicht erneut nach GitHub hochgeladen.
  Begründung: Der öffentliche Nachweis soll den Bestand zu einem Zeitpunkt belegen, ohne Nachrichteninhalte zu veröffentlichen oder unnötige Synchronisierungs-Commits zu erzeugen.

- Datum: 2026-08-11 bis 2026-08-19
  Entscheidung: Laufzeit-Logs, Quellenfehler und der aktuelle Anchor-Status bleiben flüchtig; fachliche Nachrichten-, Bild- und Integritätsdaten werden persistent gespeichert und Fehler zusätzlich sofort nach `stderr` geschrieben.
  Begründung: Betriebszustände gehören zum aktuellen Prozesslauf, während Archiv- und Nachweisdaten dauerhaft erhalten bleiben müssen.

## Projektregeln

- Datum: 2026-08-04
  Entscheidung: HTTP-Aufrufe verwenden `requests` statt einer eigenen `urllib`-Abstraktion.
  Begründung: Im Prototyp bietet `requests` die einfachere und robustere Fehlerbehandlung.

- Datum: 2026-08-13
  Entscheidung: Jede Code-Änderung erhöht das Patchlevel in `app/pyproject.toml`, `app/src/newshash/__init__.py` und der Lockdatei synchron.
  Begründung: Jede ausgelieferte Anwendungsversion soll Codeänderungen eindeutig erkennen lassen.

- Datum: 2026-08-13
  Entscheidung: Abgeschlossene Änderungen werden jeweils in einem eigenen Commit festgehalten.
  Begründung: Die Änderungshistorie bleibt nachvollziehbar.

- Datum: 2026-08-13 bis 2026-08-14
  Entscheidung: Die Homepage liegt unter `docs/`, die verbindliche Projekt- und Produktdokumentation unter `project-docu/`. GitHub-Actions verwenden vollständige Commit-SHAs.
  Begründung: Veröffentlichungsinhalt, Projektdokumentation und CI-Abhängigkeiten sollen klar getrennt und reproduzierbar sein.

- Datum: 2026-08-13 bis 2026-08-14
  Entscheidung: Reine Website-Änderungen erhöhen die App-Version nicht. Neue dauerhafte Projektanweisungen werden in `project-docu/` dokumentiert. Designänderungen werden mit einem echten Browser-Screenshot geprüft.
  Begründung: Website und Anwendung werden unabhängig veröffentlicht; dauerhafte Regeln und visuelle Ergebnisse müssen nachvollziehbar dokumentiert beziehungsweise geprüft werden.
