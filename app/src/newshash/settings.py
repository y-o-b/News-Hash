from __future__ import annotations

import threading
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from newshash.codec import CODEC_REGISTRY

DEFAULT_SETTINGS_PATH = Path("data/settings.toml")
DEFAULT_DATA_DIR = Path("data")
DEFAULT_CODEC_NAME = "RSSv2"


@dataclass(frozen=True)
class SourceConfig:
    """Validierte Konfiguration fuer eine einzelne Feed-Quelle."""

    name: str
    feed_url: str
    storage_name: str
    poll_interval_seconds: int
    codec_name: str = DEFAULT_CODEC_NAME


@dataclass(frozen=True)
class Settings:
    """Gesamte geladene Settings-Datei."""

    sources: tuple[SourceConfig, ...]
    heartbeat_url: str | None = None


@dataclass(frozen=True)
class AppConfig:
    """Aufgeloeste Laufkonfiguration fuer einen App-Start."""

    settings_path: Path
    settings: Settings


class SettingsManager:
    """Laedt, validiert und loest Anwendungseinstellungen auf."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, default_settings_path: Path = DEFAULT_SETTINGS_PATH) -> None:
        """Initialisiere den Settings-Manager mit Daten- und Standardpfad."""

        self.data_dir = data_dir
        self.default_settings_path = default_settings_path
        self._source_errors: dict[str, list[str]] = {}
        self._source_error_types: dict[str, list[str]] = {}
        self._runtime_logs: list[str] = []
        self._anchor_statuses: dict[str, str] = {}
        self._runtime_lock = threading.Lock()
        self._source_error_acknowledged: dict[str, int] = {}

    def load_settings(self, settings_path: Path) -> Settings:
        """Lade und validiere die Quellenkonfiguration aus TOML."""

        with settings_path.open("rb") as handle:
            data = tomllib.load(handle)

        raw_sources = data.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources:
            raise ValueError("settings.toml must define at least one [[sources]] entry")

        raw_heartbeat_url = data.get("heartbeat_url")
        if raw_heartbeat_url is not None and not isinstance(raw_heartbeat_url, str):
            raise ValueError("heartbeat_url must be a string")
        heartbeat_url = raw_heartbeat_url.strip() or None if raw_heartbeat_url is not None else None

        sources: list[SourceConfig] = []
        for index, raw_source in enumerate(raw_sources, start=1):
            sources.append(self._parse_source(raw_source, index))

        return Settings(sources=tuple(sources), heartbeat_url=heartbeat_url)

    def _parse_source(self, raw_source: object, index: int) -> SourceConfig:
        """Validiere und parse einen einzelnen Quellen-Eintrag."""

        if not isinstance(raw_source, dict):
            raise ValueError(f"Source #{index} must be a table")

        name = raw_source.get("name")
        feed_url = raw_source.get("feed_url")
        storage_name = raw_source.get("storage_name")
        codec_name = raw_source.get("codec_name", DEFAULT_CODEC_NAME)
        poll_interval_seconds = raw_source.get("poll_interval_seconds")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Source #{index} is missing a valid name")
        if not isinstance(feed_url, str) or not feed_url.strip():
            raise ValueError(f"Source {name} is missing a valid feed_url")
        if not isinstance(storage_name, str) or not storage_name.strip():
            raise ValueError(f"Source {name} is missing a valid storage_name value")
        if not isinstance(codec_name, str) or not codec_name.strip():
            raise ValueError(f"Source {name} is missing a valid codec_name value")
        if codec_name.strip() not in CODEC_REGISTRY:
            raise ValueError(f"Source {name} uses an unknown codec_name: {codec_name}")
        if not isinstance(poll_interval_seconds, int) or isinstance(poll_interval_seconds, bool) or poll_interval_seconds <= 0:
            raise ValueError(f"Source {name} is missing a valid poll_interval_seconds value")

        return SourceConfig(
            name=name.strip(),
            feed_url=feed_url.strip(),
            storage_name=storage_name.strip(),
            poll_interval_seconds=poll_interval_seconds,
            codec_name=codec_name.strip(),
        )

    def resolve_config(self, settings_path: str | None) -> AppConfig:
        """Loese die endgueltige Laufkonfiguration fuer einen Start auf."""

        resolved_settings_path = Path(settings_path) if settings_path else self.default_settings_path
        settings = self.load_settings(resolved_settings_path)
        return AppConfig(settings_path=resolved_settings_path, settings=settings)

    def storage_root(self) -> Path:
        """Gib das Storage-Stammverzeichnis zurueck."""

        return self.data_dir

    def source_error_counts(self) -> dict[str, int]:
        """Gib die seit dem Start gezählten Fehler je Quelle zurueck."""

        with self._runtime_lock:
            return {name: len(errors) for name, errors in self._source_errors.items()}

    def source_errors(self) -> dict[str, list[str]]:
        """Gib die flüchtig gespeicherten Fehlermeldungen je Quelle zurueck."""

        with self._runtime_lock:
            return {name: list(errors) for name, errors in self._source_errors.items()}

    def unacknowledged_source_error_counts(self) -> dict[str, int]:
        """Gib die noch nicht quittierten Fehler je Quelle zurueck."""

        with self._runtime_lock:
            return {
                name: len(errors) - self._source_error_acknowledged.get(name, 0)
                for name, errors in self._source_errors.items()
                if len(errors) > self._source_error_acknowledged.get(name, 0)
            }

    def unacknowledged_source_errors(self) -> dict[str, list[str]]:
        """Gib die noch nicht quittierten Fehlermeldungen je Quelle zurueck."""

        with self._runtime_lock:
            return {
                name: list(errors[self._source_error_acknowledged.get(name, 0) :])
                for name, errors in self._source_errors.items()
                if len(errors) > self._source_error_acknowledged.get(name, 0)
            }

    def unacknowledged_source_error_type_counts(self) -> dict[tuple[str, str], int]:
        """Gib die noch nicht quittierten Fehler nach Quelle und Typ zurück."""

        with self._runtime_lock:
            counts: dict[tuple[str, str], int] = {}
            for source_name, error_types in self._source_error_types.items():
                acknowledged = self._source_error_acknowledged.get(source_name, 0)
                for error_type in error_types[acknowledged:]:
                    key = source_name, error_type
                    counts[key] = counts.get(key, 0) + 1
            return counts

    def record_source_error(self, source_name: str, message: str = "", error_type: str = "unknown") -> int:
        """Erhöhe den flüchtigen Fehlerzähler einer Quelle um eins."""

        with self._runtime_lock:
            errors = self._source_errors.setdefault(source_name, [])
            error_types = self._source_error_types.setdefault(source_name, [])
            acknowledged = min(self._source_error_acknowledged.get(source_name, 0), len(errors))
            errors.append(message)
            error_types.append(error_type)
            removed = max(0, len(errors) - 10)
            if removed:
                del errors[:removed]
                del error_types[:removed]
            self._source_error_acknowledged[source_name] = max(0, acknowledged - removed)
            return len(errors)

    def acknowledge_source_errors(self, source_name: str) -> bool:
        """Quittiere alle bis jetzt aufgelaufenen Fehler einer Quelle."""

        with self._runtime_lock:
            if source_name not in self._source_errors:
                return False
            self._source_error_acknowledged[source_name] = len(self._source_errors[source_name])
            return True

    def log_runtime(self, message: str) -> None:
        """Speichere ein flüchtiges Laufzeitereignis für die WebUI."""

        entry = f"{datetime.now(UTC).isoformat(timespec='seconds')} {message}"
        with self._runtime_lock:
            self._runtime_logs.append(entry)
            del self._runtime_logs[:-100]

    def runtime_logs(self) -> list[str]:
        """Gib die letzten flüchtigen Laufzeitereignisse zurück."""

        with self._runtime_lock:
            return list(self._runtime_logs)

    def set_anchor_status(self, source_name: str, status: str) -> None:
        """Speichere den flüchtigen Anchor-Status einer Quelle."""

        self._anchor_statuses[source_name] = status

    def anchor_statuses(self) -> dict[str, str]:
        """Gib die zuletzt geprüften flüchtigen Anchor-Statuswerte zurück."""

        return dict(self._anchor_statuses)
