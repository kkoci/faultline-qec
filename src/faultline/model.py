"""Public Python configuration for the deterministic native error model."""
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from selene_core import ErrorModel
from .build import build_native

Fault = tuple[int, int, str]


@dataclass(init=False)
class PauliScheduleErrorModel(ErrorModel):
    schedule: Sequence[Fault] = ()
    audit_path: str | Path | None = None

    def __init__(self, schedule: Sequence[Fault] = (), *, audit_path: str | Path | None = None,
                 random_seed: int | None = None):
        super().__init__(random_seed=random_seed)
        self.schedule = schedule
        self.audit_path = audit_path
        self.__post_init__()

    def __post_init__(self):
        normalized = []
        for item in self.schedule:
            if len(item) != 3:
                raise ValueError("Each fault must be (positive op ordinal, physical qubit, X/Y/Z)")
            ordinal, qubit, pauli = item
            if type(ordinal) is not int or ordinal < 1 or ordinal >= 2**64:
                raise ValueError("Op ordinal must be a positive uint64 integer")
            if type(qubit) is not int or qubit < 0 or qubit >= 2**64:
                raise ValueError("Physical qubit must be a nonnegative uint64 integer")
            if pauli not in ("X", "Y", "Z"):
                raise ValueError("Pauli must be X, Y or Z")
            normalized.append((ordinal, qubit, pauli))
        # Stable ordering preserves sequential faults at the same boundary.
        self.schedule = tuple(sorted(normalized, key=lambda f: f[0]))
        if self.audit_path is not None:
            self.audit_path = Path(self.audit_path).resolve()
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def library_file(self) -> Path:
        return build_native()

    def get_init_args(self) -> list[str]:
        return [str(self.audit_path) if self.audit_path is not None else ""] + [
            str(value) for fault in self.schedule for value in fault
        ]
