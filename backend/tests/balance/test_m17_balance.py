"""docs/formulas.md 33.6 targets (M17), nightly; tools/m17_targets.py prints the same. Values
recorded in docs/balance-targets.md (M17) and the M17 brief. Target 6 is the golden snapshots."""

from __future__ import annotations

import pytest

from tst.balance import m17


@pytest.mark.nightly
def test_33_6_targets() -> None:
    r = m17.run(m17.SEEDS)
    print(m17.report(r))
    assert r.mismatches == 0  # target 1 (the API half: tests/integration/test_api_commodities.py)
    assert 0.03 <= r.phone.rise <= 0.08  # target 2
    assert all(h.gap >= 0.03 for h in r.hedges)  # target 3
    cheapest = min(r.power.values())
    assert cheapest <= 0.85 and r.power["north_america"] == 1.0  # target 4
    assert all(6 <= n <= 10 for n in m17.shocked_seeds(r).values())  # target 5
    assert max(max(f.longest_above.values()) for f in r.futures) <= 36
