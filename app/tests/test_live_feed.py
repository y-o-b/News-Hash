from __future__ import annotations

from pathlib import Path

import pytest
import requests

from newshash.codec import DEFAULT_CODEC
from newshash.settings import SettingsManager


def _load_live_sources():
    settings = SettingsManager().load_settings(Path("data/settings.toml"))
    return settings.sources


@pytest.mark.parametrize("source", _load_live_sources(), ids=lambda source: source.name)
def test_live_feed_matches_expected_format(source) -> None:
    """Rufe den echten RSSBridge-Feed ab und pruefe das erwartete Feldformat."""

    try:
        feed = DEFAULT_CODEC.fetch_feed(source.feed_url)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"feed not reachable: {exc}")

    assert isinstance(feed, dict)
    assert isinstance(feed.get("items"), list)
    assert len(feed["items"]) > 0

    for item in feed["items"][:5]:
        assert isinstance(item, dict)
        assert isinstance(item.get("id"), str) and item["id"].strip()
        assert isinstance(item.get("title"), str) and item["title"].strip()
        assert isinstance(item.get("url"), str) and item["url"].strip()
        assert isinstance(item.get("content_html"), str)

        rssbridge = item.get("_rssbridge")
        assert isinstance(rssbridge, dict)
        assert "link" in rssbridge
        if "dc" in rssbridge:
            assert isinstance(rssbridge["dc"], dict)

        # Mindestens eine der autoritativen Quellen fuer published_at muss vorhanden sein.
        dc_date = rssbridge.get("dc", {}).get("date") if isinstance(rssbridge.get("dc"), dict) else None
        assert dc_date or rssbridge.get("pubDate") or rssbridge.get("published") or rssbridge.get("updated")
