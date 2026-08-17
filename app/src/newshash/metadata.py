from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_V2: dict[str, Any] = {
    "version": 2,
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
}
HASH_FUNCTION_V2: dict[str, Any] = {
    "version": 2,
    "algorithm": "SHA-256",
    "canonical_json": {"ensure_ascii": False, "sort_keys": True, "separators": [",", ":"]},
    "chain": {"genesis": "64 zeroes", "previous_field": "previous_hash"},
    "metadata_fields_in_hash": ["schema_hash", "codec_hash", "hash_function_hash"],
}
CODEC_V2: dict[str, dict[str, Any]] = {
    "RSSv2": {"version": 2, "description": "RSS and JSON/XML feed normalization"},
    "TAZv2": {"version": 2, "description": "RSS normalization with full TAZ article retrieval"},
    "SCREENv2": {"version": 2, "description": "RSS normalization with Chromium page screenshots"},
}
LEGACY_DEFINITIONS = {
    "schema-v1.json": {"version": 1, "record_fields": SCHEMA_V2["record_fields"]},
    "codecs-v1.json": {
        "version": 1,
        "codecs": {
            "RSSv1": "v1 normalization with versioned metadata hashes",
            "TAZv1": "v1 TAZ normalization with versioned metadata hashes",
            "SCREENv1": "v1 screenshot normalization with versioned metadata hashes",
        },
    },
    "hash-functions-v1.json": {
        "version": 1,
        "algorithm": "SHA-256",
        "canonical_json": {"ensure_ascii": False, "sort_keys": True, "separators": [",", ":"]},
        "chain": {"genesis": "64 zeroes", "previous_field": "previous_hash"},
        "metadata_fields_in_hash": ["schema_hash", "codec_hash", "hash_function_hash"],
    },
}


def canonical_json(value: dict[str, Any]) -> bytes:
    """Serialisiere Metadaten deterministisch fuer ihren Identitaetshash."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _codec_definition(codec_name: str) -> dict[str, Any]:
    try:
        codec = CODEC_V2[codec_name]
    except KeyError as error:
        raise ValueError(f"no v2 metadata definition for codec: {codec_name}") from error
    return {"codec": {"name": codec_name, **codec}, "schema": SCHEMA_V2, "hash_function": HASH_FUNCTION_V2}


def metadata_hashes(storage_root: Path, codec_name: str) -> dict[str, str]:
    """Lege den normalisierten Codecvertrag ab und gib alle drei Teilhashes zurueck."""

    if not codec_name.endswith("v2"):
        return _legacy_metadata_hashes(storage_root)

    codec_dir = storage_root / "Codec"
    codec_dir.mkdir(parents=True, exist_ok=True)
    definition = _codec_definition(codec_name)
    path = codec_dir / f"{codec_name}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if canonical_json(existing) != canonical_json(definition):
            raise ValueError(f"codec metadata changed without a new codec version: {path.name}")
    else:
        path.write_text(json.dumps(definition, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return {
        "schema_version": "2",
        "schema_hash": hashlib.sha256(canonical_json(SCHEMA_V2)).hexdigest(),
        "codec_version": "2",
        "codec_hash": hashlib.sha256(canonical_json(definition)).hexdigest(),
        "hash_function_version": "2",
        "hash_function_hash": hashlib.sha256(canonical_json(HASH_FUNCTION_V2)).hexdigest(),
    }


def _legacy_metadata_hashes(storage_root: Path) -> dict[str, str]:
    """Bewahre den bisherigen v1-Metadatenvertrag fuer alte Records."""

    storage_root.mkdir(parents=True, exist_ok=True)
    for name, definition in LEGACY_DEFINITIONS.items():
        path = storage_root / name
        if not path.exists():
            path.write_text(json.dumps(definition, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    schema = storage_root / "schema-v1.json"
    codecs = storage_root / "codecs-v1.json"
    functions = storage_root / "hash-functions-v1.json"
    return {
        "schema_version": "1",
        "schema_hash": hashlib.sha256(schema.read_bytes()).hexdigest(),
        "codec_version": "1",
        "codec_hash": hashlib.sha256(codecs.read_bytes()).hexdigest(),
        "hash_function_version": "1",
        "hash_function_hash": hashlib.sha256(functions.read_bytes()).hexdigest(),
    }
