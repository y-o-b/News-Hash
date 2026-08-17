from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

METADATA_DEFINITIONS: dict[str, dict[str, Any]] = {
    "schema-v0.json": {
        "version": 0,
        "record_fields": [
            "codec_name",
            "source_id",
            "source_url",
            "title",
            "content",
            "author_name",
            "published_at",
            "retrieved_at",
            "images",
            "previous_hash",
            "hash",
        ],
    },
    "schema-v1.json": {
        "version": 1,
        "record_fields": [
            "codec_name",
            "source_id",
            "source_url",
            "title",
            "content",
            "author_name",
            "published_at",
            "retrieved_at",
            "images",
            "schema_version",
            "schema_hash",
            "codec_version",
            "codec_hash",
            "hash_function_version",
            "hash_function_hash",
            "previous_hash",
            "hash",
        ],
    },
    "codecs-v0.json": {
        "version": 0,
        "codecs": {
            "RSSv0": "RSS and JSON/XML feed normalization",
            "TAZv0": "RSS normalization with full TAZ article retrieval",
            "SCREENv0": "RSS normalization with Chromium page screenshots",
        },
    },
    "codecs-v1.json": {
        "version": 1,
        "codecs": {
            "RSSv1": "v1 normalization with versioned metadata hashes",
            "TAZv1": "v1 TAZ normalization with versioned metadata hashes",
            "SCREENv1": "v1 screenshot normalization with versioned metadata hashes",
        },
    },
    "hash-functions-v0.json": {
        "version": 0,
        "algorithm": "SHA-256",
        "canonical_json": {"ensure_ascii": False, "sort_keys": True, "separators": [",", ":"]},
        "chain": {"genesis": "64 zeroes", "previous_field": "previous_hash"},
    },
    "hash-functions-v1.json": {
        "version": 1,
        "algorithm": "SHA-256",
        "canonical_json": {"ensure_ascii": False, "sort_keys": True, "separators": [",", ":"]},
        "chain": {"genesis": "64 zeroes", "previous_field": "previous_hash"},
        "metadata_fields_in_hash": ["schema_hash", "codec_hash", "hash_function_hash"],
    },
}


def _metadata_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def ensure_metadata_files(storage_root: Path) -> None:
    """Lege unveraenderliche v0- und v1-Metadaten im Data-Verzeichnis ab."""

    storage_root.mkdir(parents=True, exist_ok=True)
    for name, definition in METADATA_DEFINITIONS.items():
        path = storage_root / name
        expected = _metadata_bytes(definition)
        if path.exists():
            if path.read_bytes() != expected:
                raise ValueError(f"metadata file changed without a new version: {path.name}")
            continue
        path.write_bytes(expected)


def metadata_hashes(storage_root: Path) -> dict[str, str]:
    """Gib die SHA-256-Hashes der aktiven v1-Metadaten zurueck."""

    ensure_metadata_files(storage_root)
    return {
        "schema_version": "1",
        "schema_hash": hashlib.sha256((storage_root / "schema-v1.json").read_bytes()).hexdigest(),
        "codec_version": "1",
        "codec_hash": hashlib.sha256((storage_root / "codecs-v1.json").read_bytes()).hexdigest(),
        "hash_function_version": "1",
        "hash_function_hash": hashlib.sha256((storage_root / "hash-functions-v1.json").read_bytes()).hexdigest(),
    }
