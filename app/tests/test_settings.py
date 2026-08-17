from __future__ import annotations

import pytest

from newshash.settings import SettingsManager


def write_settings(tmp_path, content: str):
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(content.strip(), encoding="utf-8")
    return settings_path


def test_loads_source_with_default_codec(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        poll_interval_seconds = 300
        """,
    )

    settings = SettingsManager().load_settings(settings_path)

    assert len(settings.sources) == 1
    source = settings.sources[0]
    assert source.name == "alpha"
    assert source.codec_name == "RSSv2"
    assert source.poll_interval_seconds == 300
    assert settings.heartbeat_url is None


def test_loads_optional_heartbeat_url(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        heartbeat_url = " https://example.invalid/heartbeat "

        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        poll_interval_seconds = 300
        """,
    )

    settings = SettingsManager().load_settings(settings_path)

    assert settings.heartbeat_url == "https://example.invalid/heartbeat"


def test_parses_poll_intervals_and_codec(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        codec_name = "RSSv2"
        poll_interval_seconds = 7

        [[sources]]
        name = "beta"
        feed_url = "https://example.invalid/b"
        storage_name = "beta"
        poll_interval_seconds = 42
        """,
    )

    settings = SettingsManager().load_settings(settings_path)

    assert settings.sources[0].poll_interval_seconds == 7
    assert settings.sources[1].poll_interval_seconds == 42


def test_rejects_unknown_codec_name(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        codec_name = "Unknown"
        poll_interval_seconds = 300
        """,
    )

    with pytest.raises(ValueError, match="unknown codec_name"):
        SettingsManager().load_settings(settings_path)


def test_rejects_historical_codec_for_new_configuration(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "legacy"
        feed_url = "https://example.invalid/legacy"
        storage_name = "legacy"
        codec_name = "RSSv1"
        poll_interval_seconds = 300
        """,
    )

    with pytest.raises(ValueError, match="unknown codec_name"):
        SettingsManager().load_settings(settings_path)


def test_rejects_missing_sources(tmp_path) -> None:
    settings_path = write_settings(tmp_path, "")

    with pytest.raises(ValueError, match="at least one"):
        SettingsManager().load_settings(settings_path)


def test_rejects_invalid_poll_interval(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        poll_interval_seconds = 0
        """,
    )

    with pytest.raises(ValueError, match="poll_interval_seconds"):
        SettingsManager().load_settings(settings_path)


def test_rejects_missing_poll_interval(tmp_path) -> None:
    settings_path = write_settings(
        tmp_path,
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        """,
    )

    with pytest.raises(ValueError, match="poll_interval_seconds"):
        SettingsManager().load_settings(settings_path)


def test_resolve_config_uses_default_path_when_none_given(tmp_path) -> None:
    settings_path = tmp_path / "data" / "settings.toml"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        """
        [[sources]]
        name = "alpha"
        feed_url = "https://example.invalid/a"
        storage_name = "alpha"
        poll_interval_seconds = 300
        """.strip(),
        encoding="utf-8",
    )

    manager = SettingsManager(data_dir=tmp_path / "data", default_settings_path=settings_path)
    config = manager.resolve_config(None)

    assert config.settings_path == settings_path
    assert len(config.settings.sources) == 1


def test_source_error_count_is_in_memory_only(tmp_path) -> None:
    manager = SettingsManager(data_dir=tmp_path)

    assert manager.source_error_counts() == {}
    assert manager.record_source_error("alpha") == 1
    assert manager.record_source_error("alpha", "Timeout") == 2
    assert manager.source_error_counts() == {"alpha": 2}
    assert manager.source_errors() == {"alpha": ["", "Timeout"]}
    assert SettingsManager(data_dir=tmp_path).source_error_counts() == {}


def test_runtime_logs_are_in_memory_only(tmp_path) -> None:
    manager = SettingsManager(data_dir=tmp_path)
    manager.log_runtime('source="alpha" action="fetch start"')

    assert manager.runtime_logs()[-1].endswith('source="alpha" action="fetch start"')
    assert SettingsManager(data_dir=tmp_path).runtime_logs() == []
