#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/app"
exec uv run newshash-validate --settings data/settings.toml --data-dir data
