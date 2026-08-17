from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SHARD_SIZE_LIMIT_BYTES = 1_000_000_000
SHARD_INDEX_PATTERN = re.compile(r"\.(\d+)\.")

RECORDS_TABLE = "records"
RECORDS_COLUMNS = (
    "id",
    "source_url",
    "source_id",
    "title",
    "content",
    "author_name",
    "codec_name",
    "published_at",
    "retrieved_at",
    "previous_hash",
    "hash",
    "images_json",
)
RECORDS_CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_url TEXT,
        source_id TEXT UNIQUE,
        title TEXT,
        content TEXT,
        author_name TEXT,
        codec_name TEXT,
        published_at TEXT,
        retrieved_at TEXT,
        previous_hash TEXT,
        hash TEXT UNIQUE,
        images_json TEXT
    )
"""

RECORD_IMAGES_TABLE = "record_images"
RECORD_IMAGES_COLUMNS = ("image_hash", "image_data")
RECORD_IMAGES_CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS record_images (
        image_hash TEXT PRIMARY KEY,
        image_data BLOB NOT NULL
    )
"""


def _shard_index(path: Path) -> int:
    """Extrahiere den numerischen Shard-Index aus einem Dateinamen."""

    match = SHARD_INDEX_PATTERN.search(path.name)
    return int(match.group(1)) if match else 0


