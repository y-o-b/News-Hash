from __future__ import annotations

import os
import tracemalloc
from pathlib import Path

METRIC_DESCRIPTIONS = {
    "newshash_process_resident_memory_bytes": ("Resident memory used by the News-Hash process.", "gauge"),
    "newshash_process_resident_anonymous_memory_bytes": ("Anonymous resident memory used by the News-Hash process.", "gauge"),
    "newshash_process_resident_file_memory_bytes": ("File-backed resident memory used by the News-Hash process.", "gauge"),
    "newshash_process_resident_shared_memory_bytes": ("Shared resident memory used by the News-Hash process.", "gauge"),
    "newshash_process_virtual_memory_bytes": ("Virtual memory size of the News-Hash process.", "gauge"),
    "newshash_process_peak_resident_memory_bytes": ("Peak resident memory used by the News-Hash process.", "gauge"),
    "newshash_cgroup_memory_current_bytes": ("Current memory charged to the News-Hash cgroup.", "gauge"),
    "newshash_cgroup_memory_limit_bytes": ("Memory limit of the News-Hash cgroup when one is configured.", "gauge"),
    "newshash_cgroup_memory_available_bytes": ("Memory remaining before the News-Hash cgroup memory limit.", "gauge"),
    "newshash_cgroup_memory_anonymous_bytes": ("Anonymous memory charged to the News-Hash cgroup.", "gauge"),
    "newshash_cgroup_memory_file_bytes": ("File cache charged to the News-Hash cgroup.", "gauge"),
    "newshash_cgroup_memory_inactive_file_bytes": ("Inactive file cache charged to the News-Hash cgroup.", "gauge"),
    "newshash_cgroup_memory_active_file_bytes": ("Active file cache charged to the News-Hash cgroup.", "gauge"),
    "newshash_cgroup_memory_events_total": ("Cgroup memory limit and out-of-memory events.", "counter"),
    "newshash_memory_pressure_stall_ratio": ("Fraction of time stalled by memory pressure during the given window.", "gauge"),
    "newshash_python_tracemalloc_enabled": ("Whether Python allocation tracing is enabled.", "gauge"),
    "newshash_python_traced_memory_bytes": ("Currently allocated Python-traced memory.", "gauge"),
    "newshash_python_traced_memory_peak_bytes": ("Peak Python-traced memory since process start.", "gauge"),
}


def configure_memory_tracing() -> None:
    """Aktiviere Python-Allokationstracing nur bei expliziter Diagnose-Konfiguration."""

    enabled = os.environ.get("NEWSHASH_TRACEMALLOC", "").strip().lower() in {"1", "true", "yes", "on"}
    if enabled and not tracemalloc.is_tracing():
        tracemalloc.start(1)


