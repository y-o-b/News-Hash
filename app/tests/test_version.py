from __future__ import annotations

import tomllib
from pathlib import Path

from newshash import __version__


def test_version_matches_pyproject() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["version"] == __version__
