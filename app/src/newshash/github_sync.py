from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from newshash.anchoring import OpenTimestampsAnchor
from newshash.settings import SourceConfig

GITHUB_TIMEOUT_SECONDS = 30


def read_credential(name: str, credentials_path: Path = Path("data/credentials.env")) -> str | None:
    """Lese einen Credential-Wert ohne ihn zu protokollieren."""

    if not credentials_path.exists():
        return None
    for line in credentials_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip().strip('"').strip("'") or None
    return None


def read_github_token(credentials_path: Path = Path("data/credentials.env")) -> str | None:
    """Lese den GitHub-Token ohne ihn zu protokollieren."""

    return read_credential("GITHUB_TOKEN", credentials_path)


class GitHubAnchorPublisher:
    """Veröffentlicht Anchor-Dateien im konfigurierten GitHub-Repository."""

    def __init__(self, storage_root: Path, credentials_path: Path = Path("data/credentials.env")) -> None:
        self.storage_root = storage_root
        self.credentials_path = credentials_path

    def publish_source(self, source: SourceConfig, anchor_date: date | None = None) -> list[str]:
        """Lade Manifest und Proof einer Quelle nach GitHub hoch."""

        token = read_github_token(self.credentials_path)
        repository = read_credential("GITHUB_REPOSITORY", self.credentials_path)
        if not token or not repository:
            return []
        day = anchor_date or datetime.now(UTC).date()
        anchor = OpenTimestampsAnchor(self.storage_root)
        files = [anchor.manifest_path(source, day), anchor.proof_path(source, day)]
        api_url = f"https://api.github.com/repos/{repository}/contents"
        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
        urls: list[str] = []
        for local_path in files:
            if not local_path.is_file():
                continue
            repository_path = f"anchors/{day.isoformat()}/{local_path.name}"
            endpoint = f"{api_url}/{repository_path}"
            existing = requests.get(endpoint, headers=headers, params={"ref": "main"}, timeout=GITHUB_TIMEOUT_SECONDS)
            existing_data = existing.json() if existing.status_code == 200 else {}
            sha: str | None = existing_data.get("sha")
            if existing.status_code not in {200, 404}:
                existing.raise_for_status()
            local_bytes = local_path.read_bytes()
            existing_content = existing_data.get("content")
            if isinstance(existing_content, str):
                remote_bytes = base64.b64decode("".join(existing_content.split()))
                if remote_bytes == local_bytes:
                    urls.append(existing_data.get("html_url", endpoint))
                    continue
            payload: dict[str, Any] = {
                "message": f"Add News-Hash anchor {day.isoformat()} {source.storage_name}",
                "content": base64.b64encode(local_bytes).decode("ascii"),
                "branch": "main",
            }
            if sha:
                payload["sha"] = sha
            response = requests.put(endpoint, headers=headers, json=payload, timeout=GITHUB_TIMEOUT_SECONDS)
            response.raise_for_status()
            urls.append(response.json().get("content", {}).get("html_url", endpoint))
        return urls
