"""Product invariants over random teams and products (formulas.md 11.3-11.8).

Development: quality and brand stay in [0, 100], output is never negative (feature points
never fall), and a product nobody works on only loses quality. Market: customers are never
negative, a segment's customers never exceed its addressable demand, and every ledger entry
balances in integer cents.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.conftest import DATA_DIR
from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import load_all
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, apply_entries
from tst.sim.products.phases import brand_and_demand, develop
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person
from tst.sim.turn import advance_turn

LOADED = load_all(DATA_DIR)
BASE = fresh_game(LOADED)
PRODUCT = 13
ROLES = ("software_engineer", "designer", "marketer", "account_executive", "recruiter")
TAGS = ("quiet_genius", "toxic_high_performer", "perfectionist", "maverick", "politician", "")


@st.composite
def teams(draw: st.DrawFn) -> GameState:
    state = BASE
    for pid in range(2, 2 + draw(st.integers(min_value=0, max_value=12))):
        role = draw(st.sampled_from(ROLES))
        person = make_person(LOADED, pid, role)
        tag = draw(st.sampled_from(TAGS))
        skill = draw(st.floats(min_value=1, max_value=20))
        skills = person.skills.updated(dict.fromkeys(person.skills.keys(), skill))
        person = replace(person, tags=(tag,) if tag else (), skills=skills)
        morale = draw(st.floats(min_value=0, max_value=100))
        state = with_employee(LOADED, state, person, 9_000_000, morale=morale)
        state = with_person(state, person)
    category = draw(st.sampled_from([c.key for c in LOADED.game_data.categories]))
    segment = LOADED.game_data.category(category).segment_keys[0]
    return with_product(
        state,
        category=category,
        prices={segment: 1000},
        status=draw(st.sampled_from(["in_development", "live"])),
        quality=draw(st.floats(min_value=0, max_value=100)),
        brand=draw(st.floats(min_value=0, max_value=100)),
        budget_cents=draw(st.integers(min_value=0, max_value=50_000_000)),
        root=draw(st.booleans()),
    )


def months(state: GameState, seed: int, turns: int) -> list[GameState]:
    rng = RngFactory(seed)
    out = []
    for _ in range(turns):
        state, _ = develop(state, rng, LOADED.balance, LOADED.game_data)
        state = brand_and_demand(state, LOADED.balance, LOADED.game_data)
        out.append(state)
        state = replace(state, turn=state.turn + 1)
    return out


@settings(max_examples=60, deadline=None)
@given(teams(), st.integers(min_value=0, max_value=2**32))
def test_scores_stay_in_range_and_output_is_never_negative(state: GameState, seed: int) -> None:
    before = state.product(PRODUCT)
    assert before is not None
    points = before.feature_points
    for month in months(state, seed, 6):
        product = month.product(PRODUCT)
        assert product is not None
        assert 0 <= product.quality <= 100
        assert 0 <= product.brand <= 100
        assert product.feature_points >= points  # o >= 0
        points = product.feature_points


@settings(max_examples=40, deadline=None)
@given(teams(), st.integers(min_value=0, max_value=2**32))
def test_a_product_with_no_units_only_loses_quality(state: GameState, seed: int) -> None:
    state = replace(
        state, companies=(replace(state.player, root_product_id=None), *state.companies[1:])
    )
    before = state.product(PRODUCT)
    assert before is not None
    quality, points = before.quality, before.feature_points
    for month in months(state, seed, 6):
        product = month.product(PRODUCT)
        assert product is not None
        assert product.quality <= quality and product.feature_points == points
        quality = product.quality


# --- Market (11.7, 11.8) --------------------------------------------------------------------


@st.composite
def markets(draw: st.DrawFn) -> GameState:
    """One to three player products with random scores, prices and customers."""
    state = draw(teams())
    for i in range(draw(st.integers(min_value=0, max_value=2))):
        category = draw(st.sampled_from([c.key for c in LOADED.game_data.categories]))
        cat = LOADED.game_data.category(category)
        segs = draw(st.lists(st.sampled_from(cat.segment_keys), min_size=1, unique=True))
        prices = {s: draw(st.integers(min_value=1, max_value=2_000_000)) for s in segs}
        demand = {s: cat.market(s).addressable for s in segs}
        state = with_product(
            state,
            category=category,
            prices=prices,  # type: ignore[arg-type]
            status=draw(st.sampled_from(["live", "sunset", "in_development"])),
            quality=draw(st.floats(min_value=0, max_value=100)),
            brand=draw(st.floats(min_value=0, max_value=100)),
            feature_points=draw(st.floats(min_value=0, max_value=500)),
            customers={s: draw(st.floats(min_value=0, max_value=0.1)) * demand[s] for s in segs},
            root=False,
            name=f"P{i}",
        )
    return state


@settings(max_examples=40, deadline=None)
@given(markets(), st.integers(min_value=0, max_value=2**32))
def test_customers_stay_within_demand_and_entries_balance(state: GameState, seed: int) -> None:
    balances = {(1, CASH): 10**12}  # flows, not solvency (bankruptcy since M4, 14.7)
    for _ in range(4):
        result = advance_turn(
            state, Decisions(), RngFactory(seed), LOADED.balance, LOADED.game_data, balances
        )
        state = result.new_state
        for entry in result.ledger_entries:
            assert sum(line.amount for line in entry.lines) == 0
            assert all(isinstance(line.amount, int) for line in entry.lines)
        balances = dict(apply_entries(balances, result.ledger_entries))
        products = {p.id: p for p in state.products}
        totals: dict[tuple[str, str], float] = {}
        for seg in state.product_segments:
            assert seg.customers >= 0
            product = products[seg.product_id]
            key = (product.category, seg.segment)
            totals[key] = totals.get(key, 0.0) + seg.customers
        for (category, segment), total in totals.items():
            market = state.market(category, segment)
            assert market is not None
            assert total <= market.addressable * (1 + 1e-9)
