# Veröffentlichung auf PyPI

**Status: vorgeschlagen**

## Ziel

Das Python-Paket soll reproduzierbar gebaut und als öffentliche Version auf PyPI veröffentlicht werden, damit Installation und Nutzung außerhalb des Repositorys möglich werden.

## Möglicher Umfang

- Prüfung und Vervollständigung der Paketmetadaten, Lizenz und Projektbeschreibung
- Reproduzierbarer Build von Wheel und Source Distribution
- Veröffentlichung über einen geschützten CI-Workflow mit PyPI-Trusted Publishing
- Dokumentierte Installations- und Upgrade-Schritte
- Klare Abgrenzung zwischen der Python-Anwendung und dem geplanten unabhängigen Go-Verifizierer

## Voraussetzungen

- Eine verbindliche Lizenz ist festgelegt.
- Die öffentliche Paketbeschreibung und die Endnutzer-Dokumentation sind vollständig.
- Versionsnummern und Veröffentlichungsworkflow sind abgestimmt.
- Geheimnisse werden nicht als langlebige CI-Token im Repository gespeichert.

## Offene Fragen

- Soll das Paket unter `newshash` oder einem anderen Namen auf PyPI erscheinen?
- Welche Teile der Anwendung sollen mit dem Paket veröffentlicht werden?
- Soll jede Version automatisch veröffentlicht werden oder nur markierte Releases?
- Welche Python-Versionen sollen unterstützt werden?

## Kommentar / Fragen

<!-- Hier Kommentare, Rückfragen und Entscheidungen zu dieser Erweiterung eintragen. -->
