# News-Hash

## Die Idee hinter dem Projekt - Nachrichten nachvollziehbar archivieren

Nachrichten verändern sich schnell. Ein Artikel kann später überarbeitet, gekürzt, verschoben oder vollständig entfernt werden. Dadurch ist im Nachhinein oft schwer festzustellen, was zu einem bestimmten Zeitpunkt tatsächlich veröffentlicht war.

News-Hash setzt genau dort an: Nachrichten werden regelmäßig aus verschiedenen Quellen abgerufen und als unveränderliche Momentaufnahmen archiviert. Jeder neue Datensatz wird mit einem kryptografischen Hash versehen. Zusätzlich verweist er auf den Hash des vorherigen Datensatzes. So entsteht pro Speicherformat eine fortlaufende Kette.

Wird ein gespeicherter Datensatz nachträglich verändert, passt sein Hash nicht mehr. Dadurch wird eine Manipulation sichtbar. Die Hash-Kette beweist nicht, dass der Inhalt journalistisch richtig ist. Sie beweist aber, dass die gespeicherte Fassung nachträglich verändert wurde oder unverändert geblieben ist.

Die Daten werden parallel in JSONL und SQLite gespeichert. JSONL ist einfach zu archivieren und von vielen Werkzeugen lesbar. SQLite ermöglicht schnelle Abfragen für die WebUI. Beide Speicher führen ihre eigene Kette, damit ein Fehler oder Abbruch in einem Speicherformat die Integrität des anderen nicht beeinträchtigt.

Für besondere Quellen gibt es eigene Codecs. Die normale RSS-Verarbeitung übernimmt strukturierte JSON- und XML-Feeds. Der TAZ-Codec lädt zusätzlich den vollständigen Artikel. Der Screenshot-Codec öffnet den ersten Link einer Quelle mit Chromium, entfernt bekannte Cookie-Banner und bewahrt eine vollständige visuelle Momentaufnahme auf.

Einmal täglich werden die aktuellen Hashes beider Speicherketten in einem kleinen Manifest zusammengefasst. Dieses Manifest enthält keine Nachrichtentexte. Es wird mit OpenTimestamps öffentlich verankert und damit mit der Bitcoin-Zeitachse verbunden. So kann später nachgewiesen werden, dass diese Hashes spätestens zu diesem Zeitpunkt existiert haben.

Das Projekt verbindet damit drei Ebenen: ein lokales Archiv für die Inhalte, Hash-Ketten für die interne Nachvollziehbarkeit und eine öffentliche Zeitverankerung für den unabhängigen Existenznachweis. Die Blockchain speichert dabei nicht die Nachrichten, sondern nur den kryptografischen Fingerabdruck des lokalen Archivs.


## Dashboard bedienen

- Klicke auf die Meldungsanzahl einer Quelle, um die Meldungen zu filtern.
- Nutze `Filter zurücksetzen`, um wieder alle Quellen zu sehen.
- Die Meldungsliste zeigt zehn Meldungen pro Seite.
- Mit `Erste`, `Zurück`, `Weiter` und `Letzte` wechselst du die Seite.
- Ein Klick auf den Meldungstitel öffnet die gespeicherte Detailansicht.
- `Jetzt abrufen` startet den Abruf einer einzelnen Quelle sofort.
- Der Countdown-Kreis neben `Live-Übersicht` aktualisiert die Seite automatisch oder sofort per Klick.

## Themes

Die Auswahl befindet sich unten neben `Daemon beenden`.

- `LightMode` ist der Standard.
- `Comic` verwendet farbige Karten und wechselnde Schatten.
- `DarkMode` verwendet eine dunkle, sachliche Farbpalette.
- `Papier` erinnert an eine Zeitung.
- `News` verwendet ein sachliches Nachrichten-Design mit roten Akzenten.

## Anchor-Status

- `Kein Anchor`: Für den heutigen UTC-Tag gibt es noch kein Manifest.
- `Keine .ots-Datei`: Das Manifest wurde erstellt, aber noch kein Proof erzeugt.
- `Attestation ausstehend`: Die Bestätigung durch OpenTimestamps steht noch aus.
- `Vollständig bestätigt`: Ein vollständiger Attestation-Pfad liegt vor.

