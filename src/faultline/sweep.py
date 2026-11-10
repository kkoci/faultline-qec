"""Exhaustive distinct-data-qubit single and pair Pauli fault coverage."""
from collections import Counter
from itertools import combinations, product
import json
from pathlib import Path
import hashlib
import platform
import sys
from importlib.metadata import version
from .oracle import predict, predict_both_bases
from .runner import Runner


def fault_cases():
    for q in range(7):
        for pauli in "XYZ":
            yield ((q, pauli),)
    for a, b in combinations(range(7), 2):
        for pa, pb in product("XYZ", repeat=2):
            yield ((a, pa), (b, pb))


def sweep(runner: Runner, boundary: int, *, shots: int, output_dir: Path) -> dict:
    program = runner.program
    if boundary not in program.oracle_boundaries:
        raise ValueError("Boundary is not declared code-capacity compatible by this program adapter")
    output_dir.mkdir(parents=True, exist_ok=True)
    ops = runner.boundaries(output_dir / "baseline-audit.jsonl")
    if boundary not in {op["ordinal"] for op in ops}:
        raise ValueError("Boundary does not occur in the baseline execution")
    baseline = predict((), logical_state=program.logical_state, basis=program.readout_basis)
    ideal_bit = max(range(2), key=lambda bit: baseline.probabilities[bit])
    if baseline.probabilities[ideal_bit] != 1.0:
        raise ValueError("v0.1 sweep requires a deterministic ideal logical readout")
    actual_baseline = runner.run(shots=shots)
    if actual_baseline != Counter({ideal_bit: shots}):
        raise ValueError(f"Baseline disagrees with oracle: {actual_baseline}")
    rows = []
    for index, faults in enumerate(fault_cases()):
        prediction = predict(faults, logical_state=program.logical_state, basis=program.readout_basis)
        expected = max(range(2), key=lambda bit: prediction.probabilities[bit])
        schedule = [(boundary, program.data_qubits[q], p) for q, p in faults]
        audit = output_dir / "audits" / f"{index:03d}.jsonl"
        # Execution failures propagate: never classify a missing/failed run as corrected.
        counts = runner.run(schedule, shots=shots, audit_path=audit)
        matches = counts == Counter({expected: shots})
        outcome = "mismatch" if not matches else "logical_flip" if expected != ideal_bit else "corrected"
        rows.append({"faults": [{"data_index": q, "physical_qubit": program.data_qubits[q], "pauli": p} for q, p in faults],
                     "weight": len(faults), "category": outcome,
                     "counts": {str(k): v for k, v in sorted(counts.items())},
                     "oracle": prediction.to_dict(),
                     "unobserved_logical_error": prediction.logical_pauli != "I" and expected == ideal_bit,
                     "audit": str(audit.relative_to(output_dir))})
    totals = {kind: sum(r["category"] == kind for r in rows) for kind in ("corrected", "logical_flip", "mismatch")}
    report = {"schema_version": 1, "program": program.name, "boundary": boundary, "shots_per_case": shots,
              "versions": {name: version(name) for name in ("faultline-qec", "guppyft", "guppylang", "selene-sim", "selene-core", "numpy", "ziglang")},
              "python": sys.version, "platform": platform.platform(),
              "baseline_stream_sha256": hashlib.sha256(json.dumps(ops,sort_keys=True).encode()).hexdigest(),
              "readout_basis": program.readout_basis, "data_qubits": list(program.data_qubits),
              "classification_scope": "measured logical outcome; corrected does not certify the full logical channel",
              "baseline_counts": {str(k): v for k, v in sorted(actual_baseline.items())},
              "total_cases": len(rows), "totals": totals,
              "unobserved_logical_errors": sum(r["unobserved_logical_error"] for r in rows), "cases": rows}
    (output_dir / "coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [f"# Fault coverage: {program.name}", "", f"Boundary after op {boundary}; {shots} shots/case; {program.readout_basis} readout.", "",
             "`corrected` means the measured outcome is unchanged. See residual logical Paulis for phase errors hidden by this readout.", "",
             "| Fault weight | Cases | Corrected outcome | Logical flip | Oracle mismatch |", "|---|---:|---:|---:|---:|"]
    for weight in (1, 2):
        subset = [r for r in rows if r["weight"] == weight]
        c = Counter(r["category"] for r in subset)
        lines.append(f"| {weight} | {len(subset)} | {c['corrected']} | {c['logical_flip']} | {c['mismatch']} |")
    lines += ["", f"Unchanged outcomes with an oracle-predicted nonidentity logical Pauli: {report['unobserved_logical_errors']}.", "",
              "| Faults (physical ID:Pauli) | Category | Residual logical Pauli | Counts |", "|---|---|---|---|"]
    for r in rows:
        label = ", ".join(f"{f['physical_qubit']}:{f['pauli']}" for f in r["faults"])
        lines.append(f"| {label} | {r['category']} | {r['oracle']['logical_pauli']} | {r['counts']} |")
    (output_dir / "coverage.md").write_text("\n".join(lines) + "\n")
    return report


