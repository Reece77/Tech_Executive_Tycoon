"""M40 sub-task 4 property test (formulas.md 56.1-56.3): the books balance through launches,
losses with insurance, and subscriptions. For any constellation plan (shells, satellites a month,
launches a month, own vehicle or bought, insured or not), seed, months and subscribers: every
ledger entry balances; the constellation's capitalized cost equals the net 1500 postings and its
accumulated depreciation the net 1510 postings, and never passes its cost; satellites are conserved
(built = in orbit + waiting + lost + retired); and the cumulative cash flow equals the month
records'."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tst.sim.actions  # noqa: F401
from tests.helpers import fresh_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.ledger import ACCUMULATED_DEPRECIATION, PPE
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.space import constellation as con
from tst.sim.space import services
from tst.sim.space.models import Constellation, LaunchSpec, Licence
from tst.sim.state import with_facility, with_product, with_segments

PLAYER = 1


def _facility(fid: int, kind: str, capacity: int) -> Facility:
    return Facility(
        id=fid,
        company_id=PLAYER,
        kind=kind,
        region="north_america",
        capacity=capacity,
        on_time=capacity,
        ordered_turn=0,
        ready_turn=0,
        late_turn=0,
        capex_cents=0,
        input_index=1.0,
        capex_paid_cents=0,
        status="live",
    )


def _product(pid: int, category: str) -> Product:
    return Product(
        id=pid,
        company_id=PLAYER,
        category=category,
        name=f"P{pid}",
        status="live",
        quality=60.0,
        feature_points=0.0,
        brand=50.0,
        marketing_budget_cents=0,
        created_turn=0,
        launched_turn=0,
    )


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    seed=st.integers(min_value=1, max_value=10_000),
    shells=st.integers(min_value=1, max_value=3),
    build=st.integers(min_value=0, max_value=60),
    launches=st.integers(min_value=0, max_value=4),
    own=st.booleans(),
    insured=st.booleans(),
    life=st.integers(min_value=36, max_value=48),
    months=st.integers(min_value=1, max_value=60),
    subscribers=st.floats(min_value=0, max_value=50_000),
    year=st.integers(min_value=2015, max_value=2035),
)
def test_space_books_balance(
    loaded: LoadedData,
    seed: int,
    shells: int,
    build: int,
    launches: int,
    own: bool,
    insured: bool,
    life: int,
    months: int,
    subscribers: float,
    year: int,
) -> None:
    b, d = loaded.balance, loaded.game_data
    state = replace(fresh_game(loaded), turn=ym_to_turn(year, 1))
    state = with_product(state, _product(9001, b.space.broadband))
    state = with_product(state, _product(9002, b.space.launch))
    state = with_segments(state, [ProductSegment(9001, "consumer", 9000, subscribers)], [])
    state = with_facility(state, _facility(8001, b.space.plant_kind, 25))
    state = with_facility(state, _facility(8002, b.space.site_kind, 2))
    spec = LaunchSpec(9002, PLAYER, 20_000.0, "expendable")
    c = Constellation(
        id=1,
        company_id=PLAYER,
        name="Ring",
        kind="broadband",
        product_id=9001,
        shells=shells,
        mass_kg=300.0,
        life_months=life,
        d2d=False,
        insured=insured,
        build_per_month=build,
        launches_per_month=launches,
        vehicle_product_id=9002 if own else None,
        created_turn=state.turn,
    )
    lic = tuple(Licence(PLAYER, r, "granted", state.turn, None, state.turn) for r in d.region_keys)
    state = replace(
        state, space=replace(state.space, constellations=(c,), launch_specs=(spec,), licences=lic)
    )
    rng = RngFactory(seed)
    ppe = acc = 0
    built = lost = retired = 0
    cash = 0
    for _ in range(months):
        state, entries, revenue = services.books(state, {}, b, d)
        for e in entries:
            assert sum(line.amount for line in e.lines) == 0
        state, more, _, _, _ = con.month(state, rng, b, d, revenue, {})
        for e in more:
            assert sum(line.amount for line in e.lines) == 0
            for line in e.lines:
                if e.memo.startswith("Constellation "):
                    if line.account == PPE:
                        ppe += line.amount
                    elif line.account == ACCUMULATED_DEPRECIATION:
                        acc -= line.amount
        x = state.space.constellations[0]
        assert x.month is not None
        built += x.month.built
        lost += x.month.lost
        retired += x.month.retired
        cash += x.month.cash_cents
        state = replace(state, turn=state.turn + 1)
    x = state.space.constellations[0]
    assert x.capex_cents == ppe
    assert x.depreciated_cents == acc
    assert 0 <= x.depreciated_cents <= x.capex_cents
    assert built == x.in_orbit() + x.ground + lost + retired
    assert x.cash_cents == cash
