# v0.1 validation — updated 2026-11-10

Scaffold created under `faultline-qec/`; previous Gate 1/2 evidence remains in the parent directory. No Git repository was initialized, no commits were made, and no GitHub workflow was submitted.

## Versions

Local platform: Ubuntu 26.04.1 LTS under WSL2, x86_64, Linux 6.6.114.1-microsoft-standard-WSL2, glibc 2.43.

| Component | Version |
|---|---|
| faultline-qec | 0.1.0 |
| CPython | 3.12.16 |
| uv | 0.13.7 |
| Guppy FT | 0.6.1 |
| Guppy / internals | 1.2.0 / 1.2.0 |
| Selene | 0.3.7 |
| Selene core | 0.3.3 |
| Selene HUGR QIS compiler | 0.5.1 |
| NumPy | 2.5.4 |
| ziglang / Zig | 0.16.0 / 0.16.0 |
| pytest | 9.0.2 |

All 43 original Gate 2 pins were checked against installed distribution metadata, with no differences. `artifacts/versions.json` records them; [uv.lock](uv.lock) also pins the added development dependencies. The C plugin uses error-model descriptor API version 768 (0x0300) from the installed public header. Native build flags: `-shared -fPIC -O2 -Wall -Wextra -Werror`, invoked through `python -m ziglang cc`. No system compiler was installed.

## Commands actually run

From this project directory inside WSL Ubuntu:

```sh
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/faultline-qec"
uv sync --python 3.12.16
uv run faultline build-native
uv run faultline boundaries gate2 > artifacts/boundaries.txt
uv run --locked pytest -q
uv run --locked faultline sweep gate2 --boundary 70 --shots 1 --output artifacts/sweep
uv run --locked faultline sweep gate2 --boundary 70 --both-bases --shots 1 --output artifacts/both-bases
uv build --wheel
"$UV_PROJECT_ENVIRONMENT/bin/python" scripts/record-versions.py > artifacts/versions.json
"$UV_PROJECT_ENVIRONMENT/bin/python" examples/gate2_regression.py > gate2-regression-output.log
```

The first command generated the lock; subsequent validation used it. `scripts/dev-setup.sh`, `scripts/validate-local.sh`, `scripts/package-check.sh` and `scripts/wheel-smoke.sh` preserve reproducible command sequences. After initial validation, the suite was repeated when constructor ergonomics, report metadata, mismatch detection and CLI formatting checks were added.

Generated logs, JSONL audits and machine-specific version output are ignored
local evidence, not public repository files. The curated [sample paired coverage
table](docs/sample-coverage.md) is included for review without running the tool.
The historical reports are archived in [docs/feasibility](docs/feasibility/README.md).

An initial `.venv` installation on the mounted Windows filesystem was stopped because copying the compiler/dependency files was slow. Completed validation used the Linux-home environment shown above.

## Native ABI regression

The printed regression output from the **error-model** implementation, with 1,000 shots per case:

```text
baseline: Counter({1: 1000}); oracle=(0.0, 1.0); residual=I
single_X: Counter({1: 1000}); oracle=(0.0, 1.0); residual=I
double_X: Counter({0: 1000}); oracle=(1.0, 0.0); residual=X
PASS: Gate 2 reproduced with the native error-model ABI.
```

The test suite additionally checks that every shot applies its entire schedule, reproduces the original first-shot final data words `0011100` / `0011100` / `0011011`, and observes the actual active X correction on data ID 0 for the single fault or ID 4 for the double fault. First-shot raw data have zero syndrome and logical parities 1 / 1 / 0. This separates active QEC recovery from final-readout correction.

Regression JSONL audits are under `artifacts/regression/`; printed output is `gate2-regression-output.log`.

## Boundaries command

The baseline contains 248 original physical operations. Excerpt from `artifacts/boundaries.txt`:

```text
0068 RXY            q=[7] ancilla/other theta=1.57079632679 phi=3.14159265359
0069 RZ             q=[7] ancilla/other theta=-1.57079632679 phi=0
0070 MEASURE        q=[7] ancilla/other result=0 prepared block 0; flag measured; before transversal X + Reichardt QEC
0071 RXY            q=[0] data[0] theta=3.14159265359 phi=0
0072 RXY            q=[1] data[1] theta=3.14159265359 phi=0
```

