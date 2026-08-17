from __future__ import annotations

from typing import Protocol


class AnchorableResult(Protocol):
    """Minimale Result-Schnittstelle für das OpenTimestamps-Anchoring."""

    latest_hash_jsonl: str
    latest_hash_sqlite: str
    latest_shard_jsonl: int
    latest_shard_sqlite: int
