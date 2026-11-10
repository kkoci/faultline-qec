import pytest
from faultline.programs import gate2
from faultline.runner import Runner


@pytest.fixture(scope="session")
def runner():
    return Runner(gate2())
