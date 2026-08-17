from __future__ import annotations

import json

from newshash.codec import GENESIS_HASH, RSSv0
from newshash.settings import SourceConfig
from newshash.validation import validate_source


def _record(codec: RSSv0, source_id: str, previous_hash: str) -> dict:
    return codec.finalize_record(
        {
            "source_id": source_id,
            "source_url": f"https://example.invalid/{source_id}",
            "title": source_id,
            "content": f"content {source_id}",
            "author_name": "author",
            "codec_name": codec.codec_name,
            "published_at": "2026-08-17T10:00:00Z",
            "retrieved_at": "2026-08-17T10:01:00Z",
            "images": {},
        },
        previous_hash,
    )


def test_validate_source_checks_latest_shard_and_all_shards(tmp_path) -> None:
    source = SourceConfig("Example", "feed", "example", 300)
    codec = RSSv0()
    first = _record(codec, "one", GENESIS_HASH)
    second = _record(codec, "two", first["hash"])
    (tmp_path / "example.0.jsonl").write_text(json.dumps(first) + "\n", encoding="utf-8")
    (tmp_path / "example.1.jsonl").write_text(json.dumps(second) + "\n", encoding="utf-8")

    latest_jsonl, latest_sqlite = validate_source(tmp_path, source)
    assert latest_jsonl.valid
    assert latest_jsonl.shards_checked == (1,)
    assert latest_jsonl.records_checked == 1
    assert latest_sqlite.valid

    all_jsonl, all_sqlite = validate_source(tmp_path, source, all_shards=True)
    assert all_jsonl.valid
    assert all_jsonl.shards_checked == (0, 1)
    assert all_jsonl.records_checked == 2
    assert all_sqlite.valid


def test_validate_source_reports_corruption_in_selected_shard(tmp_path) -> None:
    source = SourceConfig("Example", "feed", "example", 300)
    codec = RSSv0()
    first = _record(codec, "one", GENESIS_HASH)
    second = _record(codec, "two", first["hash"])
    second["title"] = "changed"
    (tmp_path / "example.0.jsonl").write_text(json.dumps(first) + "\n", encoding="utf-8")
    (tmp_path / "example.1.jsonl").write_text(json.dumps(second) + "\n", encoding="utf-8")

    latest_jsonl, _ = validate_source(tmp_path, source)

    assert not latest_jsonl.valid
    assert "hash=" in latest_jsonl.errors[0]
