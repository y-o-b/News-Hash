# News-Hash

News-Hash is a local news archive with a verifiable history. The application reads configured news sources, normalizes new reports, and stores them permanently in an append-only data structure. Every report remains traceable through its timestamp, source, and hash history.

Deutsche Version: [README.de.md](README.de.md)

The Python application is located under `app/`. The static GitHub Pages website is located under `docs/`. The binding project and product documentation is located under `project-docu/`.

The external proofs and operational monitoring are particularly important: hash manifests are anchored in the Bitcoin blockchain through OpenTimestamps and their `.ots` proofs are additionally published with Git in a GitHub repository. The running system can be monitored through an optional heartbeat and Prometheus metrics.

> Built with AI, refined with care, for curious people

## Table of contents

- [Architecture](#architecture)
- [Directory structure](#directory-structure)
- [Requirements](#requirements)
- [Installation and startup](#installation-and-startup)
- [Configuration](#configuration)
- [Data flow](#data-flow)
- [Storage and shards](#storage-and-shards)
- [Hash chains](#hash-chains)
- [Codecs](#codecs)
- [Daemon and WebUI](#daemon-and-webui)
- [Integrity proofs](#integrity-proofs)
- [Monitoring](#monitoring)
- [Anchoring and GitHub synchronization](#anchoring-and-github-synchronization)
- [Docker](#docker)
- [Tests and quality assurance](#tests-and-quality-assurance)
- [Development rules](#development-rules)

## Architecture

News-Hash consists of a CLI program, an import and normalization layer, replaceable source codecs, two parallel stores, and an embedded HTTP web UI.

The application operates without a public blockchain and without external consensus mechanisms. The internal chain is an append-only sequence of records. Each new record references the hash of the preceding record. This makes later changes to content or order detectable.

JSONL and SQLite are deliberately maintained in parallel. Both stores use the same hash material, but each has an independent chain. This allows consistent recovery if a process is terminated, for example, between two write operations.

## Directory structure

```text
app/
├── data/                    Runtime data, settings, and credentials
├── src/newshash/            Application code
├── tests/                   Unit and integration tests
├── pyproject.toml           Package metadata and tool configuration
└── uv.lock                 Reproducible dependencies
docs/                        Static GitHub Pages website
project-docu/                Binding project and product documentation
anchors/                     Publicly synchronized anchor files
docker-compose.yml           Container deployment
```

Runtime data under `app/data/` includes SQLite files, JSONL files, images, and local anchor files. Credentials are read from `app/data/credentials.env` and are never logged.

## Requirements

- Python 3.14 or compatible
- `uv`
- For `SCREENv0`: Playwright with Chromium installed
- For OpenTimestamps: the `ots` command
- For GitHub synchronization: a GitHub token and repository in `data/credentials.env`

Python dependencies are managed through `pyproject.toml` and `uv.lock`. The application uses, among other packages, `requests`, `markdown`, `playwright`, and `opentimestamps-client`.

## Installation and startup

Run all Python and test commands from `app/`:

```bash
cd app
uv sync --dev
uv run newshash
```

A single run retrieves each configured source exactly once. Start the daemon for continuous operation:

```bash
uv run newshash --daemon
```

OpenTimestamps can be explicitly enabled for a single run:

```bash
uv run newshash --ots
```

Available CLI options:

- `--settings <path>` loads an alternative TOML file.
- `--daemon` starts continuous polling with the web UI.
- `--ots` enables anchoring for a single run.
- `--host <address>` sets the web UI bind address.
- `--port <number>` sets the web UI HTTP port.
- `--version` displays the installed application version.

By default, the web UI binds to `0.0.0.0:8000` in daemon mode. Restrict the bind address for local tests:

```bash
uv run newshash --daemon --host 127.0.0.1 --port 8000
```

Hash chains can be checked independently of feed retrieval. By default, only the latest non-empty shard is checked:

```bash
uv run newshash-validate --settings data/settings.toml --data-dir data
```

Add `--all-shards` to validate every shard. Use `--source <storage_name>` to restrict validation to one source. The command checks both JSONL and SQLite and exits with status 1 when a chain is invalid.

## Configuration

The default file is `app/data/settings.toml`. It must contain at least one `[[sources]]` block. A complete source block looks like this:

```toml
[[sources]]
name = "Tagesschau"
feed_url = "https://example.org/feed.json"
storage_name = "tagesschau"
codec_name = "RSSv0"
poll_interval_seconds = 300
```

The fields mean:

- `name` is the display name in the web UI.
- `feed_url` is the URL of the JSON or XML feed.
- `storage_name` determines the JSONL and SQLite shard file names.
- `codec_name` selects source-specific processing. The default is `RSSv0`.
- `poll_interval_seconds` determines the individual polling interval in the daemon.

An optional heartbeat target can be specified at the top level:

```toml
heartbeat_url = "https://example.org/heartbeat"
```

If `heartbeat_url` is not set or is empty, no heartbeat is sent. The application does not use a hard-coded heartbeat address.

## Data flow

Each time a source is processed, a report passes through these steps:

1. The configured feed is retrieved over HTTP.
2. JSON or XML is converted into the internal feed format.
3. The selected codec normalizes the title, content, URL, author, and timestamps.
4. Already known `source_id` values are skipped before expensive processing steps.
5. Linked images or source-specific content are loaded if the codec requires it.
6. The next hash is calculated separately for JSONL and SQLite using each store's chain.
7. The new records are written to both storage formats.
8. A daily manifest is optionally created, anchored, and synchronized.

Errors from a source are counted, written to `stderr`, and retained in the running process for the dashboard and metrics. An error must not stop processing of other sources.

## Storage and shards

Each source creates files under `app/data/` following this pattern:

```text
<storage_name>.0.jsonl
<storage_name>.0.sqlite3
```

When a file reaches 1 GB, the next numbered shard is created. JSONL contains one JSON record per line. SQLite stores records in `records` and deduplicated image data in `record_images`.

JSONL image references point to relative files under `data/images/`. SQLite also stores the same image data as BLOBs so detail views can access archived data independently of the JSONL file.

Duplicate detection reads only the newest shard for each storage format. Metrics and detail access, on the other hand, use all shards. For performance reasons, the dashboard list uses only the newest SQLite shard.

If the schema of an existing SQLite table changes, the old table is renamed to `<table>_legacy_<timestamp>`. It is not deleted or overwritten automatically.

## Hash chains

For each record, canonical hash material is first built as a JSON object. Keys are sorted, no additional whitespace is used, and the UTF-8 representation is hashed. The algorithm is SHA-256.

The hash material for `RSSv0` includes:

- `author_name`
- `content`
- `codec_name`
- `images`
- `previous_hash`
- `published_at`
- `source_id`
- `source_url`
- `title`

The first record uses 64 zeroes as its `previous_hash`. Every subsequent record references the hash of the preceding record. `retrieved_at` is stored but does not contribute to the hash, so the same published content does not receive a different content hash after a later retrieval.

A record is valid if `previous_hash` points to the expected predecessor and `hash` matches the newly calculated value. The validation logic is in the codec and covered by tests.

## Codecs

Codecs encapsulate source-specific processing without burdening the general import logic with host names or special cases:

- `RSSv0` processes general JSON feeds and classic XML RSS. Timestamps are normalized to UTC and images are loaded from HTML content.
- `TAZv0` additionally retrieves the complete TAZ article through the feed link and uses its structured article text.
- `SCREENv0` opens the feed link with Chromium and stores a complete PNG page screenshot. Known consent and cookie banners are removed before capture.

New sources are added through additional `[[sources]]` blocks and an existing or new codec.

## Daemon and WebUI

The daemon processes each source according to its own interval and starts the embedded HTTP server in parallel. The web UI provides:

- Source cards with message, image, error, and anchor status
- Source filters and ten messages per page
- Detail pages with content, hashes, timestamps, and stored images
- Local browser times for internally stored UTC timestamps
- Five themes: `Comic`, `DarkMode`, `LightMode`, `Papier`, and `News`
- Runtime log and transient error display
- Controlled daemon shutdown
- Prometheus metrics at `/metrics`

Important endpoints are `/`, `/hilfe`, `/metrics`, `/meldung/<storage>/<source_id>`, `/media/<path>`, `/anchor/<storage>/<date>/<type>`, `/fetch`, and `/shutdown`.

The web UI has no user management or authentication. It must therefore not be exposed to a public network without protection.

## Integrity proofs

News-Hash provides two independent ways to trace the existence and origin of archive proofs:

1. OpenTimestamps anchors the hash manifests through Bitcoin. The manifest contains the current hashes of the JSONL and SQLite chains, but no news content. The OpenTimestamps proof can later verify that these hashes existed no later than the confirmed timestamp.
2. GitHub publishes the associated manifest and `.ots` files in a versioned repository. This keeps the proofs publicly discoverable and traceable through Git history. Unchanged files are not uploaded again.

The two methods serve different purposes: Bitcoin provides external time anchoring, while GitHub makes the proof files accessible and historically visible. Neither storage publishes the archived news content.

## Monitoring

Two monitoring options are available for continuous operation:

- The optional `heartbeat_url` is called by the daemon after polling steps and reports process operation to a configured monitoring service. No heartbeat is sent without this setting.
- `/metrics` provides Prometheus metrics for configured sources, stored reports, images, and source errors. Prometheus or a compatible monitoring service can query these metrics regularly.

Example heartbeat in `app/data/settings.toml`:

```toml
heartbeat_url = "https://example.org/heartbeat"
```

The heartbeat does not replace a functional integrity check. It shows that the daemon is running; the hash chains, OpenTimestamps proofs, and GitHub files enable later verification of the archived history.

## Anchoring and GitHub synchronization

After a successful source run, a manifest can be created for the UTC date under `data/anchors/<date>/`. The manifest contains the latest JSONL and SQLite hashes, but no news content. `ots stamp` submits the manifest to OpenTimestamps and creates the associated `.ots` file for Bitcoin-based time anchoring.

The status distinguishes between no anchor, a missing `.ots` file, pending attestation, and complete confirmation. Existing anchor files are compared by content before GitHub upload. Unchanged files are not uploaded again with `PUT`, preventing unnecessary Git commits.

The following values are expected in `app/data/credentials.env` for synchronization:

```text
GITHUB_TOKEN=<token>
GITHUB_REPOSITORY=<owner>/<repository>
```

The token is not logged. GitHub synchronization does not take place without complete credentials.

## Docker

`docker-compose.yml` builds an image based on Python 3.14, installs the dependencies and Chromium, and starts the daemon. The project documentation is copied into the image as `project-docu/` and the application code as `src/`.

Runtime data is mounted to `/app/data` through a volume. Container name, image, data path, and network values are supplied through the Compose environment. The container binds to port 8000 inside the container by default.

## Tests and quality assurance

Run tests from `app/`:

```bash
uv run pytest
uv run ruff check .
uv run ruff format . --check
```

The tests cover settings validation, feed normalization, hash chains, sharding, the SQLite schema, anchoring, GitHub synchronization, daemon polling, and web UI rendering, among other areas. Screenshot tests require Chromium; they load pages with `domcontentloaded` and a short render wait instead of `networkidle`.

## Development rules

- The patch level is increased for every code change.
- The version in `app/pyproject.toml`, `app/src/newshash/__init__.py`, and `app/uv.lock` remains synchronized.
- Changes only to the static website under `docs/` do not increase the application patch level.
- Completed changes are recorded in a separate commit each.
- Architecture decisions and relevant requirements are maintained under `project-docu/`.

## Further documentation

- `project-docu/architecture.md` describes the architecture and hash calculation.
- `project-docu/requirements.md` describes mandatory, optional, and out-of-scope requirements.
- `project-docu/webui.md` describes web UI usage and endpoints.
- `project-docu/description_for_enduser.md` is the detailed German user help.
- `project-docu/description_for_enduser_en.md` is the English user help.
- `docs/` contains only the static GitHub Pages website.

## License

News-Hash is released under the [MIT License](LICENSE).