def _read_key_values(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return {parts[0]: parts[1] for line in lines if len(parts := line.split()) >= 2}


def _read_status_bytes(status_path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for key, value in _read_key_values(status_path).items():
        if key not in {"VmRSS:", "VmSize:", "VmHWM:", "RssAnon:", "RssFile:", "RssShmem:"}:
            continue
        try:
            values[key] = int(value) * 1024
        except ValueError:
            continue
    return values


def _cgroup_candidates(proc_root: Path, cgroup_root: Path) -> list[Path]:
    candidates: list[Path] = []
    try:
        cgroup_lines = (proc_root / "self" / "cgroup").read_text(encoding="utf-8").splitlines()
    except OSError:
        cgroup_lines = []

    for line in cgroup_lines:
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        controllers, relative_path = parts[1], parts[2].lstrip("/")
        path_parts = Path(relative_path).parts
        if ".." in path_parts:
            continue
        if not controllers:
            candidates.append(cgroup_root.joinpath(*path_parts))
        elif "memory" in controllers.split(","):
            candidates.append(cgroup_root / "memory" / Path(*path_parts))
            candidates.append(cgroup_root / "memory")

    candidates.append(cgroup_root)
    return list(dict.fromkeys(candidates))


def _read_cgroup_memory(proc_root: Path, cgroup_root: Path) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
    for directory in _cgroup_candidates(proc_root, cgroup_root):
        unified = directory / "memory.current"
        legacy = directory / "memory.usage_in_bytes"
        usage_path = unified if unified.is_file() else legacy
        if not usage_path.is_file():
            continue

        try:
            current = int(usage_path.read_text(encoding="utf-8").strip())
        except OSError, ValueError:
            continue

        limit_path = directory / ("memory.max" if unified == usage_path else "memory.limit_in_bytes")
        try:
            raw_limit = limit_path.read_text(encoding="utf-8").strip()
            limit = None if raw_limit == "max" else int(raw_limit)
        except OSError, ValueError:
            limit = None
        if limit is not None and limit >= 1 << 60:
            limit = None

        stats = _read_key_values(directory / "memory.stat")
        if unified == usage_path:
            aliases = {
                "anon": ("anon",),
                "file": ("file",),
                "inactive_file": ("inactive_file",),
                "active_file": ("active_file",),
            }
        else:
            aliases = {
                "anon": ("total_rss", "rss"),
                "file": ("total_cache", "cache"),
                "inactive_file": ("total_inactive_file", "inactive_file"),
                "active_file": ("total_active_file", "active_file"),
            }
        values = {"current": current}
        if limit is not None:
            values["limit"] = limit
            values["available"] = max(0, limit - current)
        for metric, keys in aliases.items():
            for key in keys:
                try:
                    values[metric] = int(stats[key])
                except KeyError, ValueError:
                    continue
                break

        events = _read_key_values(directory / "memory.events")
        if not events:
            try:
                events = {"failcnt": (directory / "memory.failcnt").read_text(encoding="utf-8").strip()}
            except OSError:
                events = {}
        pressure_path = directory / "memory.pressure"
        return values, {key: int(value) for key, value in events.items() if value.isdecimal()}, {"pressure": str(pressure_path)}
    return {}, {}, {}


def _append_pressure_samples(samples: list[tuple[str, str, int | float]], path: Path, scope: str) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        fields = line.split()
        if not fields or fields[0] not in {"some", "full"}:
            continue
        values = dict(field.split("=", 1) for field in fields[1:] if "=" in field)
        for key, window in (("avg10", "10s"), ("avg60", "60s"), ("avg300", "300s")):
            try:
                ratio = float(values[key]) / 100
            except KeyError, ValueError:
                continue
            samples.append(("newshash_memory_pressure_stall_ratio", f'scope="{scope}",stall="{fields[0]}",window="{window}"', ratio))


def render_memory_metrics(proc_root: Path = Path("/proc"), cgroup_root: Path = Path("/sys/fs/cgroup")) -> list[str]:
    """Lies Prozess-, Python- und cgroup-Speicherwerte für die Prometheus-Ausgabe."""

    samples: list[tuple[str, str, int | float]] = []
    process_values = _read_status_bytes(proc_root / "self" / "status")
    process_names = {
        "VmRSS:": "newshash_process_resident_memory_bytes",
        "RssAnon:": "newshash_process_resident_anonymous_memory_bytes",
        "RssFile:": "newshash_process_resident_file_memory_bytes",
        "RssShmem:": "newshash_process_resident_shared_memory_bytes",
        "VmSize:": "newshash_process_virtual_memory_bytes",
        "VmHWM:": "newshash_process_peak_resident_memory_bytes",
    }
    samples.extend((metric, "", process_values[key]) for key, metric in process_names.items() if key in process_values)

    cgroup_values, cgroup_events, cgroup_paths = _read_cgroup_memory(proc_root, cgroup_root)
    cgroup_names = {
        "current": "newshash_cgroup_memory_current_bytes",
        "limit": "newshash_cgroup_memory_limit_bytes",
        "available": "newshash_cgroup_memory_available_bytes",
        "anon": "newshash_cgroup_memory_anonymous_bytes",
        "file": "newshash_cgroup_memory_file_bytes",
        "inactive_file": "newshash_cgroup_memory_inactive_file_bytes",
        "active_file": "newshash_cgroup_memory_active_file_bytes",
    }
    samples.extend((metric, "", cgroup_values[key]) for key, metric in cgroup_names.items() if key in cgroup_values)
    samples.extend(("newshash_cgroup_memory_events_total", f'event="{event}"', count) for event, count in cgroup_events.items())

    samples.append(("newshash_python_tracemalloc_enabled", "", int(tracemalloc.is_tracing())))
    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        samples.extend(
            [
                ("newshash_python_traced_memory_bytes", "", current),
                ("newshash_python_traced_memory_peak_bytes", "", peak),
            ]
        )

    _append_pressure_samples(samples, proc_root / "pressure" / "memory", "host")
    if cgroup_paths:
        _append_pressure_samples(samples, Path(cgroup_paths["pressure"]), "cgroup")

    lines = []
    for name, (description, metric_type) in METRIC_DESCRIPTIONS.items():
        lines.extend((f"# HELP {name} {description}", f"# TYPE {name} {metric_type}"))
        for sample_name, labels, value in samples:
            if sample_name == name:
                suffix = f"{{{labels}}}" if labels else ""
                lines.append(f"{name}{suffix} {value}")
    return lines
