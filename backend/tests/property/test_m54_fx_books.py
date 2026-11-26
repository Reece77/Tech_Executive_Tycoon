"""M54 sub-task 2 property test (formulas.md 64.4, ADR-0025): the books balance through translation
and hedge settlement. For any forwards (regions, notionals, terms), seed and months from 2026: every
entry balances; nothing is booked before settlement (M54 decision 10); cash moves only at
settlement, by exactly the settled gains, and the gain and loss lines sum to them. Translated prices
are integers within one cent of price x ratio."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.fx import hedges, rates, translate
from tst.sim.fx.hedges import FX_GAINS, FX_LOSSES
from tst.sim.ledger import CASH
from tst.sim.rng import RngFactory

PLAYER = 1
FOREIGN = ("europe", "east_asia", "south_southeast_asia", "latin_america", "africa", "oceania")


@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    forwards=st.lists(
        st.tuples(
            st.sampled_from(FOREIGN),
            st.integers(min_value=1, max_value=10**12),
            st.integers(min_value=1, max_value=12),
            st.integers(min_value=0, max_value=6),
        ),
        min_size=1,
        max_size=6,
    ),
    months=st.integers(min_value=1, max_value=20),
)
def test_hedge_books_balance(
    loaded: LoadedData, seed: int, forwards: list[tuple[str, int, int, int]], months: int
) -> None:
    b, d = loaded.balance, loaded.game_data
    rng = RngFactory(seed)
    start = b.fx.start_turn
    state = replace(fresh_game(loaded), turn=start)
    net = {CASH: 0, FX_GAINS: 0, FX_LOSSES: 0}
    settled_total = 0
    for k in range(months):
        state = rates.walk_month(replace(state, turn=start + k), rng, b, d)
        for region, notional, term, when in forwards:
            if when == k:
                state, _ = hedges.buy(state, PLAYER, region, notional, term, b, d)
        state, entries, settled = hedges.mark_and_settle(state, b, d)
        settled_total += sum(settled.values())
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            for x in e.lines:
                net[x.account] = net.get(x.account, 0) + x.amount
    assert set(net) == {CASH, FX_GAINS, FX_LOSSES}
    assert net[CASH] == settled_total
    assert -(net[FX_GAINS] + net[FX_LOSSES]) == settled_total
    assert settled_total == sum(h.settled_cents for h in state.fx.hedges)


@settings(max_examples=200, deadline=None)
@given(
    price=st.integers(min_value=1, max_value=10**9),
    now=st.integers(min_value=1, max_value=10**7),
    then=st.integers(min_value=1, max_value=10**7),
)
def test_translated_price_is_exact(price: int, now: int, then: int) -> None:
    out = translate.translated(price, now, then)
    assert isinstance(out, int)
    assert abs(Fraction(out) - Fraction(price * now, then)) <= Fraction(1, 2)