The unmodified baseline operation audit is `artifacts/boundaries.jsonl`. Timing metadata does not advance ordinals; injected fault gates have their own audit events.

## Full XYZ sweep

Actual CLI output:

```text
{"corrected": 126, "logical_flip": 84, "mismatch": 0, "total_cases": 210, "unobserved_logical_errors": 63}
artifacts/sweep/coverage.json
artifacts/sweep/coverage.md
```

| Fault weight | Cases | Corrected outcome | Logical flip | Oracle mismatch |
|---|---:|---:|---:|---:|
| 1 | 21 | 21 | 0 | 0 |
| 2 | 189 | 105 | 84 | 0 |

The 189 pairs cover all nine Pauli combinations on each unordered pair of distinct data IDs. The oracle's residual logical Paulis among pairs are I:42, X:63, Y:21, Z:63. The 63 residual logical Z errors are invisible in this Z-only report; the complementary X readout below makes all of them visible. The single-basis `corrected` classification refers to that observable only.

Full rows, predictions and per-case audit locations: `artifacts/sweep/coverage.json`, `artifacts/sweep/coverage.md`.

## Complementary Z/X sweep

The new `gate2-x` program prepares logical |+>, performs the same transversal logical X and exactly one active Reichardt QEC cycle, then measures X using a final transversal H and Z readout. Its baseline output is 0. Its baseline native stream contains 276 original physical operations and 14 measurements (one preparation flag, six QEC syndromes, seven final data measurements).

The matching fault boundaries are after op 70 for `gate2` and after op 84 for `gate2-x`, both after state preparation and before the common logical X/QEC. The X boundary follows the 14 physical rotations implementing the seven preparation H gates. Native audits establish that the same physical IDs 0-6 carry the data in both probes. No fault is placed before the |+> preparation.

The paired oracle computes both readouts independently with NumPy and predicts the same residual logical Pauli for each fault pattern. Observed readout flips, relative to Z baseline 1 and X baseline 0, reconstruct I/X/Y/Z. The sweep uses one shot per deterministic case per basis: 420 faulted executions across 210 paired cases, plus baseline checks.

Actual paired CLI output (successful exit):

```text
{"basis_totals": {"X": {"corrected": 126, "logical_flip": 84, "mismatch": 0}, "Z": {"corrected": 126, "logical_flip": 84, "mismatch": 0}}, "corrected": 63, "invisible_oracle_logical_errors": 0, "logical_flip": 147, "mismatch": 0, "total_cases": 210}
artifacts/both-bases/coverage-both.json
artifacts/both-bases/coverage-both.md
```

| Basis | Cases | Unchanged outcome | Flipped outcome | Oracle mismatch |
|---|---:|---:|---:|---:|
| Z | 210 | 126 | 84 | 0 |
| X | 210 | 126 | 84 | 0 |

| Fault weight | Paired cases | Corrected in both | Logical error visible | Mismatch |
|---|---:|---:|---:|---:|
| 1 | 21 | 21 | 0 | 0 |
| 2 | 189 | 42 | 147 | 0 |
| Total | 210 | 63 | 147 | 0 |

| Oracle residual logical Pauli | Cases | Observed Z result | Observed X result |
|---|---:|---:|---:|
| I | 63 | 1 | 0 |
| X | 63 | 0 | 0 |
| Y | 21 | 0 | 1 |
| Z | 63 | 1 | 1 |

Every one of the 147 oracle-predicted logical errors is visible in at least one basis. There are **zero mismatches** and **zero oracle-predicted errors invisible in both bases**. The combined JSON and Markdown include both result counts, the oracle residual logical Pauli and a mismatch flag for every case, plus the Pauli reconstructed from the observed pair.

