#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/faultline-qec}"
uv sync --locked --python 3.12.16
uv run faultline build-native
mkdir -p artifacts
uv run faultline boundaries gate2 --audit artifacts/boundaries.jsonl > artifacts/boundaries.txt
