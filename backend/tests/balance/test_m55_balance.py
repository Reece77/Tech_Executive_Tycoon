"""M55's 65.8 targets 2-5 (nightly; tst.balance.m55): hits rule, content is capital-heavy,
networks tip and egos bite, on seeds 1-10. Target 1 is M28's history fingerprint, M30's state
cache and tests/balance/test_m55_consumer_apps.py; target 6 is `make check-timing`. The full run
is `tools/m55_targets.py`, printed in the brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m55


@pytest.mark.nightly
def test_65_8_targets_2_to_5() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    rows = m55.run(m55.SEEDS, workers=jobs)
    print(m55.table(rows))
    assert m55.met(rows), m55.table(rows)
