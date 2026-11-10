> Historical report. See the [feasibility index](README.md) for scope and original-workspace references.

Gate 2: controlled physical faults — feasibility result
======================================================

**Achievable using a public native extension API.** A feasibility-only Selene simulator plugin injected a physical X on data qubit 0 of an automatically Steane-encoded block, immediately after its preparation flag measurement. Active QEC corrected it. Two physical X faults, on data qubits 0 and 1 at the same boundary, caused the decoder to apply X on data qubit 4 and changed the logical outcome. The independent seven-qubit NumPy reference agreed. No upstream modifications, installed-package patches, private Python methods, product code, or commits were used.

This is not an existing Python fault-scheduling feature. It requires compiling the small experimental C plugin used in the original workspace. It instruments the simulator boundary, rather than changing the Guppy algorithm or inserting a logical gate before encoding.

Environment and pins
--------------------

Same Linux installation and complete 43-package lock as Gate 1:

| Component | Exact version |
|---|---|
| OS | Ubuntu 26.04.1 LTS under WSL2, x86_64 |
| Kernel | 6.6.114.1-microsoft-standard-WSL2 |
| Python | CPython 3.12.16 |
| uv | 0.13.7 |
| Guppy FT | 0.6.1 |
| Guppy / Guppy internals | 1.2.0 / 1.2.0 |
| Selene | selene-sim 0.3.7 |
| Selene core | 0.3.3 |
| Selene HUGR QIS compiler | 0.5.1 |
| NumPy | 2.5.4 |
| C compiler | Zig 0.16.0, through installed ziglang 0.16.0 |

All transitive pins are in requirements.lock (`requirements.lock`). No additional Python package or system compiler was installed for Gate 2. The simulator descriptor API version is 257 (0x0101), from the installed public header.

Docs and source findings
------------------------

