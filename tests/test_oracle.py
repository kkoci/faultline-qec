from collections import Counter
import numpy as np
import pytest
from faultline.oracle import apply_pauli, codewords, predict
from faultline.sweep import fault_cases


def test_all_single_paulis_are_corrected_in_both_bases():
    for case in list(fault_cases())[:21]:
        for state,basis in [("1","Z"),("+","X")]:
            result = predict(case,logical_state=state,basis=basis)
            assert result.logical_pauli == "I"
            assert result.state_fidelity == 1


def test_pair_logical_channels_and_phase_blindness():
    pairs=list(fault_cases())[21:]
    assert len(pairs)==189 and len(set(pairs))==189
    assert Counter(predict(case).logical_pauli for case in pairs) == {"I":42,"X":63,"Y":21,"Z":63}
    zpair=((0,"Z"),(1,"Z"))
    assert predict(zpair).probabilities == (0,1)
    assert predict(zpair).logical_pauli == "Z"
    assert predict(zpair,logical_state="+",basis="X").probabilities == (0,1)
    assert predict(zpair,logical_state="+",basis="X").state_fidelity == 0


def test_y_matrix_phase_and_pauli_products():
    state=np.zeros(128,dtype=complex); state[0]=1
    result=apply_pauli(state,0,"Y")
    assert result[64]==1j and np.count_nonzero(result)==1
    assert np.allclose(apply_pauli(result,0,"Y"),state)
    zero,one=codewords()
    for q in range(7):
        assert np.allclose(apply_pauli(apply_pauli(zero,q,"X"),q,"X"),zero)
    assert np.isclose(np.vdot(zero,one),0)
    assert predict([(0,"X"),(0,"X")]).logical_pauli=="I"


@pytest.mark.parametrize("faults", [[(7,"X")],[(-1,"Z")],[(0,"I")]])
def test_invalid_reference_fault(faults):
    with pytest.raises(ValueError): predict(faults)
