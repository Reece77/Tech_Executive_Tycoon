from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

from tst.loader import LoadedData, load_all

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DURATIONS_FILE = Path(__file__).resolve().parent / "durations.json"

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
    parser.addoption(
        "--shard",
        default=None,
        help="Run one of N shards balanced by measured duration, as K/N (CI's matrix jobs)",
    )
    parser.addoption(
        "--store-durations",
        action="store_true",
        default=False,
        help="Write each test's duration (setup, call and teardown) to tests/durations.json",
    )


# On the 2-core CI runner a test costs about 0.93x its local duration plus 1.2 s (fixtures,
# caches built once per worker, save setup), fitted from two shards with equal local time:
# 176 tests took 467 s and 668 took 761 s. So each test also weighs this much when sharding.
SHARD_OVERHEAD_S = 1.3


def shard_of(nodeids: list[str], durations: dict[str, float], shards: int) -> dict[str, int]:
    """Heaviest first, each to the shard with the least weight so far (ties: the lowest
    shard); a test weighs its duration plus SHARD_OVERHEAD_S. A test missing from the
    durations file counts as the mean of the known ones."""
    known = [durations[n] for n in nodeids if n in durations]
    default = sum(known) / len(known) if known else 1.0
    totals = [0.0] * shards
    shard: dict[str, int] = {}
    for n in sorted(nodeids, key=lambda n: (-durations.get(n, default), n)):
        k = min(range(shards), key=lambda i: (totals[i], i))
        shard[n] = k
        totals[k] += durations.get(n, default) + SHARD_OVERHEAD_S
    return shard


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    spec = config.getoption("--shard")
    if spec is None:
        return
    k, n = (int(x) for x in spec.split("/"))
    if not 1 <= k <= n:
        raise pytest.UsageError(f"--shard must be K/N with 1 <= K <= N, got {spec}")
    durations = json.loads(DURATIONS_FILE.read_text()) if DURATIONS_FILE.exists() else {}
    shard = shard_of([i.nodeid for i in items], durations, n)
    keep = [i for i in items if shard[i.nodeid] == k - 1]
    config.hook.pytest_deselected(items=[i for i in items if shard[i.nodeid] != k - 1])
    items[:] = keep


_DURATIONS: defaultdict[str, float] = defaultdict(float)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    _DURATIONS[report.nodeid] += report.duration


def pytest_sessionfinish(session: pytest.Session) -> None:
    config = session.config
    if config.getoption("--store-durations") and not hasattr(config, "workerinput"):
        rounded = {n: round(d, 2) for n, d in sorted(_DURATIONS.items())}
        DURATIONS_FILE.write_text(json.dumps(rounded, indent=1) + "\n")