def combine_basis_reports(z_report: dict, x_report: dict, output_dir: Path) -> dict:
    """Pair matching physical fault patterns and compare both observed bits.

    A single-observable pass cannot certify the residual Pauli. The paired
    probe reconstructs it from changes relative to each probe's own baseline.
    """
    if (z_report["readout_basis"], x_report["readout_basis"]) != ("Z", "X"):
        raise ValueError("Expected Z and X readout reports")
    if z_report["shots_per_case"] != x_report["shots_per_case"]:
        raise ValueError("Both basis reports must use the same shot count")
    if len(z_report["cases"]) != len(x_report["cases"]):
        raise ValueError("Basis reports have different case counts")
    shots = z_report["shots_per_case"]
    if z_report["baseline_counts"] != {"1": shots} or x_report["baseline_counts"] != {"0": shots}:
        raise ValueError("Paired Gate 2 probes require baseline Z=1, X=0")
    rows = []
    for zr, xr in zip(z_report["cases"], x_report["cases"], strict=True):
        faults = tuple((f["data_index"], f["pauli"]) for f in zr["faults"])
        if faults != tuple((f["data_index"], f["pauli"]) for f in xr["faults"]):
            raise ValueError("Basis reports have different fault patterns/order")
        oracle = predict_both_bases(faults)
        expected = oracle["Z"].logical_pauli
        if oracle["X"].logical_pauli != expected:
            raise ValueError("Oracle residual Pauli differs between probes")
        zb = next((bit for bit in (0, 1) if zr["counts"] == {str(bit): shots}), None)
        xb = next((bit for bit in (0, 1) if xr["counts"] == {str(bit): shots}), None)
        z_flip = zb != 1 if zb is not None else None
        x_flip = xb != 0 if xb is not None else None
        observed = ({(False, False): "I", (True, False): "X",
                     (False, True): "Z", (True, True): "Y"}.get((z_flip, x_flip))
                    if zb is not None and xb is not None else None)
        visible = bool(z_flip or x_flip)
        mismatch = observed != expected or any(
            row["counts"] != {str(max(range(2), key=lambda bit: oracle[basis].probabilities[bit])): shots}
            for basis, row in (("Z", zr), ("X", xr)))
        rows.append({"faults": zr["faults"], "weight": zr["weight"],
                     "z_basis_result": zr["counts"], "x_basis_result": xr["counts"],
                     "z_basis_flip": z_flip, "x_basis_flip": x_flip,
                     "oracle_residual_logical_pauli": expected,
                     "observed_logical_pauli": observed,
                     "oracle": {basis: prediction.to_dict() for basis, prediction in oracle.items()},
                     "visible_in_at_least_one_basis": visible, "mismatch": mismatch,
                     "category": "mismatch" if mismatch else "corrected" if expected == "I" else "logical_flip",
                     "audits": {"Z": "z/" + zr["audit"], "X": "x/" + xr["audit"]}})
    totals = {kind: sum(r["category"] == kind for r in rows) for kind in ("corrected", "logical_flip", "mismatch")}
    invisible = sum(r["oracle_residual_logical_pauli"] != "I" and not r["visible_in_at_least_one_basis"] for r in rows)
    report = {"schema_version": 2, "program": "gate2-both", "shots_per_case": shots,
              "versions": z_report["versions"], "python": z_report["python"], "platform": z_report["platform"],
              "boundaries": {"Z": z_report["boundary"], "X": x_report["boundary"]},
              "baseline_counts": {"Z": z_report["baseline_counts"], "X": x_report["baseline_counts"]},
              "baseline_stream_sha256": {"Z": z_report["baseline_stream_sha256"], "X": x_report["baseline_stream_sha256"]},
              "total_cases": len(rows), "totals": totals,
              "basis_totals": {"Z": z_report["totals"], "X": x_report["totals"]},
              "oracle_residual_paulis": dict(sorted(Counter(r["oracle_residual_logical_pauli"] for r in rows).items())),
              "invisible_oracle_logical_errors": invisible, "cases": rows}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "coverage-both.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Gate 2 complementary-basis coverage", "",
             f"{shots} shots per case per basis; Z boundary {z_report['boundary']}, X boundary {x_report['boundary']}.", "",
             "| Weight | Cases | Corrected in both | Logical error visible | Mismatch |",
             "|---|---:|---:|---:|---:|"]
    for weight in (1, 2):
        subset = [r for r in rows if r["weight"] == weight]
        c = Counter(r["category"] for r in subset)
        lines.append(f"| {weight} | {len(subset)} | {c['corrected']} | {c['logical_flip']} | {c['mismatch']} |")
    lines += ["", f"Oracle-predicted logical errors invisible in both bases: {invisible}.", "",
              "| Faults (physical ID:Pauli) | Z result | X result | Oracle residual Pauli | Observed residual Pauli | Mismatch |",
              "|---|---|---|---|---|---|"]
    for row in rows:
        label = ", ".join(f"{f['physical_qubit']}:{f['pauli']}" for f in row["faults"])
        lines.append(f"| {label} | {row['z_basis_result']} | {row['x_basis_result']} | {row['oracle_residual_logical_pauli']} | {row['observed_logical_pauli']} | {str(row['mismatch']).lower()} |")
    (output_dir / "coverage-both.md").write_text("\n".join(lines) + "\n")
    return report


def sweep_both_bases(z_runner: Runner, x_runner: Runner, *, shots: int, output_dir: Path) -> dict:
    if (z_runner.program.name, x_runner.program.name) != ("gate2", "gate2-x"):
        raise ValueError("Paired sweep currently supports the two built-in Gate 2 probes")
    z_report = sweep(z_runner, z_runner.program.oracle_boundaries[0], shots=shots, output_dir=output_dir/"z")
    x_report = sweep(x_runner, x_runner.program.oracle_boundaries[0], shots=shots, output_dir=output_dir/"x")
    return combine_basis_reports(z_report, x_report, output_dir)
