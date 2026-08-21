# Vollständige Bildintegritätsprüfung

**Status: optional ergänzen**

## Ziel

Der Validator soll prüfen, ob jeder referenzierte Bild-Hash zu einem vorhandenen und unveränderten BLOB gehört.

## Möglicher Umfang

- SHA-256-Prüfung jedes BLOBs gegen seinen Schlüssel in `record_images`
- Erkennung fehlender oder nicht referenzierter BLOBs
- Optionaler Abgleich zwischen SQLite-BLOBs und Dateien unter `data/JSONL/<storage_name>/images/`

## Offene Fragen

- Sollen zusätzliche, nicht referenzierte BLOBs nur als Hinweis ausgegeben werden?
- Die Prüfung soll über eine Option aktiviert werden; soll diese Option nur die BLOB-Prüfung oder auch den Datei-Abgleich einschalten?

## Kommentar / Fragen

- Zusätzliche BLOBs gelten nur als Hinweis. Die Prüfung wird optional aktiviert.
