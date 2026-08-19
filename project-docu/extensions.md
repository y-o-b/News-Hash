# Mögliche Erweiterungen

Dieses Dokument sammelt mögliche Erweiterungen für News-Hash. Die Punkte sind Vorschläge und noch keine beschlossenen Anforderungen. Jede Erweiterung hat einen eigenen Kommentarbereich für Rückfragen, Hinweise und Entscheidungen.

## 1. Unabhängiger Verifizierer

**Status: weiterverfolgen**

### Ziel

Ein kleines, eigenständiges Prüfwerkzeug soll SQLite-Dateien ohne die vollständige News-Hash-Anwendung verifizieren können. Die Umsetzung soll beispielsweise in Go erfolgen, damit ein einzelnes Programm ohne Laufzeit- oder Paketabhängigkeiten verteilt werden kann.

### Möglicher Umfang

- Prüfung von Hashkette, Codec-Definitionen, Bild-BLOBs und Anchor-Artefakten
- Veröffentlichung als einzelnes Go-Kommandozeilenprogramm
- Dokumentierte Prüfschritte für Dritte

### Offene Fragen

- Soll der Verifizierer ausschließlich SQLite unterstützen oder zusätzlich JSONL?
- Soll er ohne Netzwerkzugriff arbeiten können?
- Welche externen Bestandteile dürfen als vertrauenswürdig vorausgesetzt werden?

### Kommentar / Fragen

- Die Go-Implementierung soll zunächst SQLite-Dateien und die in GitHub veröffentlichten Manifeste prüfen können.

## 2. Vollständige Bildintegritätsprüfung

**Status: optional ergänzen**

### Ziel

Der Validator soll nicht nur die Bildreferenzen im Record hashen, sondern auch prüfen, ob jeder referenzierte Bild-Hash zu einem vorhandenen und unveränderten BLOB gehört.

### Möglicher Umfang

- SHA-256-Prüfung jedes BLOBs gegen seinen Schlüssel in `record_images`
- Erkennung fehlender oder nicht referenzierter BLOBs
- Optionaler Abgleich zwischen SQLite-BLOBs und Dateien unter `data/images/`

### Offene Fragen

- Sollen zusätzliche, nicht referenzierte BLOBs nur als Hinweis ausgegeben werden?
- Die Prüfung soll über eine Option aktiviert werden; soll diese Option nur die BLOB-Prüfung oder auch den Datei-Abgleich einschalten?

### Kommentar / Fragen

- Zusätzliche BLOBs gelten nur als Hinweis. Die Prüfung wird optional aktiviert.


## 3. Unveränderliche Exportpakete

**Status: neu bewerten**

### Ziel

Für JSONL soll ein separates Archivpaket die zugehörigen Daten und Metadaten transportierbar bündeln. SQLite enthält die für seine Validierung notwendigen Definitionen und Anchor-Artefakte bereits selbst; ein zusätzliches SQLite-Archivformat ist deshalb nicht erforderlich. Das Kopieren einer SQLite-Datei bleibt als Backup oder Transport möglich.

### Möglicher Umfang

- JSONL-Shards, Codec-Definitionen, Manifeste und Proofs
- Prüfsummen und maschinenlesbare Exportbeschreibung
- Prüfung des Pakets ohne laufenden Daemon

### Offene Fragen

- Welches Format soll das JSONL-Paket haben, zum Beispiel ZIP oder TAR?
- Sollen JSONL-Exporte verschlüsselt oder signiert werden?
- Soll ein Export einzelne Quellen, Zeiträume oder nur vollständige Archive umfassen?

### Kommentar / Fragen

- Für JSONL und SQLite gelten getrennte Archivierungswege. Ein zusätzliches SQLite-Archivformat ist nicht notwendig, weil die SQLite-Datei bereits selbstständig validierbar ist.

## 4. Erweiterte Quellenadapter

**Status: nach Beispieldaten weiterverfolgen**

### Ziel

Weitere Nachrichtenquellen sollen ohne Änderungen an der allgemeinen Importlogik angebunden werden können. Der Daemon soll Änderungen oder ungültige Antworten einer Quelle als Fehler melden, ohne die Verarbeitung der übrigen Quellen zu stoppen.

### Möglicher Umfang

- Adapter für weitere Feed-Formate oder APIs
- Quellenspezifische Extraktion von Artikeltext, Bildern und Veröffentlichungszeitpunkten
- Testdatensätze pro Adapter ohne Netzwerkzugriff

### Offene Fragen

- Soll eine Quelle mehrere Fallback-Adapter besitzen dürfen?
- Wie werden Änderungen an einer externen Quelle erkannt und als Fehler versioniert?
- Sollen Adapter als Python-Code oder als deklarative Konfiguration definiert werden?

### Kommentar / Fragen

- Für weitere Formate und APIs werden zunächst konkrete Beispielquellen und repräsentative Testdaten benötigt. Erst danach soll die Adapter-Schnittstelle festgelegt werden.

## 5. Wiederholungs- und Fehlerwarteschlange

**Status: zurückgestellt**

### Ziel

Fehlgeschlagene Artikelabrufe sollen gezielt erneut verarbeitet werden können, ohne die gesamte Quelle manuell neu zu starten.

### Möglicher Umfang

