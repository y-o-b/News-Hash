from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from newshash.codec import GENESIS_HASH, RSSv0, RSSv1, SCREENv0


def make_item(item_id: str = "example-1", content_html: str = "<p>Text</p>") -> dict:
    return {
        "id": item_id,
        "title": "Beispielnachricht",
        "url": "https://example.invalid/article-1",
        "content_html": content_html,
        "date_modified": "2026-07-29T10:00:00Z",
        "author": {"name": "Redaktion"},
        "_rssbridge": {
            "link": "https://example.invalid/article-1",
            "dc": {"date": "2026-07-29T10:00:00Z"},
            "guid": "guid-1",
        },
    }


def test_fetch_feed_parses_xml_rss(monkeypatch) -> None:
    response = requests.Response()
    response.status_code = 200
    response.headers["Content-Type"] = "application/xml"
    response._content = b"""<rss><channel><item>
        <title>Nachricht</title><link>https://example.invalid/news</link>
        <description>Text</description><pubDate>Mon, 10 Aug 2026 19:40:00 +0200</pubDate>
        <guid>guid-1</guid><enclosure url=\"https://example.invalid/image.jpg\" />
    </item></channel></rss>"""
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    feed = RSSv0().fetch_feed("https://example.invalid/feed")

    item = feed["items"][0]
    assert item["id"] == "guid-1"
    assert item["url"] == "https://example.invalid/news"
    assert item["date_modified"] == "2026-08-10T17:40:00Z"
    assert 'src="https://example.invalid/image.jpg"' in item["content_html"]


def test_prepare_item_ignores_date_modified(tmp_path) -> None:
    codec = RSSv0()
    item = make_item()
    item["date_modified"] = "2099-01-01T00:00:00Z"

    prepared, _ = codec.prepare_item(item, "2026-07-29T10:05:00Z", tmp_path, tmp_path / "images")

    assert prepared["published_at"] == "2026-07-29T10:00:00Z"


def test_prepare_item_normalizes_rfc_timestamp(tmp_path) -> None:
    codec = RSSv0()
    item = make_item()
    item["_rssbridge"]["dc"] = {}
    item["_rssbridge"]["pubDate"] = "Tue, 11 Aug 2026 19:01:23 +0200"

    prepared, _ = codec.prepare_item(item, "2026-07-29T10:05:00Z", tmp_path, tmp_path / "images")

    assert prepared["published_at"] == "2026-08-11T17:01:23Z"


def test_screen_codec_stores_full_page_screenshot(tmp_path, monkeypatch) -> None:
    codec = SCREENv0()

    def fake_screenshot(url: str, path: Path) -> bytes:
        data = b"fake-png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    monkeypatch.setattr(codec, "capture_screenshot", fake_screenshot)
    item, image_bytes = codec.prepare_item(make_item(), "2026-07-29T10:05:00Z", tmp_path, tmp_path / "images")

    assert len(item["images"]) == 1
    image = next(iter(item["images"].values()))
    assert image["path"].endswith(".png")
    assert image_bytes


def test_screen_codec_processes_only_first_feed_item(monkeypatch) -> None:
    codec = SCREENv0()
    monkeypatch.setattr(RSSv0, "fetch_feed", lambda self, url: {"items": [{"id": "one"}, {"id": "two"}]})

    feed = codec.fetch_feed("https://example.invalid/feed")

    assert [item["id"] for item in feed["items"]] == ["one"]


def test_extract_image_urls_from_img_tags() -> None:
    codec = RSSv0()
    item = make_item(content_html='<p><img src="https://example.invalid/a.jpg"></p><img src="https://example.invalid/b.png">')

    urls = codec.extract_image_urls(item)

    assert urls == ["https://example.invalid/a.jpg", "https://example.invalid/b.png"]


def test_extract_image_urls_deduplicates() -> None:
    codec = RSSv0()
    item = make_item(content_html='<img src="https://example.invalid/a.jpg"><img src="https://example.invalid/a.jpg">')

    urls = codec.extract_image_urls(item)

    assert urls == ["https://example.invalid/a.jpg"]


def test_record_hash_material_has_exact_fields() -> None:
    codec = RSSv0()
    record = {
        "author_name": "Redaktion",
        "content": "<p>Text</p>",
        "codec_name": "RSSv0",
        "images": {},
        "published_at": "2026-07-29T10:00:00Z",
        "source_id": "example-1",
        "source_url": "https://example.invalid/article-1",
        "title": "Beispielnachricht",
        "retrieved_at": "2026-07-29T10:05:00Z",
    }

    material = codec.record_hash_material(record, GENESIS_HASH)

    assert set(material.keys()) == {
        "author_name",
        "content",
        "codec_name",
        "images",
        "previous_hash",
        "published_at",
        "source_id",
        "source_url",
        "title",
    }
    assert "retrieved_at" not in material
    assert material["previous_hash"] == GENESIS_HASH


