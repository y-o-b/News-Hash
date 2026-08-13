# News-Hash

## The idea behind the project: preserving news for traceability

News changes quickly. An article may later be edited, shortened, moved, or removed entirely. As a result, it can be difficult to determine what was actually published at a particular point in time.

News-Hash addresses this problem by regularly retrieving news from different sources and preserving immutable snapshots. Each new record receives a cryptographic hash and references the hash of the preceding record. This creates a continuous chain for each storage format.

If a stored record is changed later, its hash no longer matches. This makes tampering visible. The hash chain does not prove that the journalism is correct. It does show whether the stored version was changed after archiving.

Data is stored in JSONL and SQLite in parallel. JSONL is easy to archive and readable by many tools. SQLite enables fast queries for the web UI. Both stores maintain their own chain so that a failure in one format does not compromise the integrity of the other.

Special sources use dedicated codecs. The regular RSS processing handles structured JSON and XML feeds. The TAZ codec additionally downloads the complete article. The screenshot codec opens the first link of a source with Chromium, removes known cookie banners, and preserves a full visual snapshot.

Once a day, the current hashes of both storage chains are combined in a small manifest. The manifest contains no news content. It is anchored publicly with OpenTimestamps and connected to the Bitcoin timeline. This makes it possible to prove that these hashes existed no later than that point in time.

The project combines three layers: a local archive for content, hash chains for internal traceability, and a public timestamp anchor for independent proof of existence. The blockchain does not store the news, only the cryptographic fingerprint of the local archive.

## Using the dashboard

- Click a source's message count to filter the message list.
- Use `Filter zurücksetzen` to show all sources again.
- The message list contains ten messages per page.
- Use `Erste`, `Zurück`, `Weiter`, and `Letzte` to navigate.
- Click a message title to open its stored detail page.
- `Jetzt abrufen` immediately fetches one source.
- The countdown ring next to `Live-Übersicht` refreshes the page automatically or immediately when clicked.

## Themes

The theme selector is at the bottom next to `Daemon beenden`.

- `LightMode` is the default.
- `Comic` uses colorful cards and changing shadows.
- `DarkMode` uses a dark, restrained color palette.
- `Papier` is inspired by a newspaper.
- `News` uses a restrained news design with red accents.

## Anchor status

- `Kein Anchor`: No manifest exists for the current UTC day.
- `Keine .ots-Datei`: The manifest exists, but no proof has been created yet.
- `Attestation ausstehend`: OpenTimestamps confirmation is still pending.
- `Vollständig bestätigt`: A complete attestation path is available.

The manifest and `.ots` file can be downloaded directly from the source card. Verification is also possible through [OpenTimestamps](https://opentimestamps.org/).
Available anchor files are also published in the public GitHub repository `y-o-b/News-Hash` under `anchors/<UTC-date>/`.

Current hash values can also be preserved using the browser's print function. The print view hides controls, filters, logs, and anchor links, making it suitable as a paper-based record of the visible hashes.

## FAQ

### What does the hash mean?

The hash identifies the content of a record. Each record also contains the hash of the preceding record and therefore forms part of a traceable chain.

### What is stored in the anchor?

OpenTimestamps receives only a manifest containing the hashes of the two local chains. News content is not transferred to the blockchain.

### How can an anchor be verified?

Download the manifest and its `.ots` file from the source card and run:

```bash
ots verify <manifest>.txt.ots
```

A local Bitcoin Core node is required for fully independent Bitcoin verification. Without one, the proof can still be checked for available attestation paths and the _Timestamp complete_ status.


### Why do I not see a message immediately?

The daemon fetches sources according to their configured intervals. The web UI refreshes automatically.

### What happens when a source fails?

The error is logged and shown on the source card. Other sources continue running. Error counters are reset when the process restarts.

### How do screenshots work?

For screenshot sources, `SCREENv0` opens the first feed link with Chromium, removes known cookie banners, and saves a complete PNG screenshot.

## Further information

Technical Prometheus metrics are available at [`/metrics`](/metrics).

## Transparency note

News-Hash was created and further developed with the AI tool [OpenCode](https://opencode.ai/).