Manifest und `.ots`-Datei können direkt auf der Quellenkarte heruntergeladen werden. Die Prüfung ist zusätzlich über [OpenTimestamps](https://opentimestamps.org/) möglich.
Vorhandene Anchor-Dateien werden zusätzlich im öffentlichen GitHub-Repository `y-o-b/News-Hash` unter `anchors/<UTC-Datum>/` abgelegt.

Die aktuellen Hash-Werte können auch über die Druckfunktion des Browsers gesichert werden. Die Druckansicht blendet Bedienbuttons, Filter, Logs und Anchor-Links aus und eignet sich dadurch als papierbasierter Nachweis der sichtbaren Hash-Werte.

## FAQ

### Was bedeutet der Hash?

Der Hash identifiziert den Inhalt eines Datensatzes. Jeder Datensatz enthält zusätzlich den Hash des vorherigen Datensatzes und bildet damit eine nachvollziehbare Kette.

### Was wird beim Anchor gespeichert?

OpenTimestamps erhält nur ein Manifest mit den Hashes der beiden lokalen Ketten. Nachrichteninhalte werden nicht an die Blockchain übertragen.

### Wie kann ein Anchor verifiziert werden?

Lade auf der Quellenkarte zuerst das Manifest und die zugehörige `.ots`-Datei herunter. Die Prüfung kann anschließend mit dem OpenTimestamps-Client erfolgen:

```bash
ots verify <manifest>.txt.ots
```

Für eine unabhängige vollständige Bitcoin-Prüfung benötigt der Client Zugriff auf einen Bitcoin-Core-Knoten. Ohne einen solchen Knoten kann der Proof trotzdem auf vorhandene Attestationspfade und den Status _Timestamp complete_ geprüft werden. Die WebUI zeigt diesen Zustand als `Vollständig bestätigt` an.

Die Dateien können außerdem über den Link zur OpenTimestamps-Webseite geprüft werden. Der Manifest-Hash muss dabei mit dem Hash der heruntergeladenen `.txt`-Datei übereinstimmen.


### Warum sehe ich eine Meldung nicht sofort?

Der Daemon fragt Quellen nach ihrem jeweiligen Intervall ab. Die WebUI aktualisiert sich automatisch.

### Was passiert bei einem Quellenfehler?

Der Fehler wird protokolliert und in der Quellenkarte angezeigt. Andere Quellen laufen weiter. Fehlerzähler werden beim Neustart zurückgesetzt.

### Wie funktionieren Screenshots?

Bei Screenshot-Quellen wird der erste Feed-Link mit Chromium geöffnet. Bekannte Cookie-Banner werden entfernt und ein vollständiger PNG-Screenshot wird gespeichert.

### Warum gibt es JSONL und SQLite?

JSONL eignet sich als einfaches, offenes Archivformat. SQLite wird für schnelle Abfragen in der WebUI verwendet. Beide Speicher enthalten dieselben Meldungen und führen getrennte Hash-Ketten.

### Werden Nachrichten nachträglich verändert?

Gespeicherte Datensätze werden nicht überschrieben oder gelöscht. Neue Fassungen oder neue Veröffentlichungen werden als eigene Datensätze aufgenommen.

### In welcher Zeitzone werden Zeiten gespeichert?

Zeitstempel werden einheitlich in UTC gespeichert. Die WebUI wandelt sie für die Anzeige in die lokale Zeitzone des Browsers um.

### Was passiert beim Neustart?

Die archivierten Meldungen, Bilder und OpenTimestamps-Proofs bleiben erhalten. Laufzeit-Logs, Fehlerzähler und der aktuelle Anchor-Status werden nur flüchtig gehalten und beginnen nach einem Neustart neu.

### Kann ich einen einzelnen Feed sofort aktualisieren?

Ja. Klicke auf der Quellenkarte auf `Jetzt abrufen`. Bereits bekannte Meldungen werden übersprungen, damit insbesondere Screenshot- und Artikel-Codecs nicht unnötig erneut ausgeführt werden.

## Weitere Informationen

Die technischen Prometheus-Metriken sind unter [`/metrics`](/metrics) verfügbar.

## Transparenzhinweis

News-Hash wurde bei der Entwicklung mit dem KI-Tool [OpenCode](https://opencode.ai/) erstellt und weiterentwickelt.
