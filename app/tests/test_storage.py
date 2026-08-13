from __future__ import annotations

import sqlite3

from newshash.codec import GENESIS_HASH
from newshash.storage import RECORD_IMAGES_COLUMNS, RECORDS_COLUMNS, SHARD_SIZE_LIMIT_BYTES, JsonlStorage, SqliteStorage


def make_record(source_id: str, previous_hash: str, image_hash: str | None = None) -> dict:
    images = {}
    if image_hash:
        images = {image_hash: {"url": f"https://example.invalid/{source_id}.png", "path": f"images/{source_id}.png"}}
    return {
        "codec_name": "RSSv0",
        "source_id": source_id,
        "source_url": f"https://example.invalid/{source_id}",
        "title": f"Titel {source_id}",
        "content": "<p>Text</p>",
        "author_name": "Redaktion",
        "published_at": "2026-07-29T10:00:00Z",
        "retrieved_at": "2026-07-29T10:05:00Z",
        "previous_hash": previous_hash,
        "images": images,
        "hash": f"hash-{source_id}".ljust(64, "0"),
    }


def test_jsonl_storage_appends_and_reads_back(tmp_path) -> None:
    storage = JsonlStorage(tmp_path, "example")
    record = make_record("example-1", GENESIS_HASH)

    storage.append_records([record])

    assert storage.path == tmp_path / "example.0.jsonl"
    assert storage.count() == 1
    assert storage.known_source_ids() == {"example-1"}
    assert storage.latest_hash(GENESIS_HASH) == record["hash"]


def test_jsonl_storage_default_state_without_existing_shard(tmp_path) -> None:
    storage = JsonlStorage(tmp_path, "example")

    assert storage.count() == 0
    assert storage.known_source_ids() == set()
    assert storage.latest_hash(GENESIS_HASH) == GENESIS_HASH


