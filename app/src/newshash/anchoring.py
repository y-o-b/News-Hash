from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from newshash.main_types import AnchorableResult
from newshash.settings import SourceConfig

OTS_TIMEOUT_SECONDS = 15
AnchorStatus = Literal["no_anchor", "no_ots", "pending", "complete"]


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "source"


class OpenTimestampsAnchor:
    """Erzeugt tägliche OpenTimestamps-Proofs für Quellen-Hash-Manifeste."""

    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    def proof_path(self, source: SourceConfig, anchor_date: date | None = None) -> Path:
        """Gib den erwarteten Proof-Pfad für eine Quelle und einen UTC-Tag zurück."""

        day = anchor_date or datetime.now(UTC).date()
        return self.storage_root / "anchors" / day.isoformat() / f"{_safe_name(source.storage_name)}.txt.ots"

    def manifest_path(self, source: SourceConfig, anchor_date: date | None = None) -> Path:
        """Gib den erwarteten Manifest-Pfad für eine Quelle und einen UTC-Tag zurück."""

        day = anchor_date or datetime.now(UTC).date()
        return self.storage_root / "anchors" / day.isoformat() / f"{_safe_name(source.storage_name)}.txt"

    def anchor_source(self, source: SourceConfig, result: AnchorableResult, anchor_date: date | None = None) -> Path:
        """Stemple die beiden aktuellen Hash-Ketten einer Quelle höchstens einmal pro UTC-Tag."""

        day = anchor_date or datetime.now(UTC).date()
        anchor_dir = self.storage_root / "anchors" / day.isoformat()
        manifest = self.manifest_path(source, day)
        proof = self.proof_path(source, day)
        if proof.exists():
            return proof

        anchor_dir.mkdir(parents=True, exist_ok=True)
        content = {
            "date": day.isoformat(),
            "source": source.name,
            "storage_name": source.storage_name,
            "latest_hash_jsonl": result.latest_hash_jsonl,
            "latest_hash_sqlite": result.latest_hash_sqlite,
        }
        manifest.write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        subprocess.run(
            ["ots", "stamp", str(manifest)],
            check=True,
            capture_output=True,
            text=True,
            timeout=OTS_TIMEOUT_SECONDS,
        )
        return proof

    def check_status(self, source: SourceConfig, anchor_date: date | None = None) -> AnchorStatus:
        """Prüfe den lokalen Proof und aktualisiere ausstehende Attestations."""

        day = anchor_date or datetime.now(UTC).date()
        anchor_dir = self.storage_root / "anchors" / day.isoformat()
        manifest = anchor_dir / f"{_safe_name(source.storage_name)}.txt"
        proof = self.proof_path(source, day)
        if not manifest.exists():
            return "no_anchor"
        if not proof.exists():
            return "no_ots"

        try:
            upgrade = subprocess.run(
                ["ots", "upgrade", str(proof)],
                check=False,
                capture_output=True,
                text=True,
                timeout=OTS_TIMEOUT_SECONDS,
            )
            upgrade_output = f"{upgrade.stdout}\n{upgrade.stderr}"
            if "Success! Timestamp complete" in upgrade_output:
                return "complete"
            verification = subprocess.run(
                ["ots", "verify", str(proof)],
                check=False,
                capture_output=True,
                text=True,
                timeout=OTS_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "pending"

        output = f"{verification.stdout}\n{verification.stderr}"
        return "complete" if "Success!" in output and "Bitcoin block" in output else "pending"
