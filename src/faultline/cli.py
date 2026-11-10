import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .build import build_native
from .programs import load_program
from .runner import Runner
from .sweep import sweep, sweep_both_bases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="faultline", description="Deterministic physical Pauli faults for Selene/Steane")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-native", help="Build the public-ABI native error-model plugin with pip ziglang")
    boundaries = sub.add_parser("boundaries", help="Run once and print the original physical operation stream")
    boundaries.add_argument("program", help="gate2, gate2-x or file.py[:build_program]")
    boundaries.add_argument("--audit", type=Path, default=Path("artifacts/boundaries.jsonl"))
    scan = sub.add_parser("sweep", help="All 21 single and 189 distinct-qubit pair Pauli faults")
    scan.add_argument("program", nargs="?", default="gate2")
    scan.add_argument("--boundary", type=int, required=True, help="Inject after this original op ordinal")
    scan.add_argument("--shots", type=int, default=1)
    scan.add_argument("--output", type=Path, default=Path("artifacts/sweep"))
    scan.add_argument("--both-bases", action="store_true",
                      help="Pair Gate 2 Z/X probes at boundaries 70/84; requires gate2 --boundary 70")
    args = parser.parse_args(argv)
    try:
        if args.command == "build-native":
            print(build_native())
            return 0
        if args.command == "sweep" and args.both_bases and (args.program != "gate2" or args.boundary != 70):
            raise ValueError("--both-bases requires gate2 --boundary 70 (X probe uses boundary 84)")
        runner = Runner(load_program(args.program))
        if args.command == "boundaries":
            for op in runner.boundaries(args.audit):
                qubits = ",".join(map(str, op["qubits"]))
                roles = ",".join(op["roles"])
                angles = f" theta={op['theta']:.12g} phi={op['phi']:.12g}" if op["kind"] in ("RXY", "RZ", "RZZ", "RPP") else ""
                result = f" result={op['result']}" if op["kind"].startswith("MEASURE") else ""
                print(f"{op['ordinal']:04d} {op['kind']:14s} q=[{qubits}] {roles}{angles}{result} {op['label']}".rstrip())
            return 0
        if args.both_bases:
            report = sweep_both_bases(runner, Runner(load_program("gate2-x")), shots=args.shots, output_dir=args.output)
            print(json.dumps({"total_cases": report["total_cases"], **report["totals"],
                              "invisible_oracle_logical_errors": report["invisible_oracle_logical_errors"],
                              "basis_totals": report["basis_totals"]}, sort_keys=True))
            print(args.output / "coverage-both.json")
            print(args.output / "coverage-both.md")
            return 1 if report["totals"]["mismatch"] or report["invisible_oracle_logical_errors"] else 0
        report = sweep(runner, args.boundary, shots=args.shots, output_dir=args.output)
        print(json.dumps({"total_cases": report["total_cases"], **report["totals"],
                          "unobserved_logical_errors": report["unobserved_logical_errors"]}, sort_keys=True))
        print(args.output / "coverage.json")
        print(args.output / "coverage.md")
        return 1 if report["totals"]["mismatch"] else 0
    except Exception as exc:
        print(f"faultline: {exc}", file=sys.stderr)
        return 2
