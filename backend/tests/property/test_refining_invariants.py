"""M20 (formulas.md 36): through refining the ledger balances and the plants' books hold, for
any recipe, region, start month and length. Every LedgerEntry checks its own balance when built;
these check what that cannot: cash moves exactly by the plants' posted costs and sales, output
stays within capacity and goes somewhere, and book value is never negative."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tst.balance import m20
from tst.sim.calendar import ym_to_turn
from tst.sim.ledger import CASH
from tst.sim.refining.phase import refining_month
from tst.sim.refining.plants import refinery_of
from tst.sim.rng import RngFactory

RECIPES = [k for k in m20.loaded().balance.refining.order if not k.startswith("byproduct_")]
REGIONS = list(m20.loaded().game_data.region_keys)
EPS = 1e-6


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    recipe=st.sampled_from(RECIPES),
    region=st.sampled_from(REGIONS),
    year=st.integers(min_value=2012, max_value=2024),
    months=st.integers(min_value=1, max_value=8),
    staffed=st.booleans(),
)
def test_refining_keeps_its_books(
    recipe: str, region: str, year: int, months: int, staffed: bool
) -> None:
    b = m20.loaded().balance
    kind = b.facility.kinds[b.refining.recipes[recipe].kind]
    size = (kind.sizes or b.facility.sizes)[0]
    game = m20.game_at(7, ym_to_turn(year, 1))
    fid = m20.build(game, recipe, region, size)
    if not staffed:
        f = game.state.facility(fid)
        assert f is not None
        game.state = m20.with_facility(game.state, replace(f, unit_id=None))
    lg = m20.loaded()
    for _ in range(months):
        # the phase alone: its cash lines are exactly sales less what it bought and burned
        state, entries, _ = refining_month(game.state, RngFactory(7), lg.balance, lg.game_data)
        cash = sum(x.amount for e in entries for x in e.lines if x.account == CASH)
        pm = refinery_of(state, fid).month  # type: ignore[union-attr]
        assert pm is not None
        burned = pm.input_cents + pm.power_cents + pm.other_cents + pm.fixed_cents
        assert cash == pm.revenue_cents - burned  # one company, no group input: all bought
        game.turn()
        ref = refinery_of(game.state, fid)
        f = game.state.facility(fid)
        assert ref is not None and f is not None and ref.month is not None
        pm = ref.month
        assert f.book_value_cents >= 0
        assert 0 <= pm.output <= pm.capacity + EPS
        assert pm.to_group + pm.to_contract + pm.to_spot == pytest.approx(pm.output, abs=1e-3)
        assert min(pm.input_group, pm.input_contract, pm.input_spot, pm.input_short) >= 0
        assert pm.input_cents >= 0 and pm.power_cents >= 0 and pm.revenue_cents >= 0
        if not staffed:
            assert pm.output == 0
