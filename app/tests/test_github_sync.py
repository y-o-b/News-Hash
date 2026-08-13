from __future__ import annotations

import base64
from datetime import date

from newshash.github_sync import GitHubAnchorPublisher, read_github_token
from newshash.settings import SourceConfig


def test_read_github_token(tmp_path) -> None:
    credentials = tmp_path / "credentials.env"
    credentials.write_text("OTHER=value\nGITHUB_TOKEN='secret-token'\n", encoding="utf-8")

    assert read_github_token(credentials) == "secret-token"


def test_publish_source_uploads_manifest_and_proof(tmp_path, monkeypatch) -> None:
    credentials = tmp_path / "credentials.env"
    credentials.write_text("GITHUB_TOKEN=secret-token\nGITHUB_REPOSITORY=y-o-b/News-Hash\n", encoding="utf-8")
    source = SourceConfig("ZDF", "feed", "zdf", 300)
    anchor_dir = tmp_path / "anchors" / "2026-08-11"
    anchor_dir.mkdir(parents=True)
    (anchor_dir / "zdf.txt").write_text("manifest", encoding="utf-8")
    (anchor_dir / "zdf.txt.ots").write_bytes(b"proof")
    calls: list[str] = []

    class Response:
        status_code = 404

        def json(self):
            return {"content": {"html_url": "https://github.com/y-o-b/News-Hash/blob/main/anchor"}}

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append(f"GET {url}")
        return Response()

    def fake_put(url, **kwargs):
        calls.append(f"PUT {url}")
        return Response()

    monkeypatch.setattr("newshash.github_sync.requests.get", fake_get)
    monkeypatch.setattr("newshash.github_sync.requests.put", fake_put)

    urls = GitHubAnchorPublisher(tmp_path, credentials).publish_source(source, date(2026, 8, 11))

    assert len(urls) == 2
    assert calls == [
        "GET https://api.github.com/repos/y-o-b/News-Hash/contents/anchors/2026-08-11/zdf.txt",
        "PUT https://api.github.com/repos/y-o-b/News-Hash/contents/anchors/2026-08-11/zdf.txt",
        "GET https://api.github.com/repos/y-o-b/News-Hash/contents/anchors/2026-08-11/zdf.txt.ots",
        "PUT https://api.github.com/repos/y-o-b/News-Hash/contents/anchors/2026-08-11/zdf.txt.ots",
    ]


def test_publish_source_skips_unchanged_files(tmp_path, monkeypatch) -> None:
    credentials = tmp_path / "credentials.env"
    credentials.write_text("GITHUB_TOKEN=secret-token\nGITHUB_REPOSITORY=y-o-b/News-Hash\n", encoding="utf-8")
    source = SourceConfig("ZDF", "feed", "zdf", 300)
    anchor_dir = tmp_path / "anchors" / "2026-08-11"
    anchor_dir.mkdir(parents=True)
    (anchor_dir / "zdf.txt").write_text("manifest", encoding="utf-8")
    (anchor_dir / "zdf.txt.ots").write_bytes(b"proof")
    calls: list[str] = []

    class Response:
        status_code = 200

        def __init__(self, content: bytes, name: str) -> None:
            self._data = {
                "sha": f"sha-{name}",
                "content": base64.b64encode(content).decode("ascii"),
                "html_url": f"https://github.com/y-o-b/News-Hash/blob/main/{name}",
            }

        def json(self):
            return self._data

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append(f"GET {url}")
        content = b"manifest" if url.endswith("zdf.txt") else b"proof"
        return Response(content, url.rsplit("/", 1)[-1])

    def fake_put(url, **kwargs):
        calls.append(f"PUT {url}")
        raise AssertionError("unchanged anchor files must not be uploaded")

    monkeypatch.setattr("newshash.github_sync.requests.get", fake_get)
    monkeypatch.setattr("newshash.github_sync.requests.put", fake_put)

    urls = GitHubAnchorPublisher(tmp_path, credentials).publish_source(source, date(2026, 8, 11))

    assert len(urls) == 2
    assert all(call.startswith("GET ") for call in calls)
