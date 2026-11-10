"""Run from the project root: uv run python examples/gate2_regression.py."""
from pathlib import Path
from faultline.oracle import predict
from faultline.programs import gate2
from faultline.runner import Runner

runner=Runner(gate2())
for name,faults,expected in [('baseline',[],1),('single_X',[(0,'X')],1),('double_X',[(0,'X'),(1,'X')],0)]:
    schedule=[(70,q,p) for q,p in faults]
    prediction=predict(faults)
    counts=runner.run(schedule,shots=1000,audit_path=Path(f'artifacts/regression/{name}.jsonl'))
    print(f'{name}: {counts}; oracle={prediction.probabilities}; residual={prediction.logical_pauli}',flush=True)
    assert counts=={expected:1000}
print('PASS: Gate 2 reproduced with the native error-model ABI.',flush=True)
