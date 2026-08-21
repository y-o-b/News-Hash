from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from requests import post

from newshash import __version__
from newshash.anchoring import OpenTimestampsAnchor
from newshash.codec import GENESIS_HASH, get_codec
from newshash.github_sync import GitHubAnchorPublisher
from newshash.settings import AppConfig, SettingsManager, SourceConfig
from newshash.storage import JsonlStorage, SqliteStorage, migrate_legacy_jsonl_and_images
from newshash.web import run_web_server


@dataclass(frozen=True)
class IngestResult:
    """Ergebnis des Imports einer einzelnen Quelle."""

    inserted_jsonl: int
    inserted_sqlite: int
    total_jsonl: int
    total_sqlite: int
    latest_hash_jsonl: str
    latest_hash_sqlite: str
    jsonl_path: Path
    sqlite_path: Path
    latest_shard_jsonl: int = 0
    latest_shard_sqlite: int = 0


def _error_text(exc: Exception) -> str:
    """Formatiere eine Exception für eine einzeilige Logmeldung."""

    return f"{type(exc).__name__}: {exc}".replace("\n", " | ")


def _log_source_error(source: SourceConfig, action: str, error: str) -> None:
    """Schreibe einen Quellenfehler sofort auf stderr."""

    print(f'source="{source.name}" action="{action}" error="{error}"', file=sys.stderr, flush=True)


def ingest_source(source: SourceConfig, settings_manager: SettingsManager) -> IngestResult:
    """Importiere neue Eintraege einer Quelle mit getrennten Hash-Ketten fuer JSONL und SQLite."""

    storage_root = settings_manager.storage_root()
    codec = get_codec(source.codec_name)

    jsonl_storage = JsonlStorage(storage_root, source.storage_name)
    sqlite_storage = SqliteStorage(storage_root, source.storage_name)
    settings_manager.log_runtime(f'source="{source.name}" action="fetch start"')

    jsonl_known_source_ids = jsonl_storage.known_source_ids()
    sqlite_known_source_ids = sqlite_storage.known_source_ids()
    jsonl_previous_hash = jsonl_storage.latest_hash(GENESIS_HASH)
    sqlite_previous_hash = sqlite_storage.latest_hash(GENESIS_HASH)

    try:
        feed = codec.fetch_feed(source.feed_url)
        if not isinstance(feed, dict) or not isinstance(feed.get("items"), list):
            raise ValueError("feed must contain an items list")
        if any(not isinstance(item, dict) or not item.get("id") for item in feed["items"]):
            raise ValueError("feed contains an invalid item")
    except Exception as exc:
        error = _error_text(exc)
        settings_manager.record_source_error(source.name, error)
        settings_manager.log_runtime(f'source="{source.name}" action="fetch error" error="{error}"')
        raise
    settings_manager.log_runtime(f'source="{source.name}" action="fetch finished" items={len(feed["items"])}')
    if source.codec_name.startswith("SCREEN"):
        unknown_items = [
            item for item in feed["items"] if str(item.get("id")) not in jsonl_known_source_ids or str(item.get("id")) not in sqlite_known_source_ids
        ]
        feed["items"] = unknown_items[:1]
    retrieved_at = codec.utc_now()
    image_root = storage_root / "JSONL" / source.storage_name / "images"

    jsonl_records: list[dict] = []
    sqlite_records: list[dict] = []
    image_bytes_by_hash: dict[str, bytes] = {}

    for item in feed.get("items", []):
        source_id = str(item.get("id"))
        needs_jsonl = source_id not in jsonl_known_source_ids
        needs_sqlite = source_id not in sqlite_known_source_ids
        if not needs_jsonl and not needs_sqlite:
            # Vor prepare_item überspringen, damit SCREENv0 keinen Browser startet.
            continue

        try:
            prepared_item, item_image_bytes = codec.prepare_item(item, retrieved_at, storage_root, image_root, storage_name=source.storage_name)
        except Exception as exc:
            error = f"{_error_text(exc)} url={item.get('url', '')}"
            settings_manager.record_source_error(source.name, error)
            settings_manager.log_runtime(f'source="{source.name}" action="interpret error" error="{error}"')
            _log_source_error(source, "interpret error", error)
            continue
        image_bytes_by_hash.update(item_image_bytes)

        if needs_jsonl:
            record = codec.finalize_record(prepared_item, jsonl_previous_hash)
            jsonl_records.append(record)
            jsonl_previous_hash = record["hash"]

        if needs_sqlite:
            record = codec.finalize_record(prepared_item, sqlite_previous_hash)
            sqlite_records.append(record)
            sqlite_previous_hash = record["hash"]

    jsonl_storage.append_records(jsonl_records)
    sqlite_storage.append_records(sqlite_records, image_bytes_by_hash)
    settings_manager.log_runtime(f'source="{source.name}" action="stored" jsonl={len(jsonl_records)} sqlite={len(sqlite_records)}')

    return IngestResult(
        inserted_jsonl=len(jsonl_records),
        inserted_sqlite=len(sqlite_records),
        total_jsonl=jsonl_storage.count(),
        total_sqlite=sqlite_storage.count(),
        latest_hash_jsonl=jsonl_storage.latest_hash(GENESIS_HASH),
        latest_hash_sqlite=sqlite_storage.latest_hash(GENESIS_HASH),
        latest_shard_jsonl=jsonl_storage.latest_shard_index(),
        latest_shard_sqlite=sqlite_storage.latest_shard_index(),
        jsonl_path=jsonl_storage.path,
        sqlite_path=sqlite_storage.path,
    )


