"""docs/formulas.md 18.9 targets 4 and 6 (M8): Fintech earns, AI demand follows its table and
every entrant is founded in its month. Targets 2, 3 and 5 are in tst.balance.m8 (nightly)."""

from __future__ import annotations

import statistics

import pytest

from tests.balance_scripts import FINTECH_PRICES, earn_and_burn
from tst.loader import LoadedData
from tst.sim.money import format_money

ARR_TURN = 36
SEEDS = range(1, 11)
BAND = (0.5, 1.5)  # fintech ARR / B2B SaaS ARR at turn 36 (18.9 target 4)


@pytest.mark.nightly
def test_fintech_earn_and_burn_band(loaded: LoadedData) -> None:
    ratios = []
    for seed in SEEDS:
        b2b = earn_and_burn(loaded, seed, ARR_TURN + 1).snapshots[ARR_TURN].arr_cents
        fin = (
            earn_and_burn(loaded, seed, ARR_TURN + 1, category="fintech", prices=FINTECH_PRICES)
            .snapshots[ARR_TURN]
            .arr_cents
        )
        ratios.append(fin / b2b if b2b else 0.0)
        print(f"seed {seed}: B2B SaaS {format_money(b2b)}, fintech {format_money(fin)}")
    median = statistics.median(ratios)
    print(f"18.9 target 4: fintech / B2B SaaS ARR at turn {ARR_TURN}, median {median:.2f}")
    assert BAND[0] <= median <= BAND[1]
