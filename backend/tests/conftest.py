from __future__ import annotations

from pathlib import Path

import pytest

from tst.loader import LoadedData, load_all

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def loaded() -> LoadedData:
    return load_all(DATA_DIR)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate tests/golden/snapshots/*.json (record the reason in CHANGELOG.md)",
    )
