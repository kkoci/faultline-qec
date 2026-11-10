import json
from collections import Counter
import pytest
from faultline.oracle import predict_both_bases
from faultline.programs import load_program
from faultline.runner import Runner, read_audit
from faultline.sweep import fault_cases, sweep_both_bases, combine_basis_reports
from faultline.cli import main


@pytest.fixture(scope="module")
def x_runner():
    return Runner(load_program("gate2-x"))


@pytest.fixture(scope="module")
def paired(runner, x_runner, tmp_path_factory):
    root = tmp_path_factory.mktemp("paired-coverage")
    return sweep_both_bases(runner, x_runner, shots=1, output_dir=root), root


def test_x_basis_preparation_and_qec(x_runner, tmp_path):
    ops = x_runner.boundaries(tmp_path/"x-boundaries.jsonl")
    assert len(ops) == 276
    assert ops[83]["label"].startswith("prepared logical +")
    assert x_runner.program.oracle_boundaries == (84,)
    measures = [op for op in ops if op["kind"] == "MEASURE"]
    assert len(measures) == 14  # prep flag + six active syndromes + seven data
    assert [op["qubits"][0] for op in measures[7:]] == list(range(7))
    assert all(op["result"] == 0 for op in measures[1:7])
    assert x_runner.run(shots=1000) == {0:1000}


@pytest.mark.parametrize("faults,expected", [
    ([(84,0,"X"),(84,1,"X")], 0),
    ([(84,0,"Z"),(84,1,"Z")], 1),
    ([(84,0,"Y"),(84,1,"Y")], 1),
])
def test_x_basis_fault_visibility(x_runner, tmp_path, faults, expected):
    audit = tmp_path/"faults.jsonl"
    assert x_runner.run(faults, shots=100, audit_path=audit) == {expected:100}
    events = read_audit(audit)
    assert len([e for e in events if e["event"] == "fault"]) == 200
    assert all(e["after"] == 84 for e in events if e["event"] == "fault")


def test_paired_oracle_has_no_blind_pauli():
    for faults in fault_cases():
        predictions = predict_both_bases(iter(faults))
        z, x = predictions["Z"], predictions["X"]
        assert z.logical_pauli == x.logical_pauli
        z_flipped = z.probabilities == (1,0)
        x_flipped = x.probabilities == (0,1)
        assert (z_flipped,x_flipped) == {"I":(False,False),"X":(True,False),
                                       "Y":(True,True),"Z":(False,True)}[z.logical_pauli]


def test_all_210_native_cases_in_both_bases(paired):
    report, root = paired
    assert report["total_cases"] == 210
    assert report["totals"] == {"corrected":63,"logical_flip":147,"mismatch":0}
    assert report["invisible_oracle_logical_errors"] == 0
    assert report["oracle_residual_paulis"] == {"I":63,"X":63,"Y":21,"Z":63}
    assert report["boundaries"] == {"Z":70,"X":84}
    assert report["baseline_counts"] == {"Z":{"1":1},"X":{"0":1}}
    for basis in ("Z","X"):
        assert report["basis_totals"][basis] == {"corrected":126,"logical_flip":84,"mismatch":0}
    for row in report["cases"]:
        assert not row["mismatch"]
        assert row["observed_logical_pauli"] == row["oracle_residual_logical_pauli"]
        assert row["visible_in_at_least_one_basis"] == (row["oracle_residual_logical_pauli"] != "I")
        assert row["weight"] in (1,2)
        assert (root/row["audits"]["Z"]).is_file() and (root/row["audits"]["X"]).is_file()
    flips = Counter((r["z_basis_flip"], r["x_basis_flip"]) for r in report["cases"])
    assert flips == {(False,False):63,(True,False):63,(False,True):63,(True,True):21}
    assert json.loads((root/"coverage-both.json").read_text())["totals"] == report["totals"]
    assert "| 2 | 189 | 42 | 147 | 0 |" in (root/"coverage-both.md").read_text()


def test_hidden_phase_error_is_a_mismatch(paired,tmp_path):
    _, root = paired
    z = json.loads((root/"z/coverage.json").read_text())
    x = json.loads((root/"x/coverage.json").read_text())
    row = next(r for r in x["cases"] if [(f["data_index"],f["pauli"]) for f in r["faults"]] == [(0,"Z"),(1,"Z")])
    row["counts"] = {"0":1}  # Deliberately hide the phase flip in X readout.
    result = combine_basis_reports(z,x,tmp_path)
    assert result["totals"]["mismatch"] == 1
    assert result["invisible_oracle_logical_errors"] == 1
    mismatch = next(r for r in result["cases"] if r["mismatch"])
    assert mismatch["oracle_residual_logical_pauli"] == "Z"
    assert mismatch["observed_logical_pauli"] == "I"


def test_paired_sweep_cli_rejects_wrong_boundary():
    assert main(["sweep","gate2","--boundary","84","--both-bases"]) == 2
