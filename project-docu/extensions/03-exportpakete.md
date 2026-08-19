# Unveränderliche Exportpakete

**Status: neu bewerten**

## Ziel

Für JSONL soll ein separates Archivpaket die zugehörigen Daten und Metadaten transportierbar bündeln. SQLite enthält die für seine Validierung notwendigen Definitionen und Anchor-Artefakte bereits selbst; ein zusätzliches SQLite-Archivformat ist deshalb nicht erforderlich. Das Kopieren einer SQLite-Datei bleibt als Backup oder Transport möglich.

## Möglicher Umfang

- JSONL-Shards, Codec-Definitionen, Manifeste und Proofs
- Prüfsummen und maschinenlesbare Exportbeschreibung
- Prüfung des Pakets ohne laufenden Daemon

## Offene Fragen

- Welches Format soll das JSONL-Paket haben, zum Beispiel ZIP oder TAR?
- Sollen JSONL-Exporte verschlüsselt oder signiert werden?
- Soll ein Export einzelne Quellen, Zeiträume oder nur vollständige Archive umfassen?

## Kommentar / Fragen

- Für JSONL und SQLite gelten getrennte Archivierungswege. Ein zusätzliches SQLite-Archivformat ist nicht notwendig, weil die SQLite-Datei bereits selbstständig validierbar ist.
