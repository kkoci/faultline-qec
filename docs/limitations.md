# Limitations

- **Code-capacity only.** Faults are placed before otherwise ideal syndrome
  extraction. These results do not establish arbitrary circuit-level fault
  tolerance or hardware error rates.
- **Reichardt lookup decoder.** The supplied primitive assumes no faults during
  syndrome extraction. The independent oracle is appropriate only at declared
  compatible recovery boundaries.
- **IDs and ordinals belong to the compiled program.** Allocation, runtime
  control flow and toolchain changes can change physical IDs and operation
  ordinals. Inspect labels and raw audits before reusing a schedule. Arbitrary
  adapters must assert their own data mapping and oracle compatibility.
- **Linux only, including WSL.** Native simulation is supported on Linux with
  the pinned dependencies. The documentation build is independent of that stack.
- **Pauli experiments, not a general noise model.** There is no leakage model;
  leaked measurements are treated as ordinary binary measurements. Custom
  operations are ignored as in the bundled ideal model and marked `CUSTOM_NOOP`.
  Complementary readouts identify deterministic residual Paulis under the
  stated assumptions, not arbitrary quantum channels.
- **Serial runs.** Do not share an audit path across concurrent experiments.

The [concepts](concepts.md) explain observable visibility, and the
[validation record](validation.md) describes the actual checks performed.
