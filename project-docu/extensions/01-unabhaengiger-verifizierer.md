# Unabhängiger Verifizierer

**Status: weiterverfolgen**

## Ziel

Ein eigenständiges Prüfwerkzeug soll SQLite-Dateien ohne die vollständige News-Hash-Anwendung verifizieren können. Die Umsetzung soll beispielsweise in Go erfolgen, damit ein einzelnes Programm ohne Laufzeit- oder Paketabhängigkeiten verteilt werden kann.

## Möglicher Umfang

- Prüfung von Hashkette, Codec-Definitionen, Bild-BLOBs und Anchor-Artefakten
- Veröffentlichung als einzelnes Go-Kommandozeilenprogramm
- Dokumentierte Prüfschritte für Dritte

## Offene Fragen

- Soll der Verifizierer ausschließlich SQLite unterstützen oder zusätzlich JSONL?
- Soll er ohne Netzwerkzugriff arbeiten können?
- Welche externen Bestandteile dürfen als vertrauenswürdig vorausgesetzt werden?

## Kommentar / Fragen

- Die Go-Implementierung soll zunächst SQLite-Dateien und die in GitHub veröffentlichten Manifeste prüfen können.
