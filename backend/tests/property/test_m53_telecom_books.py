"""M53 sub-task 2 property test (formulas.md 62.1-62.2): the books balance through builds, auctions
and wholesale sales. For any network (towers, radios, fibre, a cable), any auction bid, seed and
months: every ledger entry balances; a facility's capex paid equals the net 1500 postings for it
and its depreciation never passes it; spectrum's net 1540 postings equal the licences' carrying
value (price less amortization); and each network's cumulative cash equals its months'."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities import lifecycle
from tst.sim.ledger import CASH, PPE, SPECTRUM
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import with_product, with_segments
from tst.sim.telecom import phase, spectrum
from tst.sim.telecom.actions import BuildCable, BuildFibre, BuildTowers, apply_telecom

PLAYER = 1
NA = "north_america"


def _line(pid: int, category: str, segment: str, price: int, customers: float):  # type: ignore[no-untyped-def]
    p = Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=f"L{pid}",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )
    return p, ProductSegment(pid, segment, price, customers)


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    sites=st.sampled_from([100, 500, 1000]),
    homes=st.sampled_from([10, 50]),
    cable=st.booleans(),
    blocks=st.integers(min_value=0, max_value=4),
    limit_mult=st.floats(min_value=0.5, max_value=4.0),
    months=st.integers(min_value=1, max_value=40),
    mobile=st.floats(min_value=0, max_value=200_000),
    wholesale=st.floats(min_value=0, max_value=200),
)
def test_telecom_books_balance(
    loaded: LoadedData,
    seed: int,
    sites: int,
    homes: int,
    cable: bool,
    blocks: int,
    limit_mult: float,
    months: int,
    mobile: float,
    wholesale: float,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(2020, 10))
    founder = state.founder_of(PLAYER).id  # type: ignore[union-attr]
    balances = {(PLAYER, CASH): 10**16}
    for action in (
        BuildTowers(founder, NA, sites, "g4", "ericsson"),
        BuildFibre(founder, NA, homes),
        *([BuildCable(founder, "Atlantic", (NA, "europe"), 6600.0, 100)] if cable else []),
    ):
        state = apply_telecom(state, action, balances, b, d).state
        state = replace(state, person_states=fresh_game(loaded).person_states)  # energy back
    for pid, cat, seg, price, n in (
        (9001, b.telecom.mobile, "telecom_consumer", 4000, mobile),
        (9002, b.telecom.wholesale, "carriers", 100000, wholesale),
    ):
        p, row = _line(pid, cat, seg, price, n)
        state = with_segments(with_product(state, p), [row], [])
    a = d.telecom.auction("us_cband_2021")  # type: ignore[union-attr]
    assert a is not None
    auction = spectrum._from_def(a, 1, b.telecom.scale)
    auction = replace(
        auction,
        turn=state.turn + 2,
        bid_company_id=PLAYER if blocks else None,
        bid_blocks=blocks,
        bid_limit_cents=round(auction.reserve_cents * limit_mult * 4),
    )
    state = replace(state, telecom=replace(state.telecom, auctions=(auction,)))
    rng = RngFactory(seed)
    ppe = {f.id: 0 for f in state.facilities if f.company_id == PLAYER}
    spectrum_net = 0
    cash_months = 0
    for _ in range(months):
        for f in [x for x in state.facilities if x.company_id == PLAYER]:
            state, entries, _ = lifecycle.facility_month(state, f, b, d)
            for e in entries:
                assert sum(x.amount for x in e.lines) == 0
                ppe[f.id] += sum(x.amount for x in e.lines if x.account == PPE)
        state, entries, _ = phase.after_sales(state, rng, b, d)
        for e in entries:
            assert sum(x.amount for x in e.lines) == 0
            spectrum_net += sum(x.amount for x in e.lines if x.account == SPECTRUM)
        state, _ = phase.demand_month(state, rng, b, d)
        cash_months += sum(m.cash_cents for m in state.telecom.months if m.turn == state.turn)
        state = replace(state, turn=state.turn + 1)
    for f in state.facilities:
        if f.id in ppe:
            assert f.capex_paid_cents == ppe[f.id]
            assert 0 <= f.depreciated_cents <= f.capex_paid_cents
    carrying = sum(x.paid_cents - x.amortized_cents for x in state.telecom.licences)
    assert carrying == spectrum_net >= 0
    total = sum(c for _, _, c, _ in state.telecom.cash)
    assert total == cash_months