1. Selene explicitly supports third-party runtime, error-model and simulator plugins through its [public extensibility API](https://docs.quantinuum.com/selene/extensibility/index.html). Its [ErrorModel documentation](https://docs.quantinuum.com/selene/api/generated/selene_core.error_model.ErrorModel.html) describes adding X gates, modifying operations and accessing the underlying simulator. The Python base class configures a native shared library and initialization arguments; it does not provide a Python per-instruction callback.

2. The pinned Selene [error-model header](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-core/c/include/selene/error_model.h) exposes `handle_operations_fn` and a `SimulatorHandle` with per-qubit rotation operations. Thus a deterministic native error model can be implemented without a core API change. This route was inspected, not implemented in this experiment.

3. The pinned [simulator header](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-core/c/include/selene/simulator.h) exposes a descriptor/accessor ABI with `shot_start_fn`, `measure_fn`, `rxy_fn`, and `rz_fn`, using physical qubit IDs. The public Python [Simulator base class](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-core/python/selene_core/simulator.py) supplies `library_file` and `get_init_args`. **This is the route actually tested:** a simulator wrapper loads bundled Stim through its public descriptor, forwards operations, counts measurement calls per shot and calls Stim's public `rxy_fn(target, pi, 0)` for physical X. It also implements a Z option via `rz_fn(target, pi)`, but Z was not exercised. Noise normally belongs in an error model; this wrapper is test instrumentation at the simulator boundary.

4. Selene's pinned [bundled error-model exports](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-sim/python/selene_sim/backends/bundled_error_models.py) provide ideal, depolarizing and simple-leakage models. Inspection of their installed Python configuration classes found no `(instruction, qubit, Pauli)` schedule. Event hooks consume result-stream events; their [pinned interface](https://github.com/Quantinuum/selene/blob/selene-sim-v0.3.7/selene-sim/python/selene_sim/event_hooks/event_hook.py) supplies logging/event handling, not synchronous gate insertion.

5. The inspected Guppy FT [Steane builder](https://github.com/Quantinuum/guppyft/blob/v0.6.1/src/guppyft/code/steane/encode.py) provides QEC policy and state-factory configuration, with no dedicated physical fault-scheduling option. Its [logical API](https://github.com/Quantinuum/guppyft/blob/v0.6.1/src/guppyft/code/steane/logical.py) exposes logical operations and QEC cycles. Its [physical primitives](https://github.com/Quantinuum/guppyft/blob/v0.6.1/src/guppyft/code/steane/primitives.py) expose physical data arrays for architecture authors, Steane code definitions and syndrome correction. Those are another level at which to compose custom gadgets, but this experiment leaves the built-in encoding and primitives intact.

Source snapshots, immutable commit URLs and SHA256s are in gate2-source-manifest.log (`gate2-source-manifest.log`). Relevant release commits: Selene `3f907f2ea7764d6569637a62fa7107ab2b8ff6c8`; Guppy FT `394db78b7b44a81ae7658f404cbf2c3a4941e1c7`. Local installed Python source and shipped headers were read as well; implementation was built against the installed headers. Some online API prose describes older exported function names; the pinned descriptor header was authoritative for compilation.

Experiment and chosen physical boundary
---------------------------------------

`gate2_program.py` prepares one computational qubit, applies X, then measures it. `SteaneBuilder` automatically encodes it using `n_blocks=1`. `QECPolicy(style=QECStyle.Reichardt, threshold=1)` with `costs.x=1.0` inserts one active QEC cycle after the logical X. We use 32 available physical qubits; the observed circuit uses 10. The intended logical result is **1**. Each case uses the same encoded package, 1,000 shots, seed 42, and the default ideal error model.

The wrapper applies faults **immediately after the first physical measurement in each shot**. The native audit proves this is the preparation flag on physical qubit 7, with outcome zero. The already prepared data block occupies physical IDs 0–6. The next seven operations are the transversal logical X on IDs 0–6; syndrome extraction follows. Thus the faults occur after physical state preparation, before the algorithm's logical X and before the QEC cycle. X faults commute with that transversal X, so the reference can equivalently put them immediately before QEC on |1_L>.

The single case injects `X_0`; the double case injects `X_0 X_1` on two distinct data qubits of the same block. Applying X twice to one physical qubit would cancel and would not be a two-qubit error. Fault counts are reset each shot. Native logs confirm exactly 1,000 / 2,000 successful gate-injection calls across the respective cases. No measurement outcome is forcibly replaced, no shot is discarded, and no stochastic background noise is applied.

The first-shot audit includes the original physical operations, the additional fault gates, syndrome measurements and active corrections. `CircuitExtractor` records only the original requested circuit; it cannot see the extra calls made inside this simulator wrapper, so the native audit is the injection evidence.

Independent reference and correction evidence
---------------------------------------------

`gate2-run.py::reference` uses only NumPy and explicit seven-qubit vectors. It constructs |0_L> as the equal superposition over the span of three binary Steane generator rows, obtains |1_L> with transversal X, permutes amplitudes for the physical faults, calculates their syndrome, applies a minimum-weight single-X correction, and calculates overlaps with |0_L> and |1_L>. It calls no Guppy FT decoder, Selene, Stim or TKET implementation.

The parity-check rows are `1111000`, `0110110`, `0011011`, matching the specified code convention. For `X_0`, syndrome `100` identifies qubit 0, so the residual error is identity. For `X_0 X_1`, syndrome `010` identifies qubit 4; correction leaves `X_0 X_1 X_4`, a weight-three logical X representative. The reference predicts a deterministic logical flip, rather than merely a nonzero error probability.

Native first-shot audits independently show the actual QEC applying X on qubit 0 for the single fault and qubit 4 for the double fault, after the six syndrome measurements and before the seven data measurements. Final data words have zero syndrome in all cases; their parities are 1, 1 and 0. Thus active QEC restores the single-fault state to the intended codeword class, while the two-fault state ends in the wrong codeword class. Final measurement decoding is not doing the single-fault correction in these audited shots. This check is implemented in `gate2-validate-audits.py` and recorded in `gate2-audit-evidence.json`.

Commands
--------

From this workspace in WSL Ubuntu, after Gate 1 setup:

```sh
export PATH="$HOME/.local/bin:$PATH"
# Source survey and saved pinned source snapshots:
"$HOME/guppyft-feasibility/a/bin/python" gate2-source.py
"$HOME/guppyft-feasibility/a/bin/python" gate2-fetch-source.py > gate2-source-manifest.log

# Build experimental plugin and run environment A:
bash gate2-test.sh > gate2-output-a.log 2>&1

# Clear/recreate B, sync complete lock, rebuild plugin, run same cases:
bash gate2-repeat.sh > gate2-output-b.log 2>&1

# Check physical targets, active correction, raw final data syndrome/parity:
"$HOME/guppyft-feasibility/a/bin/python" gate2-validate-audits.py > gate2-validation.log 2>&1
```

The exact native build command in `gate2-build.sh` is:

```sh
PY="$HOME/guppyft-feasibility/a/bin/python"
INC="$(dirname "$PY")/../lib/python3.12/site-packages/selene_core/_dist/include"
"$PY" -m ziglang cc -shared -fPIC -O2 -Wall -Wextra -I "$INC" \
    gate2-fault-simulator.c -o gate2-fault-simulator.so -ldl
```

B is a clean virtual-environment repeat on the same Linux host, using Python 3.12.16 and cached wheels. Its 43-package freeze matches Gate 1's lock exactly. It does not constitute a second OS installation or independent compiler toolchain.

Observed outputs
----------------

Both environments A and B produced these results, with all assertions passing:

```text
baseline reference: syndrome=[0, 0, 0], correction=None, residual=[], P(logical=0,1)=[0.0, 1.0]
baseline Steane+active_Reichardt_QEC: Counter({(('logical', '1'),): 1000})
baseline: verified 0 physical injections across 1000 shots
single_X reference: syndrome=[1, 0, 0], correction=0, residual=[], P(logical=0,1)=[0.0, 1.0]
single_X Steane+active_Reichardt_QEC: Counter({(('logical', '1'),): 1000})
single_X: verified 1000 physical injections across 1000 shots
double_X reference: syndrome=[0, 1, 0], correction=4, residual=[0, 1, 4], P(logical=0,1)=[1.0, 0.0]
double_X Steane+active_Reichardt_QEC: Counter({(('logical', '0'),): 1000})
double_X: verified 2000 physical injections across 1000 shots
PASS: physical single-X corrected; physical double-X flips logical outcome; independent reference agrees.
```

First-shot physical readouts and active corrections matched across A and B:

| Case | Injected physical Xs | Active X correction | Final data bits, IDs 0–6 | Final syndrome | Logical parity |
|---|---|---|---|---|---|
| Baseline | None | None | 0011100 | 000 | 1 |
| Single | 0 | 0 | 0011100 | 000 | 1 |
| Double | 0, 1 | 4 | 0011011 | 000 | 0 |

Raw results: A (`gate2-output-a.log`), B (`gate2-output-b.log`), audit validation (`gate2-validation.log`), and `gate2-*-audit.log`. Full physical operation logs are saved for the first shot; fault-injection entries are saved for every shot.

Limitations and upstream assessment
-----------------------------------

No upstream change is required for this feasibility result. The public native simulator ABI suffices, and the public error-model ABI exposes the machinery for a more conventional deterministic error-model implementation. This is a custom compiled test plugin, not proof that an off-the-shelf Python-only scheduled-fault model exists.

Physical IDs and the chosen measurement ordinal are tied to this exact compiled program and simple runtime. There is no general logical-block-to-runtime-ID selector implemented here; changing the program, allocation strategy, compiler or runtime requires re-establishing that mapping and boundary. A convenient upstream improvement would be a bundled deterministic Pauli schedule error-model plugin with a Python wrapper accepting `(shot, instruction ordinal, physical ID, Pauli)`. That can use the existing ABI. Stable targeting by `(logical block, data index, logical boundary)` would additionally need compiler/runtime provenance or explicit marker operations.

Reichardt's supplied primitive uses code-capacity lookup decoding and assumes no faults during syndrome extraction, as its source documents. The controlled faults are placed before that circuit; the result does not establish arbitrary circuit-level fault tolerance. Only the selected single and double X patterns were simulated. Z injection and other boundaries were not tested.

An initial H-H identity trial was optimized away and did not trigger QEC, so the final test uses the explicit logical X with a QEC cost. A compiler-reordered circuit rendering is not an execution-order proof; the native operation audit establishes the actual injection boundary. Neither issue blocked the final public-API route.
