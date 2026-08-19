# Roadmap

Diese Roadmap ordnet die möglichen Erweiterungen nach Priorität und Abhängigkeiten. Sie ist eine Planungshilfe und keine beschlossene Releaseplanung. Jeder Vorschlag ist als eigene Datei dokumentiert; Rückfragen und Entscheidungen können direkt im jeweiligen Kommentarbereich festgehalten werden.

## Leitlinien

- Integrität und unabhängige Verifizierung haben Vorrang vor Komfortfunktionen.
- Erweiterungen werden erst umgesetzt, wenn ihre offenen Fragen anhand von Beispieldaten oder realer Nutzung beantwortet werden können.
- Rechtliche und betriebliche Grenzen werden vor einer technischen Umsetzung geklärt.
- Zurückgestellte Vorschläge bleiben dokumentiert, erzeugen aber keinen kurzfristigen Implementierungsauftrag.

## Phase 1: Verifizierung stärken

Diese Phase verbessert den unabhängigen Nachweis der bereits archivierten Daten.

1. [Unabhängiger Verifizierer](01-unabhaengiger-verifizierer.md)
   Umsetzung als möglichst einzelnes Go-Programm ohne Laufzeit- oder Paketabhängigkeiten.
2. [Vollständige Bildintegritätsprüfung](02-bildintegritaetspruefung.md)
   Optionaler Prüfschritt für Bild-BLOBs; zusätzliche BLOBs werden nur als Hinweis gemeldet.
3. [Mehrere Anchor- und Veröffentlichungsziele](09-anchor-provider.md)
   Zunächst wird der Verifizierer um die Nutzung der bei GitHub veröffentlichten Manifeste erweitert. Weitere Provider werden erst danach bewertet.

**Abhängigkeit:** Der unabhängige Verifizierer bildet die Grundlage für die Prüfung von GitHub-Manifesten und zusätzliche Integritätsprüfungen.

## Phase 2: Archivierung ausbauen

Diese Phase verbessert Transport und Nutzung der gespeicherten Archive, sobald ausreichend reale Daten vorhanden sind.

1. [Unveränderliche Exportpakete](03-exportpakete.md)
   Zunächst ein separates Paketformat für JSONL. SQLite wird als bereits selbstständig validierbare Datei kopiert und benötigt kein zusätzliches Archivformat.
2. [Suche und erweiterte Archivabfragen](06-archivsuche.md)
   Neubewertung anhand realer Archivgrößen und konkreter Suchanforderungen.

**Abhängigkeit:** Die Anforderungen an Export und Suche sollen aus dem tatsächlichen Datenbestand abgeleitet werden.

## Phase 3: Quellen und Betrieb

Diese Phase wird erst nach weiteren Erfahrungen mit Quellen und Fehlerfällen begonnen.

1. [Erweiterte Quellenadapter](04-quellenadapter.md)
   Zuerst Beispielquellen und repräsentative Testdaten sammeln; danach die Adapter-Schnittstelle festlegen.
2. [Wiederholungs- und Fehlerwarteschlange](05-fehlerwarteschlange.md)
   Fehlerklassen und Wiederholungsregeln aus weiteren realen Importfehlern ableiten.

**Abhängigkeit:** Beide Erweiterungen benötigen mehr konkrete Quellen- und Fehlerdaten.

## Nicht innerhalb der App geplant

1. [Zugriffsschutz für die WebUI](07-webui-zugriffsschutz.md)
   Authentifizierung und TLS werden außerhalb der App, beispielsweise durch einen Reverse Proxy, bereitgestellt.
2. [Persistentes Betriebs- und Fehlerprotokoll](08-betriebsprotokoll.md)
   `stderr` und die Protokollierung der Container- oder Prozessumgebung bleiben ausreichend.
3. [Datenschutz und Löschkonzept](10-datenschutz-und-loeschkonzept.md)
   Die fachliche und rechtliche Ausgestaltung muss vor einer technischen Umsetzung weiter geklärt werden.

## Statusübersicht

| Nr. | Erweiterung | Status |
| --- | --- | --- |
| 01 | [Unabhängiger Verifizierer](01-unabhaengiger-verifizierer.md) | Weiterverfolgen |
| 02 | [Vollständige Bildintegritätsprüfung](02-bildintegritaetspruefung.md) | Optional ergänzen |
| 03 | [Unveränderliche Exportpakete](03-exportpakete.md) | Neu bewerten |
| 04 | [Erweiterte Quellenadapter](04-quellenadapter.md) | Nach Beispieldaten weiterverfolgen |
| 05 | [Wiederholungs- und Fehlerwarteschlange](05-fehlerwarteschlange.md) | Zurückgestellt |
| 06 | [Suche und erweiterte Archivabfragen](06-archivsuche.md) | Zurückgestellt |
| 07 | [Zugriffsschutz für die WebUI](07-webui-zugriffsschutz.md) | Nicht im Scope der App |
| 08 | [Persistentes Betriebs- und Fehlerprotokoll](08-betriebsprotokoll.md) | Nicht geplant |
| 09 | [Mehrere Anchor- und Veröffentlichungsziele](09-anchor-provider.md) | Mit Fokus auf Verifizierung zurückgestellt |
| 10 | [Datenschutz und Löschkonzept](10-datenschutz-und-loeschkonzept.md) | Weiter ausarbeiten |

## Neubewertung

Die Roadmap sollte nach einem größeren Archivierungszeitraum oder bei neuen Anforderungen überprüft werden. Besonders relevant sind dann:

- die tatsächliche Anzahl und Größe der SQLite- und JSONL-Shards
- die Zahl und Art der Importfehler
- die benötigten Such- und Exportfälle
- verfügbare unabhängige Anchor-Provider
- rechtliche Anforderungen an Inhaltsentfernung und Nachweise
