"""docs/formulas.md 21.8 targets 2, 3 and 5 (M11), nightly; tools/m11_targets.py prints the
same. Targets 1 and 4 are unit tests. Values recorded in the M11 brief and
docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m11


@pytest.mark.nightly
def test_21_8_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    results = m11.run(m11.SEEDS, jobs)
    print(m11.report(results))
    net, _, gain = m11.target_2(results)
    assert net >= 1.10 and gain >= 5  # target 2
    assert m11.target_3a(results) >= 5  # target 3
    assert m11.target_3b(results) <= 0.15
    five = m11.target_5(results)
    assert five is not None and five <= 0.7  # target 5
