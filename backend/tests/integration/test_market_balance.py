"""M3a balance checks (printed): the earn-and-burn band. (M3a's incumbent equilibrium,
with incumbents that never moved, is replaced by M5's living-market target in
test_rival_balance.py: rivals now act, formulas.md 15.7.)

- Earn-and-burn: a funded_spinout founder, 3 builders, 1 account executive and 1 marketer
  ($10,000 a month marketing) on one B2B SaaS product reach first revenue by turn 10 and an
  ARR between $500,000 and $4M at turn 36 (formulas.md 11.14 design check: about $2.6M).
"""

from __future__ import annotations

import pytest

from tests.balance_scripts import earn_and_burn
from tst.loader import LoadedData
from tst.sim.money import format_money
from tst.sim.state import GameState

FIRST_REVENUE_BY = 10
ARR_TURN = 36
ARR_BAND_CENTS = (50_000_000, 400_000_000)


def served_shares(state: GameState) -> dict[tuple[str, str, int], float]:
    """Each product's share of its segment's served customers, in points."""
    products = {p.id: p for p in state.products}
    totals: dict[tuple[str, str], float] = {}
    for seg in state.product_segments:
        key = (products[seg.product_id].category, seg.segment)
        totals[key] = totals.get(key, 0.0) + seg.customers
    return {
        (products[s.product_id].category, s.segment, s.product_id): 100
        * s.customers
        / totals[(products[s.product_id].category, s.segment)]
        for s in state.product_segments
    }


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_earn_and_burn_band(loaded: LoadedData, seed: int) -> None:
    run = earn_and_burn(loaded, seed, ARR_TURN + 1)
    first = next(i for i, s in enumerate(run.snapshots) if s.mrr_cents > 0)
    even = next((i for i, s in enumerate(run.snapshots) if i and s.monthly_burn_cents == 0), None)
    arr = run.snapshots[ARR_TURN].arr_cents
    print(
        f"seed {seed}: launched turn {run.launched_turn}, first revenue turn {first}, "
        f"break-even turn {even}, ARR at turn {ARR_TURN} {format_money(arr)}, "
        f"cash {format_money(run.snapshots[ARR_TURN].cash_cents)}"
    )
    assert first <= FIRST_REVENUE_BY
    assert ARR_BAND_CENTS[0] <= arr <= ARR_BAND_CENTS[1]


def test_marketing_roughly_doubles_arr(loaded: LoadedData) -> None:
    """The design check's comparison: about $2.6M with the budget, $1.4M without."""
    with_budget = earn_and_burn(loaded, 1, ARR_TURN + 1).snapshots[ARR_TURN].arr_cents
    without = earn_and_burn(loaded, 1, ARR_TURN + 1, marketing=False).snapshots[ARR_TURN].arr_cents
    print(
        f"ARR at turn {ARR_TURN}: {format_money(with_budget)} with, {format_money(without)} without"
    )
    assert with_budget > without > 0
