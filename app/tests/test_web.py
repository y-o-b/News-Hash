from __future__ import annotations

from newshash.settings import AppConfig, Settings, SettingsManager, SourceConfig
from newshash.web import SourceSummary, render_dashboard, render_detail, render_help, render_metrics


def test_render_dashboard_contains_metrics_and_latest_records() -> None:
    page = render_dashboard(
        {
            "generated_at": "2026-08-10T20:00:00+00:00",
            "sources": [
                SourceSummary(
                    "ZDFheute",
                    "zdf",
                    157,
                    12,
                    "2026-08-10T19:59:00+00:00",
                    "hash",
                    2,
                    "Timeout",
                    (("fetch", 1), ("interpret", 1)),
                    True,
                    "complete",
                    sqlite_size_bytes=1536,
                )
            ],
            "records": [
                {
                    "source_name": "ZDFheute",
                    "title": "Neue Meldung",
                    "source_url": "https://example.invalid/news",
                    "published_at": "2026-08-10T19:58:00+00:00",
                    "hash": "abc123",
                }
            ],
            "total_records": 157,
            "total_images": 12,
            "runtime_logs": ["2026-08-11T17:00:00Z source=ZDF action=stored"],
        }
    )

    assert "<title>News-Hash</title>" in page
    assert 'src="/logo.svg?theme=lite"' in page
    assert 'href="/favicon.svg?v=1&amp;theme=lite"' in page
    assert "157" in page
    assert "12" in page
    assert "text-shadow:4px 4px 0 var(--accent)" not in page
    assert "grid-template-columns:repeat(3,1fr)" in page
    assert "min(100%,440px)" in page
    assert "SQLite: 1,5 KB" in page
    assert "2 Fehler" in page
    assert "body.theme-comic .updated" in page
    assert "Fehler nach Typ: fetch: 1, interpret: 1" in page
    assert "Hash: hash" in page
    assert "Timeout" in page
    assert "Fehler quittieren" in page
    assert "/acknowledge-error" in page
    assert "anchor-complete" in page
    assert "Vollständig bestätigt" in page
    assert "Neue Meldung" in page
    assert ".latest { list-style:none; padding:0; margin:0 }" in page
    assert "Hash: abc123" in page
    assert "Jetzt abrufen" in page
    assert "Quelle filtern" in page
    assert "source-actions" in page
    assert 'value="monet"' in page
    assert "theme-monet" in page
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in page
    assert "Laufzeit-Log" in page
    assert "action=stored" in page
    assert 'id="refresh-countdown"' in page
    assert "location.reload()" in page
    assert "Math.random()" in page
    assert "@media print" in page
    assert "/meldung//" in page
    assert "Daemon beenden" in page
    assert "OpenCode" in page
    assert "https://www.y-o-b.de/" in page
    assert 'fetch("/shutdown"' in page
    assert 'class="local-time"' in page
    assert 'Intl.DateTimeFormat("de-DE"' in page


