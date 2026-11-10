> Historical report. See the [feasibility index](README.md) for scope and original-workspace references.

Feasibility test, 2026-11-09
===========================

Scope: standalone experiment only; no product code or commits. Host directory was empty and is not a Git repository.

Environment: Ubuntu 26.04.1 LTS under WSL2, Linux 6.6.114.1-microsoft-standard-WSL2 x86_64, glibc 2.43; uv 0.13.7; CPython 3.12.16. Primary pins: guppyft==0.6.1, selene-sim==0.3.7. Guppy is 1.2.0, Selene core 0.3.3, Selene HUGR QIS compiler 0.5.1, NumPy 2.5.4. All 43 package versions are in requirements.lock; repeat installation uses that complete lock.

Source: https://docs.quantinuum.com/guppy/ft/examples/steane_encoding.html

Official noisy example, environments A AND B: `Counter({(('tgt', '0'),): 1000})`. Both executions exited successfully. The saved upstream notebook contains 999 zeros and one one; stochastic results need not match a historical saved notebook output across simulator/compiler versions. The executable cells, seed and error rates were preserved.

The documentation's downloadable notebook URL returned HTTP 404. The official repository notebook was therefore downloaded from https://raw.githubusercontent.com/Quantinuum/guppyft/main/examples/steane_encoding.ipynb and saved locally. Its SHA256 is 3f1ce930d1e1bc553f3cc1b703c05d1e88b9dd20cfdd5a5716169f033795c3e9. The first five code cells are extracted verbatim by reproduce_official.py into official_example.py. They implement teleportation of |0>, Steane encoding with three logical blocks, and 1,000 Stim shots with seed 42, 22 physical qubits, and the documented depolarizing model (p_1q=1e-4, p_2q=1e-3).

Commands (Linux, from this directory)
------------------------------------

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
bash setup.sh > setup-and-run-a.log 2>&1
bash repeat.sh > setup-and-run-b.log 2>&1
# Run only after both setup commands have completed:
bash official.sh > official-output.log 2>&1
```

setup.sh explicitly installs the primary pins into environment A and freezes the complete resolution. repeat.sh clears/recreates environment B and synchronizes the full lock. Both use exactly Python 3.12.16. requirements-b.lock must compare equal to requirements.lock. B inherits no installed packages from A, but reuses uv's downloaded wheel cache and the installed Python interpreter. This is a clean virtual-environment repeat on the same Linux host, not a second machine/OS image. An initial attempt to use a separate empty wheel cache was stopped because downloads were slow; its partial log is fresh-cache-download-attempt.log.

Ideal and deviation experiment
------------------------------

feasibility.py preserves the official teleportation functions and runs with no error model. It reserves 98 physical qubits for the encoded runs (three for unencoded), uses three logical blocks, Stim seed 42 and 1,000 shots. The sole deviation is `qlib.x(tgt)` immediately after teleportation and before final Z measurement, added before encoding. This becomes a logical X in the encoded program.

The independent reference is an eight-amplitude NumPy state-vector calculation, implemented without Guppy, Selene, Stim or TKET. It applies the Bell preparation and teleportation gates, enumerates all four measurement branches, applies the conditional corrections, and sums target measurement probabilities. Every branch has probability 0.25. It predicts P(0)=1 for baseline and P(1)=1 for the deviation. The unencoded Selene executions provide an additional comparison, but are not the independent reference.

Observed output in BOTH environment A and freshly recreated environment B (all assertions passed; package freezes compared equal):

```text
baseline NumPy reference P(tgt=0,1)=[1.0, 0.0]; branch weights=[0.25, 0.25, 0.25, 0.25]
baseline unencoded: Counter({(('tgt', '0'),): 1000})
baseline Steane: Counter({(('tgt', '0'),): 1000})
wrong_X NumPy reference P(tgt=0,1)=[0.0, 1.0]; branch weights=[0.25, 0.25, 0.25, 0.25]
wrong_X unencoded: Counter({(('tgt', '1'),): 1000})
wrong_X Steane: Counter({(('tgt', '1'),): 1000})
PASS: ideal baseline and one-gate deviation agree with independent reference.
```

Public API assessment: step 3 succeeds using the deliberate-wrong-gate option. Only public quantum operations, SteaneBuilder.build/encode, EmulatorBuilder.build, and simulator/shot configuration are used. No private API, compiler rewrite, custom native plugin, or physical fault injector is needed. This tests an intentionally wrong logical operation; it does not establish a public API for injecting a Pauli fault at a selected physical instruction, nor demonstrate failure of single-fault correction.

Operational issues: initial Windows-to-shell quoting/line-ending failures were corrected by writing LF scripts. An initial environment under /tmp disappeared between WSL invocations; final environments live under /home/kkoci/guppyft-feasibility/{a,b}. The official notebook was initially attempted in B before its installation completed, causing ModuleNotFoundError; this is a setup timing issue, not a Guppy FT API failure. Final raw logs are retained separately.