class JsonlStorage:
    """Speichert Records als JSON-Lines, aufgeteilt in nummerierte Shards ab 1 GB."""

    def __init__(self, storage_root: Path, storage_name: str) -> None:
        """Initialisiere das JSONL-Storage fuer eine Quelle."""

        self.storage_root = storage_root
        self.storage_name = storage_name

    def _shard_paths(self) -> list[Path]:
        """Gib alle existierenden Shard-Dateien sortiert nach Index zurueck."""

        if not self.storage_root.exists():
            return []
        return sorted(self.storage_root.glob(f"{self.storage_name}.*.jsonl"), key=_shard_index)

    @property
    def path(self) -> Path:
        """Gib den Pfad des aktuell beschreibbaren Shards zurueck."""

        shards = self._shard_paths()
        if not shards:
            return self.storage_root / f"{self.storage_name}.0.jsonl"

        latest = shards[-1]
        if latest.stat().st_size >= SHARD_SIZE_LIMIT_BYTES:
            return self.storage_root / f"{self.storage_name}.{_shard_index(latest) + 1}.jsonl"
        return latest

    def known_source_ids(self) -> set[str]:
        """Sammle die bereits gespeicherten source_id-Werte aus dem letzten Shard."""

        shards = self._shard_paths()
        if not shards:
            return set()

        latest = shards[-1]
        return {json.loads(line)["source_id"] for line in latest.read_text(encoding="utf-8").splitlines() if line.strip()}

    def latest_hash(self, genesis_hash: str) -> str:
        """Gib den Hash des zuletzt gespeicherten Records zurueck, sonst den Genesis-Hash."""

        for shard in reversed(self._shard_paths()):
            lines = [line for line in shard.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                return json.loads(lines[-1])["hash"]
        return genesis_hash

    def latest_shard_index(self) -> int:
        """Gib die Shardnummer des letzten nichtleeren Shards zurueck."""

        for shard in reversed(self._shard_paths()):
            if any(line.strip() for line in shard.read_text(encoding="utf-8").splitlines()):
                return _shard_index(shard)
        return 0

    def count(self) -> int:
        """Zaehle alle gespeicherten Records ueber alle Shards."""

        return sum(1 for shard in self._shard_paths() for line in shard.read_text(encoding="utf-8").splitlines() if line.strip())

    def append_records(self, records: list[dict[str, Any]]) -> None:
        """Haenge Records als JSON-Zeilen an den aktuellen Shard an, mit Rollover bei 1 GB."""

        if not records:
            return

        self.storage_root.mkdir(parents=True, exist_ok=True)
        for record in records:
            target_path = self.path
            with target_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                handle.write("\n")


class SqliteStorage:
    """Speichert Records in SQLite, gespiegelt zu JSONL, inklusive Bild-BLOBs."""

    def __init__(self, storage_root: Path, storage_name: str) -> None:
        """Initialisiere das SQLite-Storage fuer eine Quelle."""

        self.storage_root = storage_root
        self.storage_name = storage_name

    def _shard_paths(self) -> list[Path]:
        """Gib alle existierenden Shard-Dateien sortiert nach Index zurueck."""

        if not self.storage_root.exists():
            return []
        return sorted(self.storage_root.glob(f"{self.storage_name}.*.sqlite3"), key=_shard_index)

    @property
    def path(self) -> Path:
        """Gib den Pfad des aktuell beschreibbaren Shards zurueck."""

        shards = self._shard_paths()
        if not shards:
            return self.storage_root / f"{self.storage_name}.0.sqlite3"

        latest = shards[-1]
        if latest.stat().st_size >= SHARD_SIZE_LIMIT_BYTES:
            return self.storage_root / f"{self.storage_name}.{_shard_index(latest) + 1}.sqlite3"
        return latest

    def _existing_tables(self, connection: sqlite3.Connection) -> set[str]:
        """Gib die Namen aller vorhandenen Tabellen zurueck."""

        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        return {row[0] for row in rows}

    def _table_columns(self, connection: sqlite3.Connection, table_name: str) -> tuple[str, ...]:
        """Gib die aktuellen Spaltennamen einer Tabelle zurueck."""

        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return tuple(row[1] for row in rows)

    def _next_legacy_table_name(self, connection: sqlite3.Connection, table_name: str) -> str:
        """Finde einen freien Namen, unter dem eine abweichende Tabelle gesichert werden kann."""

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        candidate = f"{table_name}_legacy_{timestamp}"
        suffix = 1
        existing_tables = self._existing_tables(connection)
        while candidate in existing_tables:
            suffix += 1
            candidate = f"{table_name}_legacy_{timestamp}_{suffix}"
        return candidate

    def _rename_if_schema_mismatch(self, connection: sqlite3.Connection, table_name: str, expected_columns: tuple[str, ...]) -> None:
        """Benenne eine bestehende Tabelle um, falls ihr Schema von den erwarteten Spalten abweicht."""

        if table_name not in self._existing_tables(connection):
            return

        current_columns = self._table_columns(connection, table_name)
        if current_columns == expected_columns:
            return

        legacy_name = self._next_legacy_table_name(connection, table_name)
        connection.execute(f"ALTER TABLE {table_name} RENAME TO {legacy_name}")
        print(f"storage=sqlite schema_mismatch table={table_name} renamed_to={legacy_name}")

    def _connect(self, path: Path) -> sqlite3.Connection:
        """Oeffne eine Verbindung, pruefe das Schema und stelle sicher, dass es aktuell ist."""

        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)

        self._rename_if_schema_mismatch(connection, RECORDS_TABLE, RECORDS_COLUMNS)
        self._rename_if_schema_mismatch(connection, RECORD_IMAGES_TABLE, RECORD_IMAGES_COLUMNS)

        connection.execute(RECORDS_CREATE_SQL)
        connection.execute(RECORD_IMAGES_CREATE_SQL)
        connection.commit()
        return connection

    def known_source_ids(self) -> set[str]:
        """Sammle die bereits gespeicherten source_id-Werte aus dem letzten Shard."""

        shards = self._shard_paths()
        if not shards:
            return set()

        with self._connect(shards[-1]) as connection:
            rows = connection.execute("SELECT source_id FROM records").fetchall()
        return {row[0] for row in rows}

    def latest_hash(self, genesis_hash: str) -> str:
        """Gib den Hash des zuletzt gespeicherten Records zurueck, sonst den Genesis-Hash."""

        for shard in reversed(self._shard_paths()):
            with self._connect(shard) as connection:
                row = connection.execute("SELECT hash FROM records ORDER BY id DESC LIMIT 1").fetchone()
            if row is not None:
                return row[0]
        return genesis_hash

    def latest_shard_index(self) -> int:
        """Gib die Shardnummer des letzten nichtleeren Shards zurueck."""

        for shard in reversed(self._shard_paths()):
            with self._connect(shard) as connection:
                if connection.execute("SELECT 1 FROM records LIMIT 1").fetchone() is not None:
                    return _shard_index(shard)
        return 0

    def count(self) -> int:
        """Zaehle alle gespeicherten Records ueber alle Shards."""

        total = 0
        for shard in self._shard_paths():
            with self._connect(shard) as connection:
                total += connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        return total

    def append_records(self, records: list[dict[str, Any]], image_bytes_by_hash: dict[str, bytes]) -> None:
        """Schreibe Records und referenzierte Bild-BLOBs in den aktuellen Shard, mit Rollover bei 1 GB."""

        if not records:
            return

        for record in records:
            target_path = self.path
            with self._connect(target_path) as connection:
                connection.execute(
                    """
                    INSERT INTO records (
                        source_url, source_id, title, content, author_name,
                        codec_name, published_at, retrieved_at, previous_hash, hash, images_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["source_url"],
                        record["source_id"],
                        record["title"],
                        record["content"],
                        record["author_name"],
                        record["codec_name"],
                        record["published_at"],
                        record["retrieved_at"],
                        record["previous_hash"],
                        record["hash"],
                        json.dumps(record["images"], ensure_ascii=False, sort_keys=True),
                    ),
                )
                for image_hash in record["images"]:
                    image_bytes = image_bytes_by_hash.get(image_hash)
                    if image_bytes is None:
                        continue
                    connection.execute(
                        "INSERT OR IGNORE INTO record_images (image_hash, image_data) VALUES (?, ?)",
                        (image_hash, image_bytes),
                    )
                connection.commit()

    def read_records(self) -> list[dict[str, Any]]:
        """Lies alle Records ueber alle Shards, mit deserialisiertem images-Dict."""

        records: list[dict[str, Any]] = []
        for shard in self._shard_paths():
            with self._connect(shard) as connection:
                rows = connection.execute(
                    """
                    SELECT source_url, source_id, title, content, author_name,
                           codec_name, published_at, retrieved_at, previous_hash, hash, images_json
                    FROM records ORDER BY id
                    """
                ).fetchall()
            for row in rows:
                records.append(
                    {
                        "source_url": row[0],
                        "source_id": row[1],
                        "title": row[2],
                        "content": row[3],
                        "author_name": row[4],
                        "codec_name": row[5],
                        "published_at": row[6],
                        "retrieved_at": row[7],
                        "previous_hash": row[8],
                        "hash": row[9],
                        "images": json.loads(row[10]),
                    }
                )
        return records

    def dashboard_stats(self) -> dict[str, Any]:
        """Lese aggregierte Kennzahlen ohne alle Datensätze zu laden."""

        total_records = 0
        total_images = 0
        latest_retrieved_at = ""
        latest_hash = ""
        for shard in self._shard_paths():
            with self._connect(shard) as connection:
                count, images, retrieved_at = connection.execute(
                    """
                    SELECT COUNT(*),
                           COALESCE(SUM((SELECT COUNT(*) FROM json_each(records.images_json))), 0),
                           COALESCE(MAX(retrieved_at), '')
                    FROM records
                    """
                ).fetchone()
                latest = connection.execute("SELECT hash FROM records ORDER BY id DESC LIMIT 1").fetchone()
            total_records += count
            total_images += images
            if retrieved_at > latest_retrieved_at:
                latest_retrieved_at = retrieved_at
            if latest is not None:
                latest_hash = latest[0]

        return {
            "records": total_records,
            "images": total_images,
            "latest_retrieved_at": latest_retrieved_at,
            "latest_hash": latest_hash,
        }

    def latest_records(self, limit: int = 5) -> list[dict[str, Any]]:
        """Lese die neuesten Records aus dem letzten Shard für die Dashboard-Vorschau."""

        shards = self._shard_paths()
        if not shards:
            return []

        with self._connect(shards[-1]) as connection:
            rows = connection.execute(
                """
                SELECT source_url, source_id, title, content, author_name,
                       codec_name, published_at, retrieved_at, previous_hash, hash, images_json
                FROM records ORDER BY published_at DESC, id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "source_url": row[0],
                "source_id": row[1],
                "title": row[2],
                "content": row[3],
                "author_name": row[4],
                "codec_name": row[5],
                "published_at": row[6],
                "retrieved_at": row[7],
                "previous_hash": row[8],
                "hash": row[9],
                "images": json.loads(row[10]),
            }
            for row in rows
        ]

    def get_record(self, source_id: str) -> dict[str, Any] | None:
        """Lese einen einzelnen Record anhand seiner stabilen source_id."""

        for shard in self._shard_paths():
            with self._connect(shard) as connection:
                row = connection.execute(
                    """
                    SELECT source_url, source_id, title, content, author_name,
                           codec_name, published_at, retrieved_at, previous_hash, hash, images_json
                    FROM records WHERE source_id = ? LIMIT 1
                    """,
                    (source_id,),
                ).fetchone()
            if row is not None:
                return {
                    "source_url": row[0],
                    "source_id": row[1],
                    "title": row[2],
                    "content": row[3],
                    "author_name": row[4],
                    "codec_name": row[5],
                    "published_at": row[6],
                    "retrieved_at": row[7],
                    "previous_hash": row[8],
                    "hash": row[9],
                    "images": json.loads(row[10]),
                }
        return None

    def adjacent_records(self, source_id: str) -> tuple[dict[str, str] | None, dict[str, str] | None]:
        """Lese Vorgänger und Nachfolger eines Records aus dem neuesten Shard."""

        shards = self._shard_paths()
        if not shards:
            return None, None
        with self._connect(shards[-1]) as connection:
            current = connection.execute("SELECT id FROM records WHERE source_id = ? LIMIT 1", (source_id,)).fetchone()
            if current is None:
                return None, None
            previous = connection.execute(
                "SELECT source_id, title FROM records WHERE id < ? ORDER BY id DESC LIMIT 1", (current[0],)
            ).fetchone()
            next_record = connection.execute(
                "SELECT source_id, title FROM records WHERE id > ? ORDER BY id LIMIT 1", (current[0],)
            ).fetchone()

        def navigation(row: tuple[str, str] | None) -> dict[str, str] | None:
            return {"source_id": row[0], "title": row[1]} if row is not None else None

        return navigation(previous), navigation(next_record)
