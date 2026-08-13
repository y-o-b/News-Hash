from __future__ import annotations

from datetime import date
from pathlib import Path

from newshash.anchoring import OpenTimestampsAnchor
from newshash.settings import SourceConfig


class Result:
    latest_hash_jsonl = "a" * 64
    latest_hash_sqlite = "b" * 64


def test_anchor_source_writes_manifest_and_calls_ots(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        Path(f"{command[-1]}.ots").write_bytes(b"proof")

    monkeypatch.setattr("newshash.anchoring.subprocess.run", fake_run)
    source = SourceConfig("ZDF", "https://example.invalid/feed", "zdf", 300)

    proof = OpenTimestampsAnchor(tmp_path).anchor_source(source, Result(), date(2026, 8, 11))

    manifest = tmp_path / "anchors/2026-08-11/zdf.txt"
    assert proof == Path(f"{manifest}.ots")
    assert manifest.exists()
    assert "latest_hash_jsonl" in manifest.read_text(encoding="utf-8")
    assert calls == [["ots", "stamp", str(manifest)]]


def test_anchor_source_does_not_stamp_same_day_twice(tmp_path, monkeypatch) -> None:
    calls = 0

    def fake_run(command, **kwargs):
        nonlocal calls
        calls += 1
        Path(f"{command[-1]}.ots").write_bytes(b"proof")

    monkeypatch.setattr("newshash.anchoring.subprocess.run", fake_run)
    source = SourceConfig("ZDF", "https://example.invalid/feed", "zdf", 300)
    anchor = OpenTimestampsAnchor(tmp_path)

    anchor.anchor_source(source, Result(), date(2026, 8, 11))
    anchor.anchor_source(source, Result(), date(2026, 8, 11))

    assert calls == 1


def test_check_status_accepts_complete_upgrade_without_local_bitcoin_node(tmp_path, monkeypatch) -> None:
    source = SourceConfig("ZDF", "https://example.invalid/feed", "zdf", 300)
    anchor = OpenTimestampsAnchor(tmp_path)
    proof = anchor.proof_path(source, date(2026, 8, 11))
    proof.parent.mkdir(parents=True)
    proof.with_suffix("").write_text("manifest\n", encoding="utf-8")
    proof.write_bytes(b"proof")

    class Completed:
        returncode = 0
        stdout = "Success! Timestamp complete"
        stderr = ""

    monkeypatch.setattr("newshash.anchoring.subprocess.run", lambda *args, **kwargs: Completed())

    assert anchor.check_status(source, date(2026, 8, 11)) == "complete"
