"""docs/formulas.md 38.5 targets (M21), nightly; tools/m21_targets.py prints the same. Values
recorded in docs/balance-targets.md (M21) and the M21 brief. Target 6 is also
tests/unit/test_m21_fabs.py and the golden snapshots."""

from __future__ import annotations

import os

import pytest

from tst.balance import m21


@pytest.mark.nightly
def test_38_5_targets() -> None:
    r = m21.run(tuple(m21.seeds(10)), os.cpu_count() or 1)
    print(m21.report(r))
    assert all(m21.checks(r).values())