def emit_source_result(source: SourceConfig, result: IngestResult) -> None:
    """Schreibe das Ergebnis eines Quellenimports in die Konsole."""

    print(
        f"source={source.name} inserted_jsonl={result.inserted_jsonl} inserted_sqlite={result.inserted_sqlite} "
        f"total_jsonl={result.total_jsonl} total_sqlite={result.total_sqlite} "
        f"latest_hash_jsonl={result.latest_hash_jsonl} latest_hash_sqlite={result.latest_hash_sqlite} "
        f"jsonl={result.jsonl_path} sqlite={result.sqlite_path}"
    )


def anchor_source_result(source: SourceConfig, result: IngestResult, settings_manager: SettingsManager) -> None:
    """Erzeuge den täglichen OpenTimestamps-Proof für eine Quelle."""

    try:
        proof = OpenTimestampsAnchor(settings_manager.storage_root()).anchor_source(source, result)
    except Exception as exc:
        error = _error_text(exc)
        settings_manager.log_runtime(f'source="{source.name}" action="anchor error" error="{error}"')
        _log_source_error(source, "anchor error", error)
    else:
        settings_manager.log_runtime(f'source="{source.name}" action="anchor finished" proof="{proof}"')

    anchor = OpenTimestampsAnchor(settings_manager.storage_root())
    status = anchor.check_status(source)
    settings_manager.set_anchor_status(source.name, status)
    settings_manager.log_runtime(f'source="{source.name}" action="anchor status" status="{status}"')
    try:
        published_urls = GitHubAnchorPublisher(settings_manager.storage_root()).publish_source(source)
    except Exception as exc:
        error = _error_text(exc)
        settings_manager.log_runtime(f'source="{source.name}" action="github upload error" error="{error}"')
        _log_source_error(source, "github upload error", error)
    else:
        if published_urls:
            settings_manager.log_runtime(f'source="{source.name}" action="github upload finished" files={len(published_urls)}')


def process_sources(config: AppConfig, settings_manager: SettingsManager, enable_ots: bool = False) -> None:
    """Verarbeite alle konfigurierten Quellen genau einmal."""

    for source in config.settings.sources:
        try:
            result = ingest_source(source, settings_manager)
            emit_source_result(source, result)
            if enable_ots:
                anchor_source_result(source, result, settings_manager)
        except Exception as exc:
            _log_source_error(source, "error", _error_text(exc))


def run_daemon(
    config: AppConfig,
    settings_manager: SettingsManager,
    sleep_fn=time.sleep,
    monotonic_fn=time.monotonic,
    stop_event: threading.Event | None = None,
    enable_ots: bool = False,
) -> None:
    """Laufe dauerhaft und frage jede Quelle nach ihrem eigenen poll_interval_seconds erneut ab."""

    if not config.settings.sources:
        raise ValueError("daemon requires at least one source")

    print("daemon=started")

    next_runs = dict.fromkeys(config.settings.sources, 0.0)
    try:
        while stop_event is None or not stop_event.is_set():
            now = monotonic_fn()
            next_deadline: float | None = None

            for source in config.settings.sources:
                if now >= next_runs[source]:
                    try:
                        result = ingest_source(source, settings_manager)
                        emit_source_result(source, result)
                        if enable_ots:
                            anchor_source_result(source, result, settings_manager)
                        if config.settings.heartbeat_url and (result.inserted_jsonl > 0 or result.inserted_sqlite > 0):
                            post(config.settings.heartbeat_url, json={"status": "ok"})
                    except Exception as exc:
                        _log_source_error(source, "error", _error_text(exc))
                    next_runs[source] = now + source.poll_interval_seconds

                deadline = next_runs[source]
                if next_deadline is None or deadline < next_deadline:
                    next_deadline = deadline

            sleep_seconds = max(0.0, (next_deadline or now) - monotonic_fn())

            if stop_event is not None:
                stop_event.wait(sleep_seconds)
            elif sleep_seconds > 0.0:
                sleep_fn(sleep_seconds)
    except KeyboardInterrupt:
        print("daemon=stopped")


def build_parser() -> argparse.ArgumentParser:
    """Baue den CLI-Parser fuer die Anwendung."""

    parser = argparse.ArgumentParser(description="TSBLOCK prototype")
    parser.add_argument("--settings", help="Path to settings.toml")
    parser.add_argument("--daemon", action="store_true", help="Run continuously and poll each source on its own poll_interval_seconds")
    parser.add_argument("--ots", action="store_true", help="Create OpenTimestamps proofs during a one-shot import")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--version", action="version", version=f"newshash {__version__}")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Startpunkt der Kommandozeilenanwendung."""

    parser = build_parser()
    args = parser.parse_args(argv)

    settings_manager = SettingsManager()
    config = settings_manager.resolve_config(args.settings)
    if isinstance(config, AppConfig):
        migrate_legacy_jsonl_and_images(settings_manager.storage_root(), [source.storage_name for source in config.settings.sources])

    if args.daemon:
        stop_event = threading.Event()
        web_thread = threading.Thread(
            target=run_web_server,
            args=(config, settings_manager, args.host, args.port, stop_event),
            name="newshash-web",
            daemon=True,
        )
        web_thread.start()
        run_daemon(config, settings_manager, stop_event=stop_event, enable_ots=True)
        return

    process_sources(config, settings_manager, enable_ots=args.ots)


if __name__ == "__main__":
    main()
