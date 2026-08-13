from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

import newshash.main as main
from newshash.codec import CODEC_REGISTRY, GENESIS_HASH
from newshash.main import IngestResult
from newshash.settings import AppConfig, Settings, SettingsManager, SourceConfig
from newshash.storage import JsonlStorage, SqliteStorage


def fake_feed() -> dict:
    return {
        "items": [
            {
                "id": "example-1",
                "title": "Beispielnachricht",
                "url": "https://example.invalid/article-1",
                "content_html": "<p>Text</p>",
                "date_modified": "2026-07-29T10:00:00Z",
                "author": {"name": "Redaktion"},
                "_rssbridge": {
                    "link": "https://example.invalid/article-1",
                    "dc": {"date": "2026-07-29T10:00:00Z"},
                    "guid": "guid-1",
                },
            }
        ]
    }


def fake_feed_two_items() -> dict:
    feed = fake_feed()
    second = dict(feed["items"][0])
    second["id"] = "example-2"
    second["title"] = "Beispielnachricht 2"
    feed["items"].append(second)
    return feed


def test_ingest_source_writes_jsonl_and_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "fetch_feed", lambda url: fake_feed())
    settings_manager = SettingsManager(data_dir=tmp_path)
    source = SourceConfig(name="example", feed_url="https://example.invalid/feed", storage_name="example", poll_interval_seconds=300)

    result = main.ingest_source(source, settings_manager)

    assert result.inserted_jsonl == 1
    assert result.inserted_sqlite == 1
    assert result.total_jsonl == 1
    assert result.total_sqlite == 1
    assert len(result.latest_hash_jsonl) == 64
    assert len(result.latest_hash_sqlite) == 64
    assert result.jsonl_path == tmp_path / "example.0.jsonl"
    assert result.sqlite_path == tmp_path / "example.0.sqlite3"

    line = result.jsonl_path.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["source_id"] == "example-1"
    assert record["previous_hash"] == GENESIS_HASH

    with sqlite3.connect(result.sqlite_path) as connection:
        row = connection.execute("SELECT source_id FROM records").fetchone()
    assert row[0] == "example-1"


def test_ingest_source_skips_already_known_records(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "fetch_feed", lambda url: fake_feed())
    prepare_calls = 0
    original_prepare_item = CODEC_REGISTRY["RSSv0"].prepare_item

    def track_prepare_item(*args, **kwargs):
        nonlocal prepare_calls
        prepare_calls += 1
        return original_prepare_item(*args, **kwargs)

    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "prepare_item", track_prepare_item)
    settings_manager = SettingsManager(data_dir=tmp_path)
    source = SourceConfig(name="example", feed_url="https://example.invalid/feed", storage_name="example", poll_interval_seconds=300)

    main.ingest_source(source, settings_manager)
    second_result = main.ingest_source(source, settings_manager)

    assert prepare_calls == 1
    assert second_result.inserted_jsonl == 0
    assert second_result.inserted_sqlite == 0
    assert second_result.total_jsonl == 1
    assert second_result.total_sqlite == 1