- Persistente Warteschlange für Netzwerk- und Interpretationsfehler
- Exponentielle Wiederholungen mit Obergrenze
- Dashboard-Aktion für erneuten Versuch und endgültiges Verwerfen
- Trennung zwischen vorübergehenden und dauerhaften Fehlern

### Aktueller Stand

Die Umsetzung wird zurückgestellt, bis mehr unterschiedliche Fehlerfälle bekannt sind. Für die bisher beobachteten Fehler gibt es bereits eine Fehlerbehandlung im Importpfad.

### Kommentar / Fragen

Die Erweiterung soll erst nach einer Auswertung weiterer Fehlermöglichkeiten geplant werden.

## 6. Suche und erweiterte Archivabfragen

**Status: zurückgestellt**

### Ziel

Das Dashboard soll auch in älteren Shards nach Meldungen suchen und Ergebnisse nach Zeitraum, Quelle oder Codec filtern können.

### Möglicher Umfang

- Volltextsuche über Titel und Inhalt
- Filter für Quellen, Veröffentlichungszeitraum, Codec und Integritätsstatus
- Paginierte Suche über alle SQLite-Shards
- Optionaler Export der Trefferliste

### Aktueller Stand

Die Umsetzung wird zurückgestellt, bis mehr Archivdaten gesammelt wurden und die tatsächlichen Suchanforderungen anhand konkreter Nutzung bewertet werden können.

### Kommentar / Fragen

Die Erweiterung soll später auf Grundlage realer Daten und Nutzungsszenarien neu bewertet werden.

## 7. Zugriffsschutz für die WebUI

**Status: nicht im Scope der App**

### Ziel

Der Zugriffsschutz wird nicht innerhalb der App umgesetzt. Für einen sicheren Betrieb in geschützten Netzen soll die Dokumentation auf einen vorgeschalteten Reverse Proxy verweisen.

### Möglicher Umfang

- Betrieb hinter einem konfigurierten Reverse Proxy
- Authentifizierung und TLS außerhalb der App

### Dokumentationshinweis

Die Betriebsdokumentation sollte erklären, dass der integrierte Webserver selbst keine Benutzerverwaltung bereitstellt und für öffentliche oder nicht vertrauenswürdige Netze hinter einem Reverse Proxy betrieben werden muss.

### Kommentar / Fragen

Nicht im Scope der App. Ein Hinweis auf den Reverse-Proxy-Betrieb gehört in die Betriebsdokumentation.

## 8. Persistentes Betriebs- und Fehlerprotokoll

**Status: nicht geplant**

### Ziel

Ein persistentes Betriebs- und Fehlerprotokoll ist derzeit nicht notwendig. Fehler werden nach `stderr` geschrieben; in einem Docker-Betrieb übernimmt Docker die Protokollierung.

### Möglicher Umfang

- Weiterhin flüchtige Anzeige der Laufzeitfehler im Dashboard
- Nutzung des Container- oder Prozess-Logs für dauerhafte Betriebsprotokolle

### Aktueller Stand

Eine spätere Neubewertung ist nur erforderlich, wenn die externe Logverwaltung nicht ausreicht.

### Kommentar / Fragen

Nicht erforderlich: Fehler werden über `stderr` ausgegeben; im Docker-Betrieb kann Docker diese Ausgaben übernehmen.

## 9. Mehrere Anchor- und Veröffentlichungsziele

**Status: mit Fokus auf Verifizierung zurückgestellt**

### Ziel

Weitere Anchor-Provider werden erst bewertet, wenn konkrete und geeignete Provider bekannt sind. Die Nachrichteninhalte bleiben aus rechtlichen Gründen lokal.

### Möglicher Umfang

- Erweiterung des Verifizierers, damit die auf GitHub veröffentlichten Manifeste zur Prüfung der gespeicherten Hashes verwendet werden können
- Spätere Unterstützung weiterer Provider, falls konkrete Anforderungen entstehen

### Offene Fragen

- Welche weiteren Provider sind verfügbar und langfristig vertrauenswürdig?
- Wie werden widersprüchliche Provider-Ergebnisse dargestellt?

### Kommentar / Fragen

Weitere Provider müssen zunächst konkret benannt werden. Vorrangig soll der Verifizierer GitHub-Manifeste für die Prüfung nutzen können. Nachrichteninhalte bleiben lokal.

## 10. Datenschutz und Löschkonzept

**Status: weiter ausarbeiten**

### Ziel

Das Archiv soll nachvollziehbar mit personenbezogenen Daten, Korrekturen und gesetzlichen Löschanforderungen umgehen können.

### Möglicher Umfang

- Erkennung und Kennzeichnung personenbezogener Inhalte
- Dokumentierter Umgang mit Lösch- oder Korrekturanfragen
- Kryptografisches Ausblenden einzelner Inhalte bei Erhalt der Kettenstruktur
- Transparente Trennung zwischen Originalnachweis und öffentlich sichtbarer Darstellung

### Nächster Ansatz

Ein neuer Eintrag könnte dokumentieren, dass der Inhalt eines älteren Eintrags entfernt oder verborgen wurde. Die ursprüngliche Hashkette bliebe dadurch nachvollziehbar, während der aktuelle Inhalt nicht mehr öffentlich angezeigt wird.

### Kommentar / Fragen

Die rechtliche und technische Ausgestaltung muss noch geklärt werden.