def test_render_dashboard_escapes_record_content() -> None:
    page = render_dashboard(
        {
            "generated_at": "now",
            "sources": [],
            "records": [{"source_name": "<source>", "title": "<script>alert(1)</script>", "source_url": "#"}],
            "total_records": 1,
            "total_images": 0,
        }
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_render_dashboard_supports_source_filter_and_pagination() -> None:
    page = render_dashboard(
        {
            "generated_at": "now",
            "sources": [SourceSummary("ZDFheute", "zdf", 21, 0, "", "")],
            "records": [],
            "total_records": 21,
            "total_images": 0,
            "selected_source": "zdf",
            "page": 2,
            "total_pages": 3,
        }
    )

    assert "source=zdf" in page
    assert "theme=lite" in page
    assert "Filter zurücksetzen" in page
    assert "Meldungen · zdf" in page
    assert "Seite 2 von 3" in page
    assert 'id="neueste-meldungen"' in page
    assert "#neueste-meldungen" in page
    assert "Meldungen pro Seite" in page
    assert 'option value="25"' in page
    assert "changePageSize" in page
    assert "&lt;&lt; Erste" in page
    assert "Weiter &gt;" in page
    assert "Letzte &gt;&gt;" in page


def test_render_detail_links_stored_images() -> None:
    page = render_detail(
        {
            "title": "Gespeicherte Meldung",
            "published_at": "2026-08-10T17:40:00Z",
            "retrieved_at": "2026-08-10T18:00:00Z",
            "content": "<p>Inhalt</p>",
            "hash": "hash-value",
            "previous_hash": "pre-hash-value",
            "images": {"hash": {"path": "images/20260810T174000-0001.jpg"}},
        },
        "ZDFheute",
        storage_name="zdf",
    )

    assert "Gespeicherte Meldung" in page
    assert "/media/zdf/hash" in page
    assert "<p>Inhalt</p>" in page
    assert "hash-value" in page
    assert "pre-hash-value" in page
    assert "#neueste-meldungen" in page
    assert 'Intl.DateTimeFormat("de-DE"' in page


def test_render_metrics_contains_source_and_total_values(tmp_path, monkeypatch) -> None:
    from newshash import web
    from newshash.settings import AppConfig, Settings, SettingsManager, SourceConfig

    config = AppConfig(tmp_path / "settings.toml", Settings((SourceConfig("ZDF", "feed", "zdf", 300),)))
    monkeypatch.setattr(
        web.SqliteStorage,
        "dashboard_stats",
        lambda self: {"records": 12, "images": 3, "latest_retrieved_at": "", "latest_hash": ""},
    )

    metrics = render_metrics(config, SettingsManager(data_dir=tmp_path))

    assert 'newshash_records_total{source="ZDF"} 12' in metrics
    assert 'newshash_images_total{source="ZDF"} 3' in metrics
    assert "newshash_records_all_total 12" in metrics
    assert "newshash_images_all_total 3" in metrics
    assert 'newshash_source_errors_total{source="ZDF"} 0' in metrics


def test_render_metrics_hides_acknowledged_source_errors(tmp_path, monkeypatch) -> None:
    from newshash import web

    config = AppConfig(tmp_path / "settings.toml", Settings((SourceConfig("ZDF", "feed", "zdf", 300),)))
    monkeypatch.setattr(
        web.SqliteStorage,
        "dashboard_stats",
        lambda self: {"records": 0, "images": 0, "latest_retrieved_at": "", "latest_hash": ""},
    )
    manager = SettingsManager(data_dir=tmp_path)
    manager.record_source_error("ZDF", "Timeout")
    manager.acknowledge_source_errors("ZDF")

    metrics = render_metrics(config, manager)

    assert 'newshash_source_errors_total{source="ZDF"} 0' in metrics
    assert "newshash_source_errors_all_total 0" in metrics


def test_render_help_contains_faq() -> None:
    page = render_help("lite")

    assert "News-Hash" in page
    assert "FAQ" in page
    assert "Was bedeutet der Hash?" in page
    assert "/metrics" in page


def test_render_help_supports_english() -> None:
    page = render_help("lite", "en")

    assert "The idea behind the project" in page
    assert "What does the hash mean?" in page
    assert "Deutsch" in page


def test_render_help_finds_documentation_in_container_layout(tmp_path, monkeypatch) -> None:
    from newshash import web

    package_path = tmp_path / "app" / "src" / "newshash"
    documentation_path = tmp_path / "app" / "project-docu"
    package_path.mkdir(parents=True)
    documentation_path.mkdir(parents=True)
    (documentation_path / "description_for_enduser.md").write_text("# Container help", encoding="utf-8")
    monkeypatch.setattr(web, "__file__", str(package_path / "web.py"))

    page = web.render_help("lite")

    assert "Container help" in page


def test_dashboard_sorts_published_at_by_instant(tmp_path, monkeypatch) -> None:
    from newshash import web

    records = [
        {"published_at": "2026-08-10T17:40:00Z", "retrieved_at": "a", "source_name": "ZDF", "title": "UTC"},
        {"published_at": "Mon, 10 Aug 2026 19:30:00 +0200", "retrieved_at": "b", "source_name": "ZDF", "title": "Lokalzeit"},
    ]
    monkeypatch.setattr(
        web.SqliteStorage,
        "dashboard_stats",
        lambda self: {"records": 2 if self.storage_name == "zdf" else 0, "images": 0, "latest_retrieved_at": "", "latest_hash": ""},
    )
    monkeypatch.setattr(web.SqliteStorage, "latest_count", lambda self: 2 if self.storage_name == "zdf" else 0)
    monkeypatch.setattr(web.SqliteStorage, "latest_records", lambda self, limit: records if self.storage_name == "zdf" else [])

    config = AppConfig(
        settings_path=tmp_path / "settings.toml",
        settings=Settings(sources=(SourceConfig("ZDF", "feed", "zdf", 300), SourceConfig("Other", "feed", "other", 300))),
    )
    data = web.collect_dashboard_data(config, SettingsManager(data_dir=tmp_path))

    assert [record["title"] for record in data["records"]] == ["UTC", "Lokalzeit"]
