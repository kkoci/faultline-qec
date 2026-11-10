# Quickstart

Use Linux or an Ubuntu WSL shell. Run the following commands from the repository
root. Python and runtime dependencies are pinned in `.python-version`,
`pyproject.toml` and `uv.lock`.

## Install with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
git clone https://github.com/kkoci/faultline-qec.git
cd faultline-qec
uv sync --locked --python 3.12.16
```

For a WSL checkout under `/mnt/c`, set the environment location before syncing
to avoid slow copying on the Windows filesystem:

```sh
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/faultline-qec"
uv sync --locked --python 3.12.16
```

## Build the native plugin

```sh
uv run --locked faultline build-native
```

The build uses the pinned PyPI `ziglang` package and Selene's public headers.
No system C compiler or Rust toolchain is required. The shared library is cached
under `$XDG_CACHE_HOME/faultline-qec`, or `~/.cache/faultline-qec`.

## Inspect physical boundaries

```sh
uv run --locked faultline boundaries gate2 --audit artifacts/boundaries.jsonl
uv run --locked faultline boundaries gate2-x --audit artifacts/x-boundaries.jsonl
```

These commands run one fault-free shot and print the actual physical operation
stream. For the pinned benchmarks, inject after op **70** for Z readout and
after op **84** for X readout. Both address data IDs **0–6**.

## Run the paired sweep

```sh
uv run --locked faultline sweep gate2 --boundary 70 --both-bases --shots 1 --output artifacts/both-bases
```

The command chooses the matching X boundary automatically and executes all 210
cases in each basis. Read `artifacts/both-bases/coverage-both.md` and
`coverage-both.json`; individual reports and audits are in `z/` and `x/`.
Expect **63 corrected cases, 147 visible logical errors, zero mismatches**,
and zero oracle-predicted errors invisible in both bases.
An oracle mismatch makes the command exit 1; configuration or execution errors
exit 2. See the [committed results](results.md) for a sample.

## Build the documentation

The `docs` optional extra declares MkDocs and Material. Like the Pages workflow,
you can build without installing the Linux simulation stack:

```sh
uv tool run --from 'mkdocs>=1.6,<2' --with 'mkdocs-material>=9.5,<10' mkdocs build --strict
```
