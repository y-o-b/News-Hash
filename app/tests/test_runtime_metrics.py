from __future__ import annotations

from newshash import runtime_metrics


def test_render_memory_metrics_reads_process_and_cgroup_values(tmp_path, monkeypatch) -> None:
    proc_root = tmp_path / "proc"
    cgroup_root = tmp_path / "cgroup"
    process_dir = proc_root / "self"
    cgroup_dir = cgroup_root / "slice" / "newshash"
    pressure_dir = proc_root / "pressure"
    process_dir.mkdir(parents=True)
    cgroup_dir.mkdir(parents=True)
    pressure_dir.mkdir(parents=True)
    (process_dir / "status").write_text("VmRSS:\t123 kB\nVmHWM:\t456 kB\nRssAnon:\t100 kB\nRssFile:\t20 kB\n", encoding="utf-8")
    (process_dir / "cgroup").write_text("0::/slice/newshash\n", encoding="utf-8")
    (cgroup_dir / "memory.current").write_text("700000\n", encoding="utf-8")
    (cgroup_dir / "memory.max").write_text("1000000\n", encoding="utf-8")
    (cgroup_dir / "memory.stat").write_text("anon 400000\nfile 250000\ninactive_file 200000\nactive_file 50000\n", encoding="utf-8")
    (cgroup_dir / "memory.events").write_text("high 2\nmax 1\noom 0\noom_kill 0\n", encoding="utf-8")
    (cgroup_dir / "memory.pressure").write_text("some avg10=2.50 avg60=1.00 avg300=0.50 total=100\n", encoding="utf-8")
    (pressure_dir / "memory").write_text("full avg10=0.25 avg60=0.10 avg300=0.05 total=20\n", encoding="utf-8")
    monkeypatch.setattr(runtime_metrics.tracemalloc, "is_tracing", lambda: False)

    lines = runtime_metrics.render_memory_metrics(proc_root, cgroup_root)

    assert "newshash_process_resident_memory_bytes 125952" in lines
    assert "newshash_process_peak_resident_memory_bytes 466944" in lines
    assert "newshash_cgroup_memory_current_bytes 700000" in lines
    assert "newshash_cgroup_memory_available_bytes 300000" in lines
    assert 'newshash_cgroup_memory_events_total{event="oom_kill"} 0' in lines
    assert 'newshash_memory_pressure_stall_ratio{scope="cgroup",stall="some",window="10s"} 0.025' in lines
    assert 'newshash_memory_pressure_stall_ratio{scope="host",stall="full",window="10s"} 0.0025' in lines
    assert "newshash_python_tracemalloc_enabled 0" in lines


def test_render_memory_metrics_omits_unavailable_system_values(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_metrics.tracemalloc, "is_tracing", lambda: False)

    lines = runtime_metrics.render_memory_metrics(tmp_path / "proc", tmp_path / "cgroup")

    assert not any(line.startswith("newshash_process_resident_memory_bytes ") for line in lines)
    assert not any(line.startswith("newshash_cgroup_memory_current_bytes ") for line in lines)
    assert "newshash_python_tracemalloc_enabled 0" in lines


def test_render_memory_metrics_reads_legacy_cgroup_memory_files(tmp_path, monkeypatch) -> None:
    proc_root = tmp_path / "proc"
    cgroup_root = tmp_path / "cgroup"
    cgroup_dir = cgroup_root / "memory" / "docker" / "container"
    (proc_root / "self").mkdir(parents=True)
    cgroup_dir.mkdir(parents=True)
    (proc_root / "self" / "cgroup").write_text("5:memory:/docker/container\n", encoding="utf-8")
    (cgroup_dir / "memory.usage_in_bytes").write_text("500000\n", encoding="utf-8")
    (cgroup_dir / "memory.limit_in_bytes").write_text("9223372036854771712\n", encoding="utf-8")
    (cgroup_dir / "memory.stat").write_text("total_rss 300000\ntotal_cache 150000\n", encoding="utf-8")
    (cgroup_dir / "memory.failcnt").write_text("4\n", encoding="utf-8")
    monkeypatch.setattr(runtime_metrics.tracemalloc, "is_tracing", lambda: False)

    lines = runtime_metrics.render_memory_metrics(proc_root, cgroup_root)

    assert "newshash_cgroup_memory_current_bytes 500000" in lines
    assert "newshash_cgroup_memory_anonymous_bytes 300000" in lines
    assert "newshash_cgroup_memory_file_bytes 150000" in lines
    assert 'newshash_cgroup_memory_events_total{event="failcnt"} 4' in lines
    assert not any(line.startswith("newshash_cgroup_memory_limit_bytes ") for line in lines)


def test_configure_memory_tracing_is_opt_in(monkeypatch) -> None:
    tracing_started = []
    monkeypatch.setenv("NEWSHASH_TRACEMALLOC", "1")
    monkeypatch.setattr(runtime_metrics.tracemalloc, "is_tracing", lambda: False)
    monkeypatch.setattr(runtime_metrics.tracemalloc, "start", lambda frames: tracing_started.append(frames))

    runtime_metrics.configure_memory_tracing()

    assert tracing_started == [1]


def test_render_memory_metrics_reports_traced_python_memory(monkeypatch) -> None:
    monkeypatch.setattr(runtime_metrics.tracemalloc, "is_tracing", lambda: True)
    monkeypatch.setattr(runtime_metrics.tracemalloc, "get_traced_memory", lambda: (1234, 5678))

    lines = runtime_metrics.render_memory_metrics()

    assert "newshash_python_tracemalloc_enabled 1" in lines
    assert "newshash_python_traced_memory_bytes 1234" in lines
    assert "newshash_python_traced_memory_peak_bytes 5678" in lines
