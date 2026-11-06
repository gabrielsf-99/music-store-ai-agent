from pathlib import Path

import pytest

FIXTURE_DATA_DIR = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def fixture_data_dir() -> Path:
    return FIXTURE_DATA_DIR
