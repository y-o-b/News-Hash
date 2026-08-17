from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from newshash.codec import GENESIS_HASH, get_codec
from newshash.settings import DEFAULT_DATA_DIR, SettingsManager, SourceConfig
from newshash.storage import JsonlStorage, SqliteStorage, _shard_index


@dataclass(frozen=True)
class ValidationResult:
    """Ergebnis der Kettenpruefung eines Speicherformats."""

    storage_name: str
    storage_format: str
    shards_checked: tuple[int, ...]
    records_checked: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Gib an, ob alle geprueften Records gueltig waren."""

        return not self.errors


def _nonempty_jsonl_paths(storage: JsonlStorage) -> list[Path]:
    return [path for path in storage._shard_paths() if any(line.strip() for line in path.read_text(encoding="utf-8").splitlines())]


def _nonempty_sqlite_paths(storage: SqliteStorage) -> list[Path]:
    paths: list[Path] = []
    for path in storage._shard_paths():
        with sqlite3.connect(path) as connection:
            try:
                has_record = connection.execute("SELECT 1 FROM records LIMIT 1").fetchone() is not None
            except sqlite3.DatabaseError:
                has_record = True
        if has_record:
            paths.append(path)
    return paths


def _jsonl_records(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            yield line_number, value


def _sqlite_records(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with sqlite3.connect(path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(records)").fetchall()]
        if not columns:
            raise sqlite3.DatabaseError("records table is missing")
        selected_columns = [
            "source_url",
            "source_id",
            "title",
            "content",
            "author_name",
            "codec_name",
            "published_at",
            "retrieved_at",
            "schema_version",
            "schema_hash",
            "codec_version",
            "codec_hash",
            "hash_function_version",
            "hash_function_hash",
            "previous_hash",
            "hash",
            "images_json",
        ]
        available_columns = [column for column in selected_columns if column in columns]
        rows = connection.execute(f"SELECT {', '.join(available_columns)} FROM records ORDER BY id").fetchall()
    for row_number, row in enumerate(rows, start=1):
        values = dict(zip(available_columns, row, strict=True))
        yield (
            row_number,
            {
                "source_url": values.get("source_url"),
                "source_id": values.get("source_id"),
                "title": values.get("title"),
                "content": values.get("content"),
                "author_name": values.get("author_name"),
                "codec_name": values.get("codec_name"),
                "published_at": values.get("published_at"),
                "retrieved_at": values.get("retrieved_at"),
                "schema_version": values.get("schema_version"),
                "schema_hash": values.get("schema_hash"),
                "codec_version": values.get("codec_version"),
                "codec_hash": values.get("codec_hash"),
                "hash_function_version": values.get("hash_function_version"),
                "hash_function_hash": values.get("hash_function_hash"),
                "previous_hash": values.get("previous_hash"),
                "hash": values.get("hash"),
                "images": json.loads(values.get("images_json") or "{}"),
            },
        )


def _records(path: Path, storage_format: str) -> Iterable[tuple[int, dict[str, Any]]]:
    return _jsonl_records(path) if storage_format == "jsonl" else _sqlite_records(path)


def _last_hash(path: Path, storage_format: str) -> str | None:
    last: str | None = None
    for _, record in _records(path, storage_format):
        last = str(record.get("hash"))
    return last


def _validate_paths(
    paths: list[Path],
    storage_name: str,
    storage_format: str,
    codec_name: str,
    all_shards: bool,
) -> ValidationResult:
    errors: list[str] = []
    if not paths:
        return ValidationResult(storage_name, storage_format, (), 0, ())

    selected_paths = paths if all_shards else paths[-1:]
    first_selected = paths.index(selected_paths[0])
    expected_hash = GENESIS_HASH
    if first_selected:
        expected_hash = _last_hash(paths[first_selected - 1], storage_format) or GENESIS_HASH

    records_checked = 0
    for path in selected_paths:
        shard_number = _shard_index(path)
        try:
            records = _records(path, storage_format)
            for row_number, record in records:
                records_checked += 1
                actual_previous = str(record.get("previous_hash"))
                if actual_previous != expected_hash:
                    errors.append(f"{storage_format} shard={shard_number} record={row_number}: previous_hash={actual_previous!r}, expected={expected_hash!r}")
                record_codec = get_codec(str(record.get("codec_name") or codec_name))
                calculated_hash = record_codec.digest_record(record_codec.record_hash_material(record, expected_hash))
                actual_hash = str(record.get("hash"))
                if actual_hash != calculated_hash:
                    errors.append(f"{storage_format} shard={shard_number} record={row_number}: hash={actual_hash!r}, calculated={calculated_hash!r}")
                expected_hash = actual_hash
        except (OSError, json.JSONDecodeError, sqlite3.DatabaseError, TypeError, ValueError) as error:
            errors.append(f"{storage_format} shard={shard_number}: {type(error).__name__}: {error}")

    return ValidationResult(
        storage_name,
        storage_format,
        tuple(_shard_index(path) for path in selected_paths),
        records_checked,
        tuple(errors),
    )


def validate_source(storage_root: Path, source: SourceConfig, all_shards: bool = False) -> tuple[ValidationResult, ValidationResult]:
    """Pruefe JSONL- und SQLite-Kette einer Quelle, standardmaessig nur den letzten Shard."""

    jsonl = JsonlStorage(storage_root, source.storage_name)
    sqlite = SqliteStorage(storage_root, source.storage_name)
    return (
        _validate_paths(_nonempty_jsonl_paths(jsonl), source.storage_name, "jsonl", source.codec_name, all_shards),
        _validate_paths(_nonempty_sqlite_paths(sqlite), source.storage_name, "sqlite", source.codec_name, all_shards),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate News-Hash hash chains")
    parser.add_argument("--settings", help="Path to settings.toml")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Storage directory (default: data)")
    parser.add_argument("--source", help="Validate only this storage_name")
    parser.add_argument("--all-shards", action="store_true", help="Validate every shard instead of only the latest non-empty shard")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Validiere konfigurierte Hash-Ketten und beende bei Fehlern mit Status 1."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    manager = SettingsManager(data_dir=args.data_dir, default_settings_path=args.data_dir / "settings.toml")
    config = manager.resolve_config(args.settings)
    sources = [source for source in config.settings.sources if args.source is None or source.storage_name == args.source]
    if not sources:
        parser.error(f"unknown source storage_name: {args.source}")

    invalid = False
    for source in sources:
        for result in validate_source(args.data_dir, source, args.all_shards):
            status = "ok" if result.valid else "invalid"
            print(
                f"source={source.storage_name} format={result.storage_format} status={status} "
                f"shards={','.join(map(str, result.shards_checked)) or '-'} records={result.records_checked}"
            )
            for error in result.errors:
                print(f"error={error}", file=sys.stderr)
                invalid = True
    if invalid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
