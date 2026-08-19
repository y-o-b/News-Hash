# Mögliche Erweiterungen

Dieses Dokument sammelt mögliche Erweiterungen für News-Hash. Die Punkte sind Vorschläge und noch keine beschlossenen Anforderungen. Jede Erweiterung hat einen eigenen Kommentarbereich für Rückfragen, Hinweise und Entscheidungen.

## 1. Unabhängiger Verifizierer

### Ziel

Ein kleines, eigenständiges Prüfwerkzeug soll SQLite-Dateien ohne die vollständige News-Hash-Anwendung verifizieren können.

### Möglicher Umfang

- Prüfung von Hashkette, Codec-Definitionen, Bild-BLOBs und Anchor-Artefakten
- Veröffentlichung als einzelnes Python-Modul oder Kommandozeilenprogramm
- Dokumentierte Prüfschritte für Dritte

### Offene Fragen

- Soll der Verifizierer ausschließlich SQLite oder auch JSONL unterstützen?
- Soll er ohne Netzwerkzugriff arbeiten können?
- Welche externen Bestandteile dürfen als vertrauenswürdig vorausgesetzt werden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 2. Vollständige Bildintegritätsprüfung

### Ziel

Der Validator soll nicht nur die Bildreferenzen im Record hashen, sondern auch prüfen, ob jeder referenzierte Bild-Hash zu einem vorhandenen und unveränderten BLOB gehört.

### Möglicher Umfang

- SHA-256-Prüfung jedes BLOBs gegen seinen Schlüssel in `record_images`
- Erkennung fehlender, zusätzlicher oder nicht referenzierter BLOBs
- Optionaler Abgleich zwischen SQLite-BLOBs und Dateien unter `data/images/`

### Offene Fragen

- Sollen zusätzliche, nicht referenzierte BLOBs als Fehler oder nur als Hinweis gelten?
- Soll die Prüfung standardmäßig oder über eine Option aktiviert werden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 3. Unveränderliche Exportpakete

### Ziel

Ein Archivexport soll alle für eine Quelle oder einen Zeitraum notwendigen Daten in einem transportierbaren Paket bündeln.

### Möglicher Umfang

- SQLite-Shards, Codec-Definitionen, Manifeste und Proofs
- Prüfsummen und maschinenlesbare Exportbeschreibung
- Import- oder Reparaturprüfung ohne laufenden Daemon

### Offene Fragen

- Welches Format soll das Paket haben, zum Beispiel ZIP oder TAR?
- Sollen Exporte verschlüsselt oder signiert werden?
- Soll ein Export einzelne Quellen, Zeiträume oder nur vollständige Archive umfassen?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 4. Erweiterte Quellenadapter

### Ziel

Weitere Nachrichtenquellen sollen ohne Änderungen an der allgemeinen Importlogik angebunden werden können.

### Möglicher Umfang

- Adapter für weitere Feed-Formate oder APIs
- Quellenspezifische Extraktion von Artikeltext, Bildern und Veröffentlichungszeitpunkten
- Testdatensätze pro Adapter ohne Netzwerkzugriff

### Offene Fragen

- Soll eine Quelle mehrere Fallback-Adapter besitzen dürfen?
- Wie werden Änderungen an einer externen Quelle erkannt und versioniert?
- Sollen Adapter als Python-Code oder als deklarative Konfiguration definiert werden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 5. Wiederholungs- und Fehlerwarteschlange

### Ziel

Fehlgeschlagene Artikelabrufe sollen gezielt erneut verarbeitet werden können, ohne die gesamte Quelle manuell neu zu starten.

### Möglicher Umfang

- Persistente Warteschlange für Netzwerk- und Interpretationsfehler
- Exponentielle Wiederholungen mit Obergrenze
- Dashboard-Aktion für erneuten Versuch und endgültiges Verwerfen
- Trennung zwischen vorübergehenden und dauerhaften Fehlern

### Offene Fragen

- Welche Fehler dürfen automatisch wiederholt werden?
- Wie lange sollen fehlgeschlagene Einträge aufbewahrt werden?
- Soll ein erneuter Versuch die ursprüngliche Hashkette oder einen neuen Importlauf verwenden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 6. Suche und erweiterte Archivabfragen

