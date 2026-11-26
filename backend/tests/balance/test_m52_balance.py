"""M52's 66.4 targets (tst.balance.m52). Target 1 is M30's state cache, the golden snapshots and
M45's dynasty fixture (their own tests). Target 2 (nightly): every scenarios.yaml entry opened in
the editor and saved unchanged starts a game identical to the original's to month 12 on seeds
1-3. Target 4 (weekly): a 2069 dynasty game continued in sandbox runs to December 2100 on seeds
1-3 with no error, every integer within SQLite's signed 64-bit column and the 2100 economy at
least 1,000x below it. Target 3 is the determinism job (tools/platform_digests.py). The full
runs are `tools/m52_targets.py`, printed in the brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m52
from tst.balance.known_misses import Reading, verdict

ECONOMY = "M52.economy_2100"


def _jobs() -> int:
    return int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))


@pytest.mark.nightly
def test_66_4_target_2_every_scenario_round_trips() -> None:
    runs = m52.round_trips(workers=_jobs())
    bad = [r for r in runs if not r.identical]
    assert len(runs) == 11 * len(m52.SEEDS)
    assert bad == [], bad


@pytest.mark.weekly
def test_66_4_target_4_sandbox_to_2100() -> None:
    runs = m52.long_play(workers=min(_jobs(), len(m52.SEEDS)))
    for r in runs:
        print(r)
    for r in runs:
        assert r.error is None, r
        assert r.reached == "Dec 2100" and r.ended == "active", r
        assert r.largest_int < m52.INT64, r
        score = r.revenue_2100 * m52.ECONOMY_MARGIN / m52.INT64
        reading = Reading(ECONOMY, score <= 1, score, str(r))
        assert verdict(reading) != "fail", r  # Reece (2026-11-26): a known miss within its bound
