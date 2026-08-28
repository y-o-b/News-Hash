# WebUI

## Start

Die WebUI wird zusammen mit dem Daemon gestartet:

```bash
uv run newshash --daemon
```

Standardmäßig lauscht der Server auf `0.0.0.0:8000`. Die Adresse kann angepasst werden:

```bash
uv run newshash --daemon --host 0.0.0.0 --port 5000
```

## Dashboard

Das Dashboard zeigt:

- Anzahl der konfigurierten Quellen
- Gesamtzahl der Meldungen
- Gesamtzahl der gespeicherten Bilder
- Quellenkarten mit Meldungs-, Bild- und Fehleranzahl nach Fehlertyp
- Status des heutigen OpenTimestamps-Anchors
- Die neuesten Meldungen
- Den flüchtigen Laufzeit-Log

Die Meldungsliste verwendet den neuesten SQLite-Shard. Kennzahlen und Detailzugriffe bleiben shardübergreifend.

## Navigation

- Der Button `Quelle filtern` filtert die Liste auf diese Quelle.
- `Filter zurücksetzen` zeigt wieder alle Quellen.
- Die Liste zeigt standardmäßig zehn Meldungen pro Seite; auswählbar sind 10, 25, 50 oder 100 Meldungen.
- `Erste`, `Zurück`, `Weiter` und `Letzte` navigieren durch die Seiten.
- Ein Klick auf den Meldungstitel öffnet die gespeicherte Detailansicht.
- In der Detailansicht werden Inhalt, Zeitstempel, Hash und lokal gespeicherte Bilder angezeigt.
- `Jetzt abrufen` startet den Abruf einer einzelnen Quelle sofort.
- `Fehler quittieren` blendet die offenen Fehler dieser Quelle aus und entfernt sie aus den aktuellen Fehler-Metriken.

## Themes

Die Theme-Auswahl befindet sich am unteren Rand neben `Daemon beenden`.

- `LightMode` ist der Standard.
- `Comic` verwendet farbige Karten, starke Konturen und Schatten.
- `DarkMode` verwendet eine dunkle, sachliche Farbpalette.
- `Papier` orientiert sich an einer Zeitung mit Serifenschrift und redaktionellen Trennern.
- `News` verwendet ein sachliches Nachrichten-Design mit roten Akzenten.

Die Auswahl bleibt beim Filtern, Blättern und Öffnen von Meldungen erhalten.

## Aktualisierung

Neben `Live-Übersicht` zeigt ein Kreis den Countdown bis zur nächsten Aktualisierung. Der Ring leert sich fortlaufend. Ein Klick auf den Ring aktualisiert die Seite sofort.

## Anchor-Status

Die Quellenkarte zeigt den Zustand des heutigen OpenTimestamps-Anchors:

- `Kein Anchor`: Es gibt für den UTC-Tag noch kein Manifest.
- `Keine .ots-Datei`: Das Manifest wurde erzeugt, aber kein Proof erstellt.
- `Attestation ausstehend`: Die `.ots`-Datei existiert, die Bitcoin-Bestätigung steht noch aus.
- `Vollständig bestätigt`: Der Proof verweist auf einen bestätigten Bitcoin-Block.

## Laufzeit-Log

Der Laufzeit-Log zeigt die letzten 100 flüchtigen Ereignisse des aktuellen Prozesses. Dazu gehören Fetch-Start, Fetch-Ende, Speicherung, Anchor-Prüfungen und Fehler. Die Zeit wird in der lokalen Browser-Zeitzone angezeigt.

## Prometheus

Prometheus kann die Metriken über `/metrics` abrufen:

```text
http://127.0.0.1:8000/metrics
```

Der Endpoint liefert unter anderem Meldungs-, Bild- und Fehlerzähler je Quelle sowie Fehlerzähler nach Quelle und Fehlertyp.

## Beenden

Der Button `Daemon beenden` setzt das gemeinsame Stop-Signal, beendet den Import und fährt den Webserver kontrolliert herunter.

## FAQ

### Was bedeutet der Hash?

Der Hash identifiziert den Inhalt eines Datensatzes. Jeder Datensatz enthält zusätzlich den Hash des vorherigen Datensatzes und bildet damit eine nachvollziehbare Kette.

### Was wird beim Anchor gespeichert?

OpenTimestamps erhält nur ein Manifest mit den Hashes der beiden lokalen Ketten. Nachrichteninhalte werden nicht an die Blockchain übertragen.

### Was bedeuten die Anchor-Symbole?

`Kein Anchor` bedeutet, dass noch kein Manifest existiert. `Keine .ots-Datei` bedeutet, dass die Übergabe noch keinen Proof erzeugt hat. `Attestation ausstehend` wartet auf die Bestätigung. `Vollständig bestätigt` bedeutet, dass ein vollständiger Attestation-Pfad vorliegt.

### Warum sehe ich eine Meldung nicht sofort?

Der Daemon fragt Quellen nach ihrem jeweiligen Intervall ab. Die WebUI aktualisiert sich automatisch; der Ring neben `Live-Übersicht` kann außerdem für eine sofortige Aktualisierung angeklickt werden.

### Was passiert bei einem Quellenfehler?

Der Fehler wird nach `stderr` und in den flüchtigen Laufzeit-Log geschrieben. Andere Quellen laufen weiter. Die Fehlerzähler werden beim Neustart zurückgesetzt.

### Wie funktionieren Screenshots?

`SCREENv0` öffnet den ersten Feed-Link einer Screenshot-Quelle mit Chromium, entfernt bekannte Cookie-Banner und speichert einen vollständigen PNG-Screenshot.
