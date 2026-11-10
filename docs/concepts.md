# Concepts

## Pauli schedules

A schedule is a sequence of `(original physical op ordinal, physical qubit ID,
Pauli)` tuples. Each Pauli is X, Y or Z. For example:

```python
from faultline import PauliScheduleErrorModel

model = PauliScheduleErrorModel(
    schedule=[(70, 0, "X"), (70, 1, "Y")],
    audit_path="artifacts/faults.jsonl",
)
```

Faults execute immediately after the specified operation. The schedule restarts
on every shot. Entries at a shared boundary preserve their supplied order;
entries at different ordinals are sorted stably. Repeated identical Paulis on
one qubit cancel up to global phase.

## Op ordinals and boundaries

Ordinals are one-based and count original physical operations, including resets,
rotations, measurements and custom operations. Injected gates and batch-time
metadata do not increment them. Faults can change measurement results and later
control flow, so a baseline audit describes one execution path. An entry whose
ordinal is never reached fails at shot end.

`faultline boundaries` records the runtime operation stream synchronously,
including physical IDs, results, roles and adapter-supplied labels. Physical ID
range checks cannot prove an ID still names a live data qubit at a given boundary.

For `gate2`, boundary 70 follows the preparation flag measurement and precedes
the transversal logical X and one active Reichardt QEC cycle. For `gate2-x`,
boundary 84 also follows the seven preparation Hadamards. Injecting at 70 in
the X variant would test a different channel. These are the respective
adapter-declared oracle-compatible boundaries; arbitrary points inside recovery
are outside the oracle's model.

## Independent oracle

The NumPy oracle constructs the 128-amplitude Steane codewords from binary rows
`1111000`, `0110110` and `0011011`. It applies full Pauli matrices, computes X
and Z syndrome components independently, applies minimum-weight corrections,
and calculates logical probabilities, state fidelity and residual Pauli I/X/Y/Z.
It does not call Guppy FT's decoder, Selene, Stim or TKET for the reference
calculation. Its code convention matches the pinned Steane implementation.

The benchmark's logical X commutes with the injected Pauli faults up to global
phase. This lets the oracle place faults immediately before ideal recovery on
the corresponding logical state. The simulator's actual readouts are then
compared with those predictions.

## Why both bases?

The Z benchmark prepares logical zero, applies logical X and recovery, and
measures Z with ideal output 1. A residual logical Z leaves this readout
unchanged. The complementary benchmark prepares logical plus, applies the same
logical X and recovery, then measures X with ideal output 0. It detects the
phase errors hidden by the Z readout.

| Residual Pauli | Z result | X result | Cases |
|---|---:|---:|---:|
| I | 1 | 0 | 63 |
| X | 0 | 0 | 63 |
| Y | 0 | 1 | 21 |
| Z | 1 | 1 | 63 |

The 63 residual-Z cases are hidden in the Z-only report. Across the paired
experiments all 147 nonidentity residuals are visible. A single-basis
`corrected` category means the chosen observable agrees with its baseline;
it does not guarantee correction of the full logical channel. The paired
`corrected` category requires both readouts to agree with the oracle and a
residual I. This identification relies on deterministic Pauli/code-capacity
assumptions and is not general quantum process tomography.
