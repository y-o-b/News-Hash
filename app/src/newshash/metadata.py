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
LEGACY_METADATA_HASHES = {
    "schema_hash": "a457229b9a9b826381a6e9c43be1652bf4680ee0c7fbbe87b8b40e8bee699466",
    "codec_hash": "3f6334a10d750a07b45b384ca53efaf63402fb752762c09fabce4633b8a454eb",
    "hash_function_hash": "3821ac446a3b05bb1050ee4a3dcd2611aaede05a0238f32a9e1bb0b472b08c07",
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


def codec_definition(codec_name: str) -> dict[str, Any] | None:
    """Gib die persistierbare Definition eines versionierten Codecs zurück."""

    if not codec_name.endswith("v2"):
        return None
    return _codec_definition(codec_name)


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
    """Bewahre den bisherigen v1-Metadatenvertrag ohne alte JSON-Dateien."""

    return {
        "schema_version": "1",
        "schema_hash": LEGACY_METADATA_HASHES["schema_hash"],
        "codec_version": "1",
        "codec_hash": LEGACY_METADATA_HASHES["codec_hash"],
        "hash_function_version": "1",
        "hash_function_hash": LEGACY_METADATA_HASHES["hash_function_hash"],
    }
