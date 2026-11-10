# Faultline

Faultline injects deterministic physical X, Y and Z faults into Steane-encoded
Guppy programs running on Selene. Its native plugin implements Selene's public
error-model ABI, forwards the original operations to the simulator, and inserts
scheduled Pauli gates at audited physical-operation boundaries. Experiments run
locally on Linux or WSL without a cloud account or quantum hardware.

**A Z-only readout hides 63 of 147 logical errors.** In the Gate 2 benchmark,
pairing that experiment with an X-basis run makes all 147 visible, checked
against an independent NumPy oracle: zero mismatches and zero logical errors
invisible in both bases.

The sweep covers 21 single-qubit faults and 189 two-qubit faults in each basis.
All singles are corrected; 42 pairs are corrected and 147 retain a logical error.
These are deterministic code-capacity experiments with otherwise ideal recovery.

Start with the [quickstart](quickstart.md), read the [concepts](concepts.md),
or inspect the [results and embedded coverage table](results.md).
The [limitations](limitations.md) explain the scope of the finding, and the
[validation record](validation.md) documents the commands and observations.