def test_ingest_source_produces_identical_hash_chain_in_both_stores(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "fetch_feed", lambda url: fake_feed_two_items())
    settings_manager = SettingsManager(data_dir=tmp_path)
    source = SourceConfig(name="example", feed_url="https://example.invalid/feed", storage_name="example", poll_interval_seconds=300)

    result = main.ingest_source(source, settings_manager)

    assert result.inserted_jsonl == 2
    assert result.inserted_sqlite == 2
    jsonl_storage = JsonlStorage(tmp_path, "example")
    sqlite_storage = SqliteStorage(tmp_path, "example")

    jsonl_records = [json.loads(line) for line in result.jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sqlite_records = sqlite_storage.read_records()

    assert [r["hash"] for r in jsonl_records] == [r["hash"] for r in sqlite_records]
    assert jsonl_storage.latest_hash(GENESIS_HASH) == jsonl_records[-1]["hash"]


def test_ingest_source_tracks_previous_hash_independently_per_store(tmp_path, monkeypatch) -> None:
    settings_manager = SettingsManager(data_dir=tmp_path)
    source = SourceConfig(name="example", feed_url="https://example.invalid/feed", storage_name="example", poll_interval_seconds=300)

    codec = CODEC_REGISTRY["RSSv0"]
    seed_item = {
        "id": "seed-1",
        "title": "Seed",
        "url": "https://example.invalid/seed-1",
        "content_html": "<p>Seed</p>",
        "date_modified": "2026-07-28T10:00:00Z",
        "author": {"name": "Redaktion"},
        "_rssbridge": {"link": "https://example.invalid/seed-1", "dc": {"date": "2026-07-28T10:00:00Z"}, "guid": "seed"},
    }
    seed_record, _ = codec.build_record(seed_item, "2026-07-28T10:05:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")

    # Nur JSONL kennt "seed-1" bereits (z.B. weil SQLite nach einem Absturz zurueckliegt).
    JsonlStorage(tmp_path, "example").append_records([seed_record])

    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "fetch_feed", lambda url: fake_feed())

    result = main.ingest_source(source, settings_manager)

    assert result.inserted_jsonl == 1
    assert result.inserted_sqlite == 1

    jsonl_records = [json.loads(line) for line in result.jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sqlite_records = SqliteStorage(tmp_path, "example").read_records()

    jsonl_example_1 = jsonl_records[-1]
    sqlite_example_1 = sqlite_records[-1]

    assert jsonl_example_1["source_id"] == "example-1"
    assert sqlite_example_1["source_id"] == "example-1"
    assert jsonl_example_1["previous_hash"] == seed_record["hash"]
    assert sqlite_example_1["previous_hash"] == GENESIS_HASH
    assert jsonl_example_1["previous_hash"] != sqlite_example_1["previous_hash"]
    assert jsonl_example_1["hash"] != sqlite_example_1["hash"]


def test_process_sources_handles_all_configured_sources(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(CODEC_REGISTRY["RSSv0"], "fetch_feed", lambda url: fake_feed())
    settings_manager = SettingsManager(data_dir=tmp_path)
    config = AppConfig(
        settings_path=tmp_path / "settings.toml",
        settings=Settings(
            sources=(
                SourceConfig(name="alpha", feed_url="https://example.invalid/a", storage_name="alpha", poll_interval_seconds=300),
                SourceConfig(name="beta", feed_url="https://example.invalid/b", storage_name="beta", poll_interval_seconds=120),
            )
        ),
    )

    main.process_sources(config, settings_manager)

    output = capsys.readouterr().out
    assert "source=alpha" in output
    assert "source=beta" in output


def test_run_daemon_processes_sources_on_their_own_interval(tmp_path, monkeypatch) -> None:
    calls: list[str] = []
    current_time = {"value": 0.0}

    def fake_ingest_source(source, settings_manager):
        calls.append(source.name)
        return IngestResult(
            inserted_jsonl=1,
            inserted_sqlite=1,
            total_jsonl=len(calls),
            total_sqlite=len(calls),
            latest_hash_jsonl=f"hash-jsonl-{source.name}",
            latest_hash_sqlite=f"hash-sqlite-{source.name}",
            jsonl_path=Path(f"/tmp/{source.name}.jsonl"),
            sqlite_path=Path(f"/tmp/{source.name}.sqlite3"),
        )

    def fake_sleep(interval_seconds: float) -> None:
        current_time["value"] += interval_seconds
        if len(calls) >= 5:
            raise KeyboardInterrupt

    def fake_monotonic() -> float:
        return current_time["value"]

    monkeypatch.setattr(main, "ingest_source", fake_ingest_source)

    config = AppConfig(
        settings_path=tmp_path / "settings.toml",
        settings=Settings(
            sources=(
                SourceConfig(name="alpha", feed_url="https://example.invalid/a", storage_name="alpha", poll_interval_seconds=5),
                SourceConfig(name="beta", feed_url="https://example.invalid/b", storage_name="beta", poll_interval_seconds=10),
            )
        ),
    )

    main.run_daemon(config, SettingsManager(data_dir=tmp_path), sleep_fn=fake_sleep, monotonic_fn=fake_monotonic)

    assert calls == ["alpha", "beta", "alpha", "alpha", "beta"]


def test_run_daemon_rejects_empty_sources(tmp_path) -> None:
    config = AppConfig(settings_path=tmp_path / "settings.toml", settings=Settings(sources=()))

    with pytest.raises(ValueError, match="daemon requires"):
        main.run_daemon(config, SettingsManager(data_dir=tmp_path))


def test_build_parser_defaults() -> None:
    parser = main.build_parser()
    args = parser.parse_args([])

    assert args.settings is None
    assert args.daemon is False
    assert args.ots is False
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert not hasattr(args, "web")
    assert not hasattr(args, "interval")


def test_main_runs_web_server_alongside_daemon(monkeypatch) -> None:
    calls: list[str] = []
    web_started = threading.Event()

    monkeypatch.setattr(main.SettingsManager, "resolve_config", lambda self, settings_path: "config")
    monkeypatch.setattr(main, "run_web_server", lambda *args: (calls.append("web"), web_started.set()))
    monkeypatch.setattr(main, "run_daemon", lambda *args, **kwargs: calls.append("daemon"))

    main.main(["--daemon", "--port", "5000"])

    assert web_started.wait(timeout=1)
    assert calls == ["web", "daemon"] or calls == ["daemon", "web"]