### Ziel

Das Dashboard soll auch in älteren Shards nach Meldungen suchen und Ergebnisse nach Zeitraum, Quelle oder Codec filtern können.

### Möglicher Umfang

- Volltextsuche über Titel und Inhalt
- Filter für Quellen, Veröffentlichungszeitraum, Codec und Integritätsstatus
- Paginierte Suche über alle SQLite-Shards
- Optionaler Export der Trefferliste

### Offene Fragen

- Reicht SQLite FTS5 oder wird eine externe Suchkomponente benötigt?
- Soll die Suche HTML-Inhalte oder zusätzlich extrahierten Klartext durchsuchen?
- Wie sollen sehr große Suchergebnisse begrenzt werden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 7. Zugriffsschutz für die WebUI

### Ziel

Der integrierte Webserver soll sicher in Netzen betrieben werden können, in denen die Daten nicht öffentlich zugänglich sein dürfen.

### Möglicher Umfang

- Authentifizierung für Dashboard, Quellenaktionen und Shutdown
- Rollen für Lesen, manuellen Abruf und Administration
- Bind-Adresse standardmäßig auf lokale Schnittstellen beschränken
- Optionaler Reverse-Proxy- oder Token-Betrieb

### Offene Fragen

- Ist ein einfacher Zugriffstoken ausreichend oder werden Benutzerkonten benötigt?
- Welche Endpunkte müssen auch ohne Anmeldung lesbar bleiben?
- Soll TLS durch die Anwendung oder durch einen Reverse Proxy bereitgestellt werden?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 8. Persistentes Betriebs- und Fehlerprotokoll

### Ziel

Importfehler, Wiederholungen und Betriebsereignisse sollen auch nach einem Neustart nachvollziehbar bleiben.

### Möglicher Umfang

- Persistente Ereignistabelle mit Quelle, URL, Zeitpunkt, Fehlertyp und Status
- Aufbewahrungs- und Löschregeln
- Anzeige historischer Fehler im Dashboard
- Export für Support und Diagnose

### Offene Fragen

- Welche Daten dürfen dauerhaft gespeichert werden, insbesondere externe URLs?
- Soll das Protokoll in SQLite oder in einem separaten Logsystem liegen?
- Wie lange ist eine sinnvolle Aufbewahrungsfrist?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 9. Mehrere Anchor- und Veröffentlichungsziele

### Ziel

Anchor-Manifeste sollen neben OpenTimestamps an weitere unabhängige Nachweis- oder Veröffentlichungsziele übergeben werden können.

### Möglicher Umfang

- Austauschbare Anchor-Provider
- Unterstützung zusätzlicher Zeitstempel- oder Archivdienste
- Unveränderliche Veröffentlichung der Manifeste in mehreren Repositories
- Anzeige des Status je Provider

### Offene Fragen

- Welche Provider sind langfristig vertrauenswürdig und erreichbar?
- Wie werden widersprüchliche Provider-Ergebnisse dargestellt?
- Sollen Nachrichteninhalte weiterhin ausschließlich lokal bleiben?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->

## 10. Datenschutz und Löschkonzept

### Ziel

Das Archiv soll nachvollziehbar mit personenbezogenen Daten, Korrekturen und gesetzlichen Löschanforderungen umgehen können.

### Möglicher Umfang

- Erkennung und Kennzeichnung personenbezogener Inhalte
- Dokumentierter Umgang mit Lösch- oder Korrekturanfragen
- Kryptografisches Ausblenden einzelner Inhalte bei Erhalt der Kettenstruktur
- Transparente Trennung zwischen Originalnachweis und öffentlich sichtbarer Darstellung

### Offene Fragen

- Welche Daten gelten als unveränderlich und welche dürfen nachträglich verborgen werden?
- Wie lässt sich eine Löschung mit dem append-only-Ansatz vereinbaren?
- Welche rechtlichen Anforderungen gelten für die betriebenen Quellen und Standorte?

### Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->