Per-case results: `artifacts/both-bases/coverage-both.json`, [sample paired coverage](docs/sample-coverage.md). Individual reports and injection audits are retained under `artifacts/both-bases/z/` and `artifacts/both-bases/x/`. These results characterize the deterministic Pauli/code-capacity cases tested; they do not establish general circuit-level fault tolerance or general process tomography.

## Tests and distribution

Actual final test summary:

```text
34 passed, 3 warnings in 67.57s (0:01:07)
```

The three warnings originate from the pinned Selene build path calling its deprecated `compile_to_bitcode` helper; there were no test failures. The final public-preparation run is recorded locally in `artifacts/public-prep-tests.log`. `validation-both-output.log` retains the both-basis development run; `validation-output.log` retains the original Z-only validation.

New tests verify logical-plus preparation and the six active QEC syndromes in the X probe, baseline X outcome 0 for 1,000 shots, and X/X, Z/Z and Y/Y pair outcomes for 100 shots each. The complete 210-case paired sweep checks every case against both independent oracle readouts. A negative test deliberately changes the X-basis result for a Z/Z pair and requires both a mismatch and an invisible-error count, ensuring phase errors cannot silently pass.

The wheel was rebuilt successfully after the both-basis update:

```text
Successfully built dist/faultline_qec-0.1.0-py3-none-any.whl
Wheel includes native source: dist/faultline_qec-0.1.0-py3-none-any.whl
```

The initial 2026-11-09 distribution smoke test installed the original v0.1 wheel in a separate clean environment at `$HOME/.venvs/faultline-qec-wheel` with `uv pip install --constraint gate2-constraints.txt`. From outside the source checkout, with a separate `XDG_CACHE_HOME`, it compiled the bundled C source and ran:

```text
baseline {1: 10}
single {1: 10}
double {0: 10}
PASS: installed wheel builds native plugin and reproduces Gate 2.
```

See the updated `packaging-output.log` and original `wheel-smoke-output.log`. The original smoke test verified native loading from an installed distribution; the new X probe and paired sweep were tested in the pinned editable environment. The native plugin and dependency pins are unchanged.

The GitHub Actions workflow is [linux.yml](.github/workflows/linux.yml). It installs the locked Linux environment, builds the native plugin and runs tests and CLI commands. It has not been executed remotely; that requires placing this directory at a repository root and pushing it.

## Public-commit preparation

Both pinned upstream licence files were read first: Selene's `LICENSE` and
Guppy FT's `LICENCE` are Apache-2.0. The project now includes an Apache-2.0
[LICENSE](LICENSE), copyright 2026 Khrystian Koci, with matching author and
licence metadata in `pyproject.toml`. Sources are linked in
[docs/licensing.md](docs/licensing.md).

Gate 1 and Gate 2 reports were moved to `docs/feasibility/`. The generated
paired coverage table was copied byte-for-byte to `docs/sample-coverage.md`
and linked from the README. All relative Markdown links resolve to files
included in the proposed public commit. Historical private-workspace artifact
references are retained as filenames rather than broken public links.

The five development helpers are under `scripts/` and locate the project root
themselves. Version recording and wheel smoke-test constraints now read the
canonical pins in `pyproject.toml`; `gate2-constraints.txt` is redundant and
ignored. Logs, generated artifacts, distributions and caches are also ignored.

The tests were run once more after preparation: 34 passed, with the same three
upstream deprecation warnings. The package check verified that the wheel
includes the native source, the Apache-2.0 licence and Khrystian Koci author
metadata. The moved wheel smoke script also passed using a fresh temporary
environment and cache, reproducing baseline/single/double outcomes 1/1/0 for
10 shots each without `gate2-constraints.txt`. No commit was created.

## Practical limits

The oracle models code-capacity recovery with the Reichardt lookup decoder and otherwise ideal syndrome extraction. It is valid only at adapter-declared compatible boundaries, not at arbitrary instructions inside the recovery gadget. Runtime IDs and ordinals are specific to the encoded program and pinned toolchain. A baseline audit samples one control-flow path. Faults can change subsequent physical streams; unreached schedule entries fail explicitly. See [README.md](README.md) for the API, adapter contract, observable scope and other limits.