def test_build_record_without_images(tmp_path) -> None:
    codec = RSSv0()
    item = make_item()

    record, image_bytes_by_hash = codec.build_record(item, "2026-07-29T10:05:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")

    assert record["codec_name"] == "RSSv0"
    assert record["source_id"] == "example-1"
    assert record["title"] == "Beispielnachricht"
    assert record["previous_hash"] == GENESIS_HASH
    assert record["images"] == {}
    assert image_bytes_by_hash == {}
    assert len(record["hash"]) == 64


def test_v1_record_contains_metadata_hashes_and_uses_them_in_hash(tmp_path) -> None:
    codec = RSSv1()
    item = make_item()

    record, _ = codec.build_record(item, "2026-07-29T10:05:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")

    assert record["schema_version"] == "1"
    assert len(record["schema_hash"]) == 64
    assert len(record["codec_hash"]) == 64
    assert len(record["hash_function_hash"]) == 64
    changed = dict(record, schema_hash="f" * 64)
    assert codec.digest_record(codec.record_hash_material(changed, GENESIS_HASH)) != record["hash"]


def test_build_record_ignores_retrieved_at_in_hash(tmp_path) -> None:
    codec = RSSv0()
    item = make_item()

    record_a, _ = codec.build_record(item, "2026-07-29T10:05:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")
    record_b, _ = codec.build_record(item, "2026-07-29T11:00:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")

    assert record_a["hash"] == record_b["hash"]
    assert record_a["retrieved_at"] != record_b["retrieved_at"]


def test_build_record_downloads_and_stores_images(tmp_path, monkeypatch) -> None:
    codec = RSSv0()
    image_bytes = b"fake-image-bytes"
    monkeypatch.setattr(codec, "fetch_image", lambda url: (image_bytes, "image/png"))

    item = make_item(content_html='<img src="https://example.invalid/pic.png">')
    storage_root = tmp_path
    image_root = tmp_path / "images"

    record, image_bytes_by_hash = codec.build_record(item, "2026-07-29T10:05:00Z", GENESIS_HASH, storage_root, image_root)

    image_hash = hashlib.sha256(image_bytes).hexdigest()
    assert list(record["images"].keys()) == [image_hash]
    assert record["images"][image_hash]["url"] == "https://example.invalid/pic.png"

    stored_path = storage_root / record["images"][image_hash]["path"]
    assert stored_path.exists()
    assert stored_path.parent == image_root
    assert stored_path.name.startswith("20260729T100000-")
    assert image_bytes_by_hash[image_hash] == image_bytes


def test_build_record_reuses_identical_image_for_same_publication_time(tmp_path, monkeypatch) -> None:
    codec = RSSv0()
    image_bytes = b"same-bytes"
    monkeypatch.setattr(codec, "fetch_image", lambda url: (image_bytes, "image/png"))

    storage_root = tmp_path
    image_root = tmp_path / "images"

    item_a = make_item("example-1", '<img src="https://example.invalid/a.png">')
    item_b = make_item("example-2", '<img src="https://example.invalid/b.png">')

    record_a, _ = codec.build_record(item_a, "2026-07-29T10:05:00Z", GENESIS_HASH, storage_root, image_root)
    record_b, _ = codec.build_record(item_b, "2026-07-29T10:06:00Z", record_a["hash"], storage_root, image_root)

    path_a = next(iter(record_a["images"].values()))["path"]
    path_b = next(iter(record_b["images"].values()))["path"]
    assert path_a == path_b
    assert len(list((image_root).glob("20260729T100000-*"))) == 1


def test_verify_record_hash_chain_detects_tampering() -> None:
    codec = RSSv0()
    record = {
        "source_id": "example-1",
        "source_url": "https://example.invalid/article-1",
        "codec_name": "RSSv0",
        "title": "Beispielnachricht",
        "content": "<p>Text</p>",
        "author_name": "Redaktion",
        "published_at": "2026-07-29T10:00:00Z",
        "retrieved_at": "2026-07-29T10:05:00Z",
        "previous_hash": GENESIS_HASH,
        "images": {},
        "hash": "broken",
    }

    assert not codec.verify_record_hash_chain([record])


def test_verify_record_hash_chain_accepts_valid_chain(tmp_path) -> None:
    codec = RSSv0()
    item = make_item()

    record, _ = codec.build_record(item, "2026-07-29T10:05:00Z", GENESIS_HASH, tmp_path, tmp_path / "images")

    assert codec.verify_record_hash_chain([record])


def test_download_image_falls_back_to_url_suffix_without_content_type(tmp_path, monkeypatch) -> None:
    codec = RSSv0()
    monkeypatch.setattr(codec, "fetch_image", lambda url: (b"bytes", None))

    path, image_hash, data = codec.download_image("https://example.invalid/pic.jpg", tmp_path / "images", "2026-07-29T10:00:00Z", 1)

    assert Path(path).suffix == ".jpg"
    assert data == b"bytes"
    assert len(image_hash) == 64
