"""M46 sub-task 1's target (nightly): a listed steady founder who hires to plan, with work for
every hire, ends 10 years at least 5% above one who leaves the cash idle (median, 10 seeds)."""

from __future__ import annotations

import os

import pytest

from tst.balance import m46


@pytest.mark.nightly
def test_listed_capital_pays() -> None:
    runs = m46.run(m46.SEEDS, int(os.environ.get("TST_BALANCE_JOBS", str(os.cpu_count() or 1))))
    for r in sorted(runs, key=lambda r: (r.seed, r.strategy)):
        print(
            f"seed {r.seed:2d} {r.strategy:15} ARR ${r.arr_cents / 1e8:7.1f}M cash "
            f"${r.cash_cents / 1e8:7.1f}M staff {r.staff:4d} listed {r.listed_turn}"
        )
    lift = m46.paired_lift(runs)
    print(f"M46 listed capital: planner / idle 10-year ARR, median paired {1 + lift:.3f}x")
    assert lift >= m46.TARGET_LIFT
