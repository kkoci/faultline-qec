"""Independent NumPy Steane code-capacity oracle; no simulator/decoder calls."""
from dataclasses import asdict, dataclass
from typing import Iterable
import numpy as np

# Columns uniquely identify data-qubit single-error syndromes.
H = np.array([[1,1,1,1,0,0,0], [0,1,1,0,1,1,0], [0,0,1,1,0,1,1]], dtype=int)


@dataclass(frozen=True)
class Prediction:
    x_syndrome: tuple[int, ...]
    z_syndrome: tuple[int, ...]
    x_correction: int | None
    z_correction: int | None
    logical_pauli: str
    probabilities: tuple[float, float]
    state_fidelity: float

    def to_dict(self):
        return asdict(self)


def codewords() -> tuple[np.ndarray, np.ndarray]:
    zero = np.zeros(128, dtype=complex)
    for selector in range(8):
        bits = sum(((selector >> k) & 1) * H[k] for k in range(3)) % 2
        index = sum(int(b) << (6-i) for i, b in enumerate(bits))
        zero[index] = 1 / np.sqrt(8)
    return zero, zero[::-1].copy()


def apply_pauli(state: np.ndarray, qubit: int, pauli: str) -> np.ndarray:
    if type(qubit) is not int or not 0 <= qubit < 7 or pauli not in ("X", "Y", "Z"):
        raise ValueError("Expected a data index 0..6 and Pauli X/Y/Z")
    mask = 1 << (6-qubit)
    indices = np.arange(128)
    if pauli == "X":
        return state[indices ^ mask]
    if pauli == "Z":
        return state * np.where(indices & mask, -1, 1)
    # Y|0> = i|1>, Y|1> = -i|0>.
    return state[indices ^ mask] * np.where(indices & mask, 1j, -1j)


def predict(faults: Iterable[tuple[int, str]], *, logical_state: str = "1", basis: str = "Z") -> Prediction:
    """Ideal CSS syndrome correction, including both X and Z components.

    Fault indices are within the logical block, not runtime physical IDs.
    `logical_state` is the ideal state at the recovery boundary (0,1,+,-).
    """
    if logical_state not in ("0", "1", "+", "-") or basis not in ("X", "Z"):
        raise ValueError("State must be 0/1/+/- and readout basis X/Z")
    zero, one = codewords()
    states = {"0": zero, "1": one, "+": (zero+one)/np.sqrt(2), "-": (zero-one)/np.sqrt(2)}
    ideal = states[logical_state]
    state = ideal.copy()
    x = np.zeros(7, dtype=int)
    z = np.zeros(7, dtype=int)
    for q, p in faults:
        state = apply_pauli(state, q, p)
        x[q] ^= p in ("X", "Y")
        z[q] ^= p in ("Z", "Y")
    sx, sz = H @ x % 2, H @ z % 2
    def correction(syndrome):
        return next((q for q in range(7) if np.array_equal(H[:, q], syndrome)), None)
    cx, cz = correction(sx), correction(sz)
    if cx is not None:
        state = apply_pauli(state, cx, "X")
        x[cx] ^= 1
    if cz is not None:
        state = apply_pauli(state, cz, "Z")
        z[cz] ^= 1
    lx, lz = int(sum(x) % 2), int(sum(z) % 2)
    logical_pauli = {(0,0): "I", (1,0): "X", (0,1): "Z", (1,1): "Y"}[lx,lz]
    readout_states = (zero, one) if basis == "Z" else (states["+"], states["-"])
    probs = tuple(round(float(abs(v.conj() @ state)**2), 12) for v in readout_states)
    fidelity = round(float(abs(ideal.conj() @ state)**2), 12)
    return Prediction(tuple(map(int, sx)), tuple(map(int, sz)), cx, cz, logical_pauli, probs, fidelity)


def predict_both_bases(faults: Iterable[tuple[int, str]]) -> dict[str, Prediction]:
    """Complementary Gate 2 probes: |1_L>/Z and |+_L>/X after logical X.

    Both probes see the same Pauli recovery channel. A residual X flips Z,
    a residual Z flips X, and a residual Y flips both.
    """
    faults = tuple(faults)
    return {"Z": predict(faults, logical_state="1", basis="Z"),
            "X": predict(faults, logical_state="+", basis="X")}
