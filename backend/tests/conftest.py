from __future__ import annotations

import os
from pathlib import Path

import pytest

from tst.loader import LoadedData, load_all

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Never call the Anthropic API in tests (CLAUDE.md section 8): every event is written by
# MockLLMAdapter, whatever llm_settings.json or a local .env say.
os.environ["TST_LLM_ADAPTER"] = "mock"
os.environ.pop("ANTHROPIC_API_KEY", None)
# Throwaway saves need no fsync (tst/db/session.py; M6 sub-task 0: CI disks are slow to sync).
os.environ.setdefault("TST_SQLITE_SYNC", "OFF")


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
