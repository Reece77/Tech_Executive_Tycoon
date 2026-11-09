"""docs/formulas.md 37.6 targets (M26), nightly; tools/m26_targets.py prints the same. Values
recorded in the M26 brief ("Decisions made") and docs/balance-targets.md."""

from __future__ import annotations

import os

import pytest

from tst.balance import m26


@pytest.mark.nightly
def test_37_6_targets() -> None:
    jobs = int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1)))
    r = m26.run(m26.SEEDS, jobs)
    print(m26.report(r))
    median, top, _, portfolio, _ = m26.target_1(r)
    assert median < 1.0 and top > 10 and 0.8 <= portfolio <= 3.0  # target 1
    _, _, ratio, _, _ = m26.target_2(r)
    assert ratio is not None and ratio >= 1.3  # target 2
    _, _, miss, vol = m26.target_3(r)
    assert miss <= 4 and vol["aggressive"] >= 1.5 * vol["conservative"]  # target 3
    assert 6 <= m26.target_4(r) <= 10  # target 4
    assert all(r.same)  # target 5
