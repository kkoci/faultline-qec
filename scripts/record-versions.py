import json
import platform
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

root=Path(__file__).resolve().parents[1]
constraints=tomllib.loads((root/'pyproject.toml').read_text())['tool']['uv']['constraint-dependencies']
pins={}
for line in constraints:
    name,expected=line.split('==')
    actual=version(name)
    assert actual==expected,(name,actual,expected)
    pins[name]=actual
print(json.dumps({'python':sys.version,'platform':platform.platform(),
                  'faultline-qec':version('faultline-qec'),'pytest':version('pytest'),
                  'gate2_pins_verified':pins},indent=2))
