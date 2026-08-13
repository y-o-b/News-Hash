# AGENTS.md

## Projekt

- Python 3.14
- `uv` als Paketmanager
- Anwendungspfad ist `app/`; Befehle für Python und Tests werden aus diesem Verzeichnis ausgeführt
- Mehrere Quellen über `data/settings.toml`
- JSONL und SQLite parallel unter `data/`

## Regeln

- Jede abgeschlossene Änderung separat committen.
- Bei jeder Code-Änderung die Versionsnummer in den Projektmetadaten und im Paket-Export erhöhen.
- Kleine, fokussierte Änderungen bevorzugen.
- ASCII only in Code, außer vorhandene Dateien verlangen etwas anderes.
- `ruff`-Formatierung mit 160 Zeichen.

## Tests

- `uv run pytest` (in `app/`)
- `uv run ruff check .` (in `app/`)
- `uv run ruff format . --check` (in `app/`)
- Für `SCREENv0` muss Chromium einmal installiert werden: `uv run playwright install chromium`
- Screenshot-Unit-Tests ohne Netzwerk ausführen: `uv run pytest tests/test_codec.py -k screen`
- Eine echte Browser-Prüfung erstellt einen PNG-Screenshot und validiert die PNG-Signatur sowie eine Dateigröße größer als 0.
- Bei manueller Feed-Prüfung zuerst `SCREENv0` in `app/data/settings.toml` kontrollieren und danach `uv run newshash` in `app/` ausführen; die Screenshots liegen unter `app/data/images/` und werden in SQLite unter `images_json` referenziert.
- Ein Screenshot-Test darf nicht von `networkidle` abhängen; Seiten mit dauerhaft aktiven Verbindungen sollen mit `domcontentloaded` und einer kurzen Render-Wartezeit geladen werden.
- Vor dem Screenshot entfernt `SCREENv0` bekannte Cookie-/Consent-Banner; bei neuen Seiten sollte geprüft werden, ob deren Banner-Selektor ergänzt werden muss.

## Hinweise

- Doku bei relevanten Entscheidungen aktualisieren.
- In deutschsprachiger Dokumentation immer echte Umlaute und `ß` verwenden, niemals `ae`, `oe`, `ue` oder `ss` als Ersatz.
- GitHub-Actions in `.github/workflows/` müssen immer mit vollständigen Commit-SHAs statt beweglichen Versions-Tags referenziert werden.
- Neue dauerhafte Projektanweisungen werden in der passenden Datei unter `project-docu/` dokumentiert.
- Änderungen an Architekturentscheidungen, Anforderungen oder Zielbild in `project-docu/decisions.md`, `project-docu/requirements.md` und `project-docu/vision.md` nachführen.
- Diese drei Dokumente sind gemeinsam mit `project-docu/architecture.md` die verbindliche Projektdokumentation.
- `project-docu/description_for_enduser.md` ist die führende deutsche Hilfe. `project-docu/description_for_enduser_en.md` ist die englische Übersetzung und muss bei Abweichungen an die deutsche Version angepasst werden.
- Die englische Hilfe übersetzt nur die Erklärungstexte; die Dashboard-Oberfläche bleibt deutsch.
- Storage-Logik liegt in `app/src/newshash/storage.py`.
