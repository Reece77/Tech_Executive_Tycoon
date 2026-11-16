"""docs/formulas.md 46.8 (M32): targets 2-5 over seeds 1-10 (nightly), and target 1, history
holds, against main's fixture (seed 1 of each strategy in `make check`'s nightly set; all ten
seeds nightly)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m32, m32_history


@pytest.mark.nightly
def test_targets_2_to_5() -> None:
    results = m32.run(m32.SEEDS, os.cpu_count() or 1)
    assert m32.checks(results) == {2: True, 3: True, 4: True, 5: True}, m32.report(results)


@pytest.mark.nightly
def test_history_holds_on_every_seed() -> None:
    runs = m32_history.history_all(workers=os.cpu_count() or 1)
    want = m32_history.recorded_history()
    assert m32_history.cost_diffs(runs, want) == []
    assert m32_history.book_diffs(runs, want) == []
