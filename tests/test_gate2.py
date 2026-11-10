from collections import Counter
import math
import pytest
from faultline.runner import read_audit


@pytest.mark.parametrize("faults,expected,correction,raw", [
    ([], 1, None, [0,0,1,1,1,0,0]),
    ([(70,0,"X")], 1, 0, [0,0,1,1,1,0,0]),
    ([(70,0,"X"),(70,1,"X")], 0, 4, [0,0,1,1,0,1,1]),
])
def test_gate2_exact(runner, tmp_path, faults, expected, correction, raw):
    audit = tmp_path / "audit.jsonl"
    assert runner.run(faults, shots=1000, audit_path=audit) == Counter({expected:1000})
    events = read_audit(audit)
    injections = [e for e in events if e["event"] == "fault"]
    assert len(injections) == len(faults)*1000
    assert all(e["status"] == 0 and e["after"] == 70 for e in injections)
    for shot in range(1000):
        assert [(e["qubit"],e["pauli"]) for e in injections if e["shot"] == shot] == [(q,p) for _,q,p in faults]
    first = [e for e in events if e["event"] == "op" and e["shot"] == 0]
    measures = [e for e in first if e["kind"] == "MEASURE"]
    assert len(measures) == 14
    assert (measures[0]["ordinal"], measures[0]["qubits"], measures[0]["result"]) == (70,[7],0)
    assert [e["result"] for e in measures[7:]] == raw
    # Active physical correction AFTER the six syndrome measurements.
    recovery = [e for e in first if measures[6]["ordinal"] < e["ordinal"] < measures[7]["ordinal"]]
    assert len(recovery) == int(correction is not None)
    if recovery:
        assert recovery[0]["kind"] == "RXY" and recovery[0]["qubits"] == [correction]
        assert math.isclose(recovery[0]["theta"], math.pi)
    ends = [e for e in events if e["event"] == "shot_end"]
    assert len(ends) == 1000 and all(e["status"] == 0 for e in ends)


@pytest.mark.parametrize("pauli", list("XYZ"))
def test_native_single_paulis(runner, tmp_path, pauli):
    assert runner.run([(70,2,pauli)], shots=10, audit_path=tmp_path/f"{pauli}.jsonl") == {1:10}


def test_duplicate_faults_cancel_every_shot(runner, tmp_path):
    audit = tmp_path / "duplicate.jsonl"
    assert runner.run([(70,0,"Y"),(70,0,"Y")], shots=3, audit_path=audit) == {1:3}
    assert len([e for e in read_audit(audit) if e["event"]=="fault"]) == 6


def test_unreached_schedule_is_error(runner, tmp_path):
    with pytest.raises(Exception):
        runner.run([(999999,0,"X")], audit_path=tmp_path/"unreached.jsonl")


def test_out_of_range_physical_id(runner):
    with pytest.raises(Exception):
        runner.run([(70,32,"X")])
