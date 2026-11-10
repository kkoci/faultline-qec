import json
from pathlib import Path
import pytest
from faultline.cli import main
from faultline.model import PauliScheduleErrorModel
from faultline.sweep import sweep


def test_boundaries(runner,tmp_path):
    ops=runner.boundaries(tmp_path/"boundaries.jsonl")
    assert len(ops)==248
    assert [op["ordinal"] for op in ops]==list(range(1,249))
    assert ops[69]["label"].startswith("prepared block 0")
    assert ops[69]["qubits"]==[7]
    assert ops[0]["roles"]==["data[0]"]


def test_complete_native_sweep(runner,tmp_path):
    report=sweep(runner,70,shots=1,output_dir=tmp_path)
    assert report["total_cases"]==210
    assert report["totals"]=={"corrected":126,"logical_flip":84,"mismatch":0}
    assert report["unobserved_logical_errors"]==63
    assert sum(row["weight"]==1 for row in report["cases"])==21
    assert json.loads((tmp_path/"coverage.json").read_text())["totals"]==report["totals"]
    assert "| 2 | 189 | 105 | 84 | 0 |" in (tmp_path/"coverage.md").read_text()


def test_invalid_boundary_rejected(runner,tmp_path):
    with pytest.raises(ValueError,match="code-capacity"):
        sweep(runner,1,shots=1,output_dir=tmp_path)


def test_cli_argument_errors():
    assert main(["boundaries","missing-file.py"])==2
    with pytest.raises(SystemExit): main(["sweep","gate2"])


def test_boundaries_cli_output(tmp_path,capsys):
    assert main(["boundaries","gate2","--audit",str(tmp_path/"cli.jsonl")]) == 0
    lines=capsys.readouterr().out.splitlines()
    assert len(lines)==248
    assert "0070 MEASURE" in lines[69]
    assert "prepared block 0" in lines[69]


def test_sweep_reports_observed_oracle_mismatch(runner,tmp_path,monkeypatch):
    real_run=runner.run
    def altered_run(schedule=(), **options):
        if schedule==[(70,0,"X"),(70,1,"X")]:
            return {1:options["shots"]}
        return real_run(schedule,**options)
    monkeypatch.setattr(runner,"run",altered_run)
    report=sweep(runner,70,shots=1,output_dir=tmp_path)
    assert report["totals"]["mismatch"]==1
    mismatch=next(row for row in report["cases"] if row["category"]=="mismatch")
    assert mismatch["oracle"]["probabilities"]==(1,0)


@pytest.mark.parametrize("schedule", [[(0,0,"X")],[(1,-1,"X")],[(1,0,"A")],[(True,0,"X")]])
def test_invalid_schedules(schedule):
    with pytest.raises(ValueError): PauliScheduleErrorModel(schedule=schedule)


def test_stable_sorted_schedule_and_public_abi():
    model=PauliScheduleErrorModel([(9,1,"Z"),(3,0,"Y"),(9,1,"X")])
    assert model.schedule==((3,0,"Y"),(9,1,"Z"),(9,1,"X"))
    import ctypes
    lib=ctypes.CDLL(str(model.library_file))
    assert lib.selene_error_model_get_plugin_descriptor_v1
