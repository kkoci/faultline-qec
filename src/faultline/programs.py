"""Built-in Gate 2 benchmark and an explicit adapter for user programs."""
from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
import sys
from guppylang import guppy
from guppylang.std import quantum as q
from guppylang.std.platform import output
from guppyft.code.steane.encode import SteaneBuilder, QECPolicy, QECStyle


@guppy
def gate2_algorithm() -> None:
    data = q.qubit()
    q.x(data)
    output("logical", q.measure(data).read())


@guppy
def gate2_x_algorithm() -> None:
    data = q.qubit()
    q.h(data)
    q.x(data)
    q.h(data)
    output("logical", q.measure(data).read())


@dataclass
class Program:
    """Adapter contract: fully encoded package plus explicit oracle assumptions.

    `oracle_boundaries` certify a point where ideal code-capacity recovery is
    valid with no subsequent logical propagation (or propagation commuting up
    to global phase, as for the Gate 2 transversal X).
    """
    package: object
    name: str = "custom"
    n_qubits: int = 32
    data_qubits: tuple[int, ...] = tuple(range(7))
    output_tag: str = "logical"
    logical_state: str = "1"
    readout_basis: str = "Z"
    labels: dict[int, str] = field(default_factory=dict)
    oracle_boundaries: tuple[int, ...] = ()

    def __post_init__(self):
        if len(self.data_qubits) != 7 or len(set(self.data_qubits)) != 7:
            raise ValueError("Program must identify seven distinct physical data IDs")
        if any(type(q) is not int or not 0 <= q < self.n_qubits for q in self.data_qubits):
            raise ValueError("Data IDs must be in range of n_qubits")
        if self.logical_state not in ("0", "1", "+", "-") or self.readout_basis not in ("X", "Z"):
            raise ValueError("Invalid oracle state or readout basis")


def gate2(basis: str = "Z") -> Program:
    if basis not in ("Z", "X"):
        raise ValueError("Gate 2 readout basis must be Z or X")
    policy = QECPolicy(style=QECStyle.Reichardt, threshold=1)
    policy.costs.x = 1.0
    arch = SteaneBuilder().with_qec_policy(policy).build(n_blocks=1)
    if basis == "X":
        return Program(arch.encode(gate2_x_algorithm.compile()), name="gate2-x",
                       logical_state="+", readout_basis="X",
                       labels={84: "prepared logical +; before transversal X + Reichardt QEC"},
                       oracle_boundaries=(84,))
    return Program(arch.encode(gate2_algorithm.compile()), name="gate2",
                   labels={70: "prepared block 0; flag measured; before transversal X + Reichardt QEC"},
                   oracle_boundaries=(70,))


def load_program(value: str) -> Program:
    if value == "gate2":
        return gate2()
    if value == "gate2-x":
        return gate2("X")
    filename, separator, factory = value.partition(":")
    path = Path(filename).resolve()
    if not path.is_file():
        raise ValueError("Program must be 'gate2', 'gate2-x' or an existing Python file[:factory]")
    name = "_faultline_program_" + str(abs(hash(str(path))))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    result = getattr(module, factory if separator else "build_program")()
    if not isinstance(result, Program):
        raise ValueError("Program factory must return faultline.programs.Program")
    return result
