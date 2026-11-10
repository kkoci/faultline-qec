#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/faultline-qec}"
uv run --locked pytest -q
uv run --locked faultline sweep gate2 --boundary 70 --shots 1 --output artifacts/sweep
uv run --locked faultline sweep gate2 --boundary 70 --both-bases --shots 1 --output artifacts/both-bases
