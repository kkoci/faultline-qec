"""Compile once, run fault schedules through the native error-model ABI."""
import json
import math
from pathlib import Path
from collections import Counter
from guppylang.emulator import EmulatorBuilder
from selene_sim.backends.bundled_simulators import Stim
from .model import PauliScheduleErrorModel
from .programs import Program


def read_audit(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Runner:
    def __init__(self, program: Program, *, seed: int = 42):
        self.program = program
        self.emulator = (EmulatorBuilder().build(program.package, n_qubits=program.n_qubits)
                         .with_simulator(Stim(random_seed=seed)))

    def run(self, schedule=(), *, shots: int = 1, audit_path: Path | None = None) -> Counter:
        if type(shots) is not int or shots < 1:
            raise ValueError("shots must be a positive integer")
        result = (self.emulator.with_error_model(PauliScheduleErrorModel(schedule=schedule, audit_path=audit_path))
                  .with_shots(shots).run().collated_counts())
        counts = Counter()
        for tags, count in result.items():
            values = [value for tag, value in tags if tag == self.program.output_tag]
            if len(values) != 1 or values[0] not in ("0", "1"):
                raise ValueError(f"Expected one binary {self.program.output_tag!r} output; got {tags}")
            counts[int(values[0])] += count
        if sum(counts.values()) != shots:
            raise RuntimeError(f"Expected {shots} successful shots, got {counts}")
        return counts

    def boundaries(self, path: Path) -> list[dict]:
        self.run(audit_path=path)
        operations = [e for e in read_audit(path) if e["event"] == "op"]
        for op in operations:
            roles = [f"data[{self.program.data_qubits.index(q)}]" if q in self.program.data_qubits else "ancilla/other" for q in op["qubits"]]
            op["label"] = self.program.labels.get(op["ordinal"], "")
            op["roles"] = roles
        # The pinned built-in boundary is tied to physical preparation, not just
        # an ordinal that happens to exist in an unrelated executable.
        if self.program.name in ("gate2", "gate2-x"):
            first_measure = next(op for op in operations if op["kind"] == "MEASURE")
            if (first_measure["ordinal"], first_measure["qubits"], first_measure["result"]) != (70, [7], 0):
                raise RuntimeError("Gate 2 physical boundary drifted; re-establish IDs/ordinals")
            boundary = 70 if self.program.name == "gate2" else 84
            layer = operations[boundary:boundary+7]
            if not all(op["kind"] == "RXY" and op["qubits"] == [q]
                       and math.isclose(op["theta"], math.pi) and math.isclose(op["phi"], 0)
                       for q, op in enumerate(layer)) or len(layer) != 7:
                raise RuntimeError("Gate 2 transversal X layer drifted")
            if self.program.name == "gate2-x":
                preparation = operations[70:84]
                for q in range(7):
                    rotation, phase = preparation[2*q:2*q+2]
                    if not (rotation["kind"] == "RXY" and phase["kind"] == "RZ"
                            and rotation["qubits"] == phase["qubits"] == [q]
                            and math.isclose(rotation["theta"], math.pi/2)
                            and math.isclose(rotation["phi"], -math.pi/2)
                            and math.isclose(phase["theta"], math.pi)):
                        raise RuntimeError("Gate 2 logical-plus preparation drifted")
        return operations