def test_jsonl_storage_rolls_over_shard_when_size_limit_reached(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("newshash.storage.SHARD_SIZE_LIMIT_BYTES", 10)
    storage = JsonlStorage(tmp_path, "example")

    storage.append_records([make_record("example-1", GENESIS_HASH)])
    storage.append_records([make_record("example-2", "hash-example-1".ljust(64, "0"))])

    assert (tmp_path / "example.0.jsonl").exists()
    assert (tmp_path / "example.1.jsonl").exists()
    assert storage.count() == 2


def test_jsonl_storage_known_source_ids_only_considers_last_shard(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("newshash.storage.SHARD_SIZE_LIMIT_BYTES", 10)
    storage = JsonlStorage(tmp_path, "example")

    storage.append_records([make_record("example-1", GENESIS_HASH)])
    storage.append_records([make_record("example-2", "hash-example-1".ljust(64, "0"))])

    assert (tmp_path / "example.0.jsonl").exists()
    assert (tmp_path / "example.1.jsonl").exists()
    assert storage.known_source_ids() == {"example-2"}


def test_sqlite_storage_appends_records_and_image_blobs(tmp_path) -> None:
    storage = SqliteStorage(tmp_path, "example")
    image_hash = "a" * 64
    record = make_record("example-1", GENESIS_HASH, image_hash=image_hash)

    storage.append_records([record], {image_hash: b"image-bytes"})

    assert storage.count() == 1
    assert storage.known_source_ids() == {"example-1"}

    records = storage.read_records()
    assert records[0]["source_id"] == "example-1"
    assert records[0]["images"] == record["images"]

    import sqlite3

    with sqlite3.connect(storage.path) as connection:
        row = connection.execute("SELECT image_data FROM record_images WHERE image_hash = ?", (image_hash,)).fetchone()
    assert row[0] == b"image-bytes"


def test_sqlite_storage_dashboard_stats_and_latest_records(tmp_path) -> None:
    storage = SqliteStorage(tmp_path, "example")
    image_hash = "a" * 64
    first = make_record("example-1", GENESIS_HASH, image_hash=image_hash)
    second = make_record("example-2", first["hash"])
    first["published_at"] = "2026-08-01T12:00:00Z"
    second["published_at"] = "2026-08-02T12:00:00Z"
    second["retrieved_at"] = "2026-08-10T12:00:00Z"

    storage.append_records([first, second], {image_hash: b"image-bytes"})

    assert storage.dashboard_stats() == {
        "records": 2,
        "images": 1,
        "latest_retrieved_at": "2026-08-10T12:00:00Z",
        "latest_hash": second["hash"],
    }
    assert [record["source_id"] for record in storage.latest_records(1)] == ["example-2"]


def test_sqlite_storage_deduplicates_identical_image_blob(tmp_path) -> None:
    storage = SqliteStorage(tmp_path, "example")
    image_hash = "b" * 64
    record_a = make_record("example-1", GENESIS_HASH, image_hash=image_hash)
    record_b = make_record("example-2", record_a["hash"], image_hash=image_hash)

    storage.append_records([record_a], {image_hash: b"same-bytes"})
    storage.append_records([record_b], {image_hash: b"same-bytes"})

    import sqlite3

    with sqlite3.connect(storage.path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM record_images").fetchone()[0]
    assert count == 1


def test_sqlite_storage_known_source_ids_only_considers_last_shard(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("newshash.storage.SHARD_SIZE_LIMIT_BYTES", 10)
    storage = SqliteStorage(tmp_path, "example")

    storage.append_records([make_record("example-1", GENESIS_HASH)], {})
    storage.append_records([make_record("example-2", "hash-example-1".ljust(64, "0"))], {})

    assert (tmp_path / "example.0.sqlite3").exists()
    assert (tmp_path / "example.1.sqlite3").exists()
    assert storage.known_source_ids() == {"example-2"}


def test_sqlite_storage_renames_records_table_on_schema_mismatch(tmp_path) -> None:
    shard_path = tmp_path / "example.0.sqlite3"
    with sqlite3.connect(shard_path) as connection:
        connection.execute(
            """
            CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT UNIQUE,
                payload_json TEXT
            )
            """
        )
        connection.execute("INSERT INTO records (source_id, payload_json) VALUES (?, ?)", ("legacy-1", "{}"))
        connection.commit()

    storage = SqliteStorage(tmp_path, "example")

    assert storage.count() == 0
    assert storage.known_source_ids() == set()

    with sqlite3.connect(shard_path) as connection:
        table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}

    legacy_tables = [name for name in table_names if name.startswith("records_legacy_")]
    assert len(legacy_tables) == 1
    assert "records" in table_names

    with sqlite3.connect(shard_path) as connection:
        legacy_columns = tuple(row[1] for row in connection.execute(f"PRAGMA table_info({legacy_tables[0]})").fetchall())
        current_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(records)").fetchall())
        legacy_row = connection.execute(f"SELECT source_id, payload_json FROM {legacy_tables[0]}").fetchone()

    assert legacy_columns == ("id", "source_id", "payload_json")
    assert current_columns == RECORDS_COLUMNS
    assert legacy_row == ("legacy-1", "{}")


def test_sqlite_storage_renames_record_images_table_on_schema_mismatch(tmp_path) -> None:
    shard_path = tmp_path / "example.0.sqlite3"
    with sqlite3.connect(shard_path) as connection:
        connection.execute(
            """
            CREATE TABLE record_images (
                image_hash TEXT PRIMARY KEY,
                image_path TEXT
            )
            """
        )
        connection.commit()

    storage = SqliteStorage(tmp_path, "example")
    storage.count()

    with sqlite3.connect(shard_path) as connection:
        table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        current_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(record_images)").fetchall())

    legacy_tables = [name for name in table_names if name.startswith("record_images_legacy_")]
    assert len(legacy_tables) == 1
    assert current_columns == RECORD_IMAGES_COLUMNS


def test_sqlite_storage_keeps_table_when_schema_matches(tmp_path) -> None:
    storage = SqliteStorage(tmp_path, "example")
    storage.append_records([make_record("example-1", GENESIS_HASH)], {})

    # Zweiter Zugriff mit identischem, bereits korrektem Schema darf nichts umbenennen.
    storage.count()

    with sqlite3.connect(tmp_path / "example.0.sqlite3") as connection:
        table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}

    assert {"records", "record_images"} <= table_names
    assert not any(name.startswith(("records_legacy_", "record_images_legacy_")) for name in table_names)


def test_default_shard_size_limit_is_one_gigabyte() -> None:
    assert SHARD_SIZE_LIMIT_BYTES == 1_000_000_000
