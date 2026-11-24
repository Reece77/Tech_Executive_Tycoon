"""M49's 61.3 targets 2-4 (nightly; tst.balance.m49): one-to-ones keep at least 30% of the
approached people a rival would win on skip, a broken promised promotion costs at least 8 morale
and doubles the chance of leaving, and candour in a class I recall regains the brand at least
1.25x as fast as deflection, which alone risks an inspection. The full run is
`python -m tst.balance.m49`, printed in the brief."""

from __future__ import annotations

import os

import pytest

from tst.balance import m49


@pytest.mark.nightly
def test_61_3_targets_2_to_4() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m49.run(m49.SEEDS, jobs)
    print(m49.report(results))
    assert m49.met(results) == {"t2": True, "t3": True, "t4": True}, m49.report(results)
