#!/usr/bin/env bash
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
TASK_SMOKE_DIR=$(mktemp -d /tmp/faultline-qec-wheel.XXXXXXXX)
case "$TASK_SMOKE_DIR" in /tmp/faultline-qec-wheel.*) ;; *) exit 1 ;; esac
trap 'rm -rf -- "$TASK_SMOKE_DIR"' EXIT
TASK_SMOKE_PY="$TASK_SMOKE_DIR/venv/bin/python"
TASK_CONSTRAINTS="$TASK_SMOKE_DIR/constraints.txt"
uv venv --python 3.12.16 "$TASK_SMOKE_DIR/venv"
"$TASK_SMOKE_PY" - <<'PY' > "$TASK_CONSTRAINTS"
import tomllib
from pathlib import Path
pins=tomllib.loads(Path('pyproject.toml').read_text())['tool']['uv']['constraint-dependencies']
print('\n'.join(pins))
PY
uv pip install --python "$TASK_SMOKE_PY" \
    --constraint "$TASK_CONSTRAINTS" dist/faultline_qec-0.1.0-py3-none-any.whl
export XDG_CACHE_HOME="$TASK_SMOKE_DIR/cache"
cd "$HOME"
"$TASK_SMOKE_PY" - <<'PY'
import faultline
from faultline.build import build_native
from faultline.programs import gate2
from faultline.runner import Runner
print('Installed wheel:',faultline.__file__)
assert '/site-packages/' in faultline.__file__
print('Fresh native build:',build_native())
runner=Runner(gate2())
for name,schedule,expected in [('baseline',[],1),('single',[(70,0,'X')],1),('double',[(70,0,'X'),(70,1,'X')],0)]:
    counts=runner.run(schedule,shots=10)
    print(name,dict(counts))
    assert counts=={expected:10}
print('PASS: installed wheel builds native plugin and reproduces Gate 2.')
PY
