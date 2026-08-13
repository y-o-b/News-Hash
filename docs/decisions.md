# Entscheidungen

## Protokoll

- Datum: 2026-07-29
  Entscheidung: Es wird keine öffentliche Blockchain verwendet.
  Begründung: Das Projekt braucht eine interne, unveränderliche Kette von Datensätzen mit einfacher Nachvollziehbarkeit.

- Datum: 2026-07-29
  Entscheidung: Nachrichtenquelle ist der RSSBridge-JSON-Feed der Tagesschau.
  Begründung: Die Daten sollen regelmäßig automatisch eingelesen werden.

- Datum: 2026-07-29
  Entscheidung: Die interne unveränderliche Kette wird als JSONL und in SQLite gespeichert.
  Begründung: SQLite ist lokal, einfach zu betreiben und gut für append-only Daten mit Hash-Kette geeignet.

- Datum: 2026-07-29
  Entscheidung: Abgeschlossene Änderungen werden jeweils in einem eigenen Commit festgehalten.
  Begründung: Die Historie bleibt nachvollziehbar und einzelne Arbeitsschritte sind klar getrennt.

- Datum: 2026-08-04
  Entscheidung: HTTP-Aufrufe (Feed und Bilder) nutzen die externe Bibliothek `requests` statt reinem `urllib`.
  Begründung: Einfachere und robustere Fehlerbehandlung bei HTTP-Anfragen im Prototyp.

- Datum: 2026-08-04
  Entscheidung: `record_images` speichert Bild-BLOBs global dedupliziert über `image_hash` als Primärschlüssel, ohne Bezug zu einer einzelnen `source_id`.
  Begründung: Das `images`-Feld eines Records referenziert die zugehörigen Hashes bereits; ein Bild muss so pro Inhalt nur einmal gespeichert werden.

- Datum: 2026-08-04
  Entscheidung: Die CLI-Option `--interval` entfällt; `poll_interval_seconds` ist pro Quelle in `data/settings.toml` verpflichtend.
  Begründung: Das Polling-Intervall ist eine Eigenschaft der Quelle und soll nicht durch einen globalen CLI-Default überschreibbar sein.

- Datum: 2026-08-04
  Entscheidung: `known_source_ids` prüft nur noch den jeweils letzten Shard statt aller Shards.
  Begründung: Dubletten-Prüfung soll nicht bei jedem Lauf alle historischen Shards komplett einlesen müssen; neue Feed-Einträge tauchen ohnehin im aktuellen Shard auf.

- Datum: 2026-08-04
  Entscheidung: JSONL und SQLite führen jeweils ihre eigene, unabhängige `previous_hash`-Kette statt einer einmalig berechneten, gemeinsamen Kette.
  Begründung: Die beiden Speicherformate sollen auch bei Abweichungen (z.B. nach einem Absturz zwischen den beiden Schreibvorgängen) unabhängig voneinander eine konsistente, für sich gültige Kette behalten.

- Datum: 2026-08-05
  Entscheidung: Beim Verbindungsaufbau zu einer SQLite-Shard-Datei wird das Schema von `records` und `record_images` geprüft; bei Abweichung wird die alte Tabelle nach `<tabelle>_legacy_<zeitstempel>` umbenannt statt migriert oder gelöscht.
  Begründung: Alte Daten dürfen nicht verloren gehen, auch wenn sich das Schema zwischen Programmversionen ändert; eine automatische Migration wäre im Prototyp fehleranfällig, ein Umbenennen ist sicher und nachvollziehbar.

- Datum: 2026-08-11
  Entscheidung: Quellen können über eigene Codecs verarbeitet werden. `RSSv0` bleibt generisch, `TAZv0` lädt vollständige TAZ-Artikel und `SCREENv0` erstellt Browser-Screenshots.
  Begründung: Quellenspezifische Verarbeitung soll nicht über Hostnamen in der allgemeinen RSS-Logik verteilt werden.

- Datum: 2026-08-11
  Entscheidung: Das Dashboard wird zusammen mit `--daemon` gestartet und bindet standardmäßig auf `0.0.0.0`.
  Begründung: Import, Statusanzeige, Quellenaktionen und kontrolliertes Beenden sollen in einem Prozess zusammenarbeiten.

- Datum: 2026-08-11
  Entscheidung: Laufzeitfehler, Logs und Anchor-Status bleiben flüchtig und werden nicht persistent gespeichert.
  Begründung: Fehler- und Betriebszustände beschreiben den aktuellen Prozesslauf; die fachlichen Nachrichten- und Hash-Daten bleiben davon getrennt.

- Datum: 2026-08-11
  Entscheidung: Pro Quelle und UTC-Tag wird ein Manifest mit JSONL- und SQLite-Hash über OpenTimestamps verankert.
  Begründung: Eine öffentliche Bitcoin-basierte Zeitverankerung ermöglicht Integritätsnachweise, ohne Nachrichteninhalte off-chain zu veröffentlichen.

- Datum: 2026-08-11
  Entscheidung: Die Dashboard-Meldungsliste liest nur den neuesten SQLite-Shard, während Kennzahlen und Detailzugriffe shardübergreifend arbeiten.
  Begründung: Die WebUI soll bei großen Archiven speicherschonend bleiben und aktuelle Meldungen schnell anzeigen.
