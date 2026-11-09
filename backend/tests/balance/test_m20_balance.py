"""docs/formulas.md 36.5 targets (M20), nightly; tools/m20_targets.py prints the same. Values
recorded in docs/balance-targets.md (M20) and the M20 brief. Target 5 is the golden snapshots
and tests/unit/test_m20_plants.py."""

from __future__ import annotations

import os

import pytest

from tst.balance import m20


@pytest.mark.nightly
def test_36_5_targets() -> None:
    r = m20.run(tuple(m20.seeds(10)), os.cpu_count() or 1)
    print(m20.report(r))
    assert all(0.02 <= p.median_margin <= 0.15 for p in r.margins.values())  # target 1
    assert 0.20 <= r.power.saving <= 0.40  # target 2
    assert all(0.10 <= w.mean_saving <= 0.25 for w in r.wafers)  # target 3
    assert all(min(w.shortage_delivered) >= 1 - 1e-9 for w in r.wafers)
    assert r.bans  # target 4: at least one gallium export ban on seeds 1-10
    assert all(b.group_gallium_rise <= 0.10 and b.spot_gallium_rise >= 0.30 for b in r.bans)
