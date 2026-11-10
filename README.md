# faultline-qec v0.1

[Docs](https://kkoci.github.io/faultline-qec/)

Deterministic physical Pauli fault injection for Steane-encoded Guppy programs running on Selene. Linux only, including WSL. No cloud account or hardware access is needed.

The native component implements **Selene's error-model ABI**, including `handle_operations_fn`. It extracts original runtime operations, executes them on the supplied simulator handle, returns actual measurement results, and inserts scheduled physical X, Y or Z gates. It does not replace the simulator, change measurement results or patch Guppy FT.

## Install and run

Use this directory as the project/repository root. Python and package versions are pinned in `.python-version`, `pyproject.toml` and `uv.lock`.

```sh
uv sync --locked --python 3.12.16
uv run --locked faultline build-native
uv run --locked faultline boundaries gate2 --audit artifacts/boundaries.jsonl
uv run --locked faultline boundaries gate2-x --audit artifacts/x-boundaries.jsonl
uv run --locked faultline sweep gate2 --boundary 70 --both-bases --shots 1 --output artifacts/both-bases
uv run --locked pytest -q
```

`ziglang==0.16.0` comes from PyPI. The first native build invokes `python -m ziglang cc` against the public headers shipped in `selene-core==0.3.3`. There is no system C compiler or Rust toolchain requirement. The shared object is cached under `$XDG_CACHE_HOME/faultline-qec` (or `~/.cache/faultline-qec`), keyed by source, headers, architecture and Zig version. The C source is included in the Python wheel, so installed wheels can build the plugin too.

For a WSL checkout on `/mnt/c`, installing the virtual environment on the Linux filesystem can avoid slow Windows file copying:

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/faultline-qec"
uv sync --locked
```

This scaffold pins Guppy FT 0.6.1, Guppy 1.2.0, Selene 0.3.7, Selene core 0.3.3, NumPy 2.5.4, Python 3.12.16, and the complete Gate 2 dependency set. Development tests add pytest 9.0.2. The Linux GitHub Actions workflow uses uv 0.13.7 and the lockfile; it is supplied for when this directory is placed at a repository root.

## Schedule API

```python
from faultline import PauliScheduleErrorModel

model = PauliScheduleErrorModel(
    schedule=[(70, 0, "X"), (70, 1, "Y"), (90, 2, "Z")],
    audit_path="artifacts/faults.jsonl",
)
# Use an existing Guppy EmulatorInstance:
# emulator.with_error_model(model).with_shots(1000).run()
```

Each tuple is **(original physical op ordinal, physical qubit ID, Pauli)**. Ordinals are one-based; faults run immediately **after** that operation completes. A schedule is repeated from the beginning on every shot. Multiple entries at one boundary run in their supplied order. Schedules at different ordinals are sorted stably. Duplicate X/X, Y/Y or Z/Z faults on one qubit cancel up to global phase.

Resets, rotations, measurements and custom operations increment the ordinal. Batch-time metadata and injected gates do not. This avoids changing later fault positions merely because an earlier fault added a gate. The runtime stream, including control-flow-dependent correction gates, can still change when faults change measurement results. Use `boundaries` for a baseline and inspect each fault run's audit. v0.1 ignores custom operations as the bundled ideal model does, labels them `CUSTOM_NOOP`, and models leaked measurements as ordinary 0/1 measurements; it is not a leakage model.

Invalid schedules and physical IDs fail. A schedule entry whose ordinal is never reached causes a shot-end error rather than a successful no-fault run. Physical ID range checking cannot establish that an ID still refers to a live data qubit at a boundary; that is an adapter/user responsibility. Runs are serial. Do not share an audit path between concurrent runs.

The ABI and source references are [Selene error-model descriptor](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-core/c/include/selene/error_model.h), [runtime extraction callbacks](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-core/c/include/selene/runtime.h), and [the ideal model's semantics](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-ext/error-models/ideal/rust/lib.rs).

## Find a physical boundary

`faultline boundaries <program>` runs exactly one shot with an empty schedule and the native audit enabled. It prints the actual physical operation order, ordinals, parameters, measurement results, data/ancilla roles and adapter-supplied boundary labels. JSONL records also mark shot start/end and injection calls. Unlike a topologically sorted circuit rendering, this audit is emitted synchronously while operations execute.

The built-in `gate2` benchmark is the Gate 2 experiment: prepare |0_L>, apply transversal logical X, perform one active Reichardt QEC cycle, then measure logical Z. QEC is selected with `QECPolicy(style=QECStyle.Reichardt, threshold=1)` and `costs.x=1`. Physical IDs 0–6 are its one data block. At original operation **70**, the preparation flag on physical ID 7 is measured. Faults placed after op 70 precede the seven transversal X gates and the QEC circuit. The ideal logical output is **1**. X/Y/Z commute through that transversal X up to an irrelevant global phase, allowing the oracle to place them on |1_L> just before recovery.

The complementary `gate2-x` benchmark prepares logical |+> with a transversal H, performs the **same logical X and one active Reichardt QEC cycle**, and measures in the X basis (transversal H followed by Z measurement). Its ideal output is **0**. Its matching fault boundary is after op **84**, after all seven preparation Hadamards and before the logical X. Injecting at op 70 in this variant would put the faults before |+> preparation and would test a different channel.

Only boundary 70 (`gate2`) or 84 (`gate2-x`) is declared oracle-compatible for its respective benchmark. Both use the same physical data IDs 0-6. The runner verifies the preparation flag, the following transversal X layer and, for `gate2-x`, the complete preparation H layer. Other ordinals remain valid for direct schedule experiments, but a code-capacity oracle is generally wrong for a fault inside syndrome extraction or before encoding has completed.

```sh
# Individual X-basis sweep, if desired:
faultline sweep gate2-x --boundary 84 --output artifacts/x-only
# Paired report: automatically selects matching Z/X boundaries 70/84:
faultline sweep gate2 --boundary 70 --both-bases --output artifacts/both-bases
```

To use another encoded program, supply a Python file with a factory returning `faultline.programs.Program`:

```python
from faultline.programs import Program

def build_program():
    # Compile and encode your own algorithm here; do not return a raw algorithm.
    return Program(
        package=encoded_package,
        name="my-memory",
        n_qubits=32,
        data_qubits=(0, 1, 2, 3, 4, 5, 6),
        output_tag="logical",
        logical_state="1",  # 0, 1, + or - at the equivalent recovery boundary
        readout_basis="Z",  # X or Z
        labels={70: "verified data-preparation boundary"},
        oracle_boundaries=(70,),
    )
```

```sh
faultline boundaries my_program.py
faultline sweep my_program.py:build_program --boundary 70
```

Importing an adapter executes its Python code. The adapter explicitly asserts data-ID mapping, deterministic readout and code-capacity compatibility. The tool cannot infer these assumptions for an arbitrary program, propagate faults through arbitrary subsequent logical gates, or automatically prove a label correct.

## Oracle and coverage

The independent NumPy oracle constructs the 128-amplitude Steane codewords using the binary rows `1111000`, `0110110`, `0011011`. It applies full X/Y/Z matrices, decodes X and Z syndrome components independently with minimum-weight corrections, and calculates logical readout probabilities and state fidelity. It also reports the residual logical Pauli I/X/Y/Z. `predict_both_bases` evaluates each fault pattern on |1_L> with Z readout and |+_L> with X readout, after the common logical X. It does not call Guppy FT's decoder, Selene, Stim or TKET for the reference calculation. The code convention comes from [Guppy FT's pinned Steane definition](https://github.com/Quantinuum/guppyft/blob/v0.6.1/src/guppyft/code/steane/primitives.py).

`sweep` enumerates:

- All 21 single faults: seven data qubits × X/Y/Z.
- All 189 pairs: 21 unordered pairs of distinct data qubits × nine Pauli combinations.

Each case puts its faults at the selected boundary, runs the simulator, and compares the measured binary output with the oracle. Defaults are one shot per deterministic case and seed 42. Baseline disagreement, invalid adapters and execution failures stop with a nonzero exit status. Completed oracle mismatches are retained and make the CLI exit 1. Configuration/execution errors exit 2.

`coverage.json` contains all cases, schedules, observed counts, oracle predictions and audit locations; `coverage.md` contains the aggregate table and every case. Categories are:

- `corrected`: measured logical outcome matches the ideal baseline and oracle.
- `logical_flip`: measured logical outcome flips and agrees with the oracle.
- `mismatch`: observed counts disagree with the oracle.

**Single-basis categories describe the chosen observable.** For Gate 2's Z readout, a residual logical Z is invisible and may be listed as `corrected` even though it is not full error-channel correction. Such rows explicitly set `unobserved_logical_error=true`, and retain `oracle.logical_pauli`. In the X readout, residual logical X is similarly invisible. A deterministic logical Z on |1_L> has state fidelity one because it changes only global phase.

Expected Gate 2 coverage is 21/21 corrected singles; among 189 pairs, 105 unchanged outcomes and 84 flips, with 63 of the unchanged outcomes carrying an oracle-predicted residual logical Z. Among pairs the full residual-Pauli distribution is I:42, X:63, Y:21, Z:63. This table must not be described as 105 fully corrected two-qubit errors.

With `--both-bases`, the CLI executes all 210 cases in **each** basis and writes individual reports/audits in `z/` and `x/`. The combined `coverage-both.json` and `coverage-both.md` report, per case, the Z result, X result, oracle residual logical Pauli, observed residual Pauli and mismatch flag. Expected readouts relative to their respective baselines are:

| Residual logical Pauli | Z result (baseline 1) | X result (baseline 0) | Cases |
|---|---:|---:|---:|
| I | 1 | 0 | 63 |
| X | 0 | 0 | 63 |
| Y | 0 | 1 | 21 |
| Z | 1 | 1 | 63 |

The paired category `corrected` requires agreement in both bases and oracle residual I; `logical_flip` requires a matching nonidentity residual Pauli visible in at least one basis. Any disagreeing or nondeterministic readout is a mismatch. Every oracle-predicted logical error must be visible in at least one basis, otherwise the command exits nonzero. This complementary readout identifies the residual Pauli under the deterministic Pauli/code-capacity assumptions; it is not general quantum process tomography.

Observed paired sweep: **63 corrected cases, 147 visible logical errors, zero mismatches and zero errors invisible in both bases**. Both single-basis reports have 126 unchanged outcomes and 84 flips. All 21 singles are corrected; among pairs, 42 are corrected and 147 retain a logical error. See [the committed sample coverage table](docs/sample-coverage.md). Raw generated reports and audits remain under the ignored `artifacts/` directory when reproduced locally.

## Validation and limits

The tests reproduce Gate 2 exactly: baseline and X on data ID 0 each give logical 1 in all 1,000 shots; X on IDs 0 and 1 gives logical 0 in all 1,000 shots. Audits verify every-shot injections and the actual active correction (X on ID 0 or ID 4) before readout, and match the original first-shot data words. The X benchmark is checked for logical-plus preparation, one active six-syndrome QEC cycle, deterministic baseline 0 and sensitivity to Z/Z and Y/Y pairs. All 210 native cases run in both bases; tests require every predicted nonidentity logical Pauli to be observed and deliberately corrupt a phase-sensitive result to ensure it is reported as a mismatch.

This checks **code-capacity** errors placed before otherwise ideal syndrome extraction. The supplied Reichardt primitive uses a lookup decoder that assumes no faults during the syndrome-extraction circuit. It does not establish arbitrary circuit-level fault tolerance, estimate hardware error rates, characterize leakage or correlated noise, or validate arbitrary program adapters. Physical IDs and op ordinals are tied to the compiled program, allocation, runtime and pinned toolchain. See the labels and raw audit before carrying a schedule to another program/version.

See `VALIDATION.md` for the actual local versions, commands and outputs. No workflow has been submitted to GitHub by this scaffold operation.

## Development scripts and history

Run the helpers with Bash; they locate the project root themselves:

```sh
bash scripts/dev-setup.sh
bash scripts/validate-local.sh
bash scripts/package-check.sh
bash scripts/wheel-smoke.sh
uv run --locked python scripts/record-versions.py > artifacts/versions.json
```

The canonical dependency pins are in `pyproject.toml` and `uv.lock`.
`gate2-constraints.txt` is a redundant local experiment file, ignored by Git
and unnecessary for building, testing or running the helper scripts. The wheel
smoke test derives its temporary constraints from `pyproject.toml`.

The original [Gate 1 and Gate 2 feasibility reports](docs/feasibility/README.md)
document how the public API route was established. Historical raw logs, binaries,
source snapshots and downloaded notebooks are not part of this public project.

## Licence

Copyright 2026 Khrystian Koci. Licensed under [Apache-2.0](LICENSE).
See [upstream licence checks](docs/licensing.md) for the pinned Selene and
Guppy FT licence files.
