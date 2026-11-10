#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/faultline-qec}"
uv build --wheel
uv run --locked python - <<'PY'
import zipfile
from pathlib import Path
wheel=next(Path('dist').glob('*.whl'))
with zipfile.ZipFile(wheel) as archive:
    assert 'faultline/native/schedule.c' in archive.namelist()
    assert any(name.endswith('.dist-info/licenses/LICENSE') for name in archive.namelist())
    metadata=archive.read('faultline_qec-0.1.0.dist-info/METADATA').decode()
    assert 'License-Expression: Apache-2.0' in metadata
    assert 'Author: Khrystian Koci' in metadata
    print('Wheel includes native source:',wheel)
    print('Wheel includes Apache-2.0 LICENSE and author metadata.')
PY
