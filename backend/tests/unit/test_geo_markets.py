"""M9 regional markets and rivals (docs/formulas.md 19.4-19.6)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import FIRST_PRODUCT, fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim.actions import Action, ActionResult, apply_action
from tst.sim.actions.geo import LaunchInRegion, LeaseOffice, SetRegionalPrice, launch_problem
from tst.sim.errors import GeoRuleError, InsufficientCashError
from tst.sim.geo.markets import reach_context
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.ledger import CASH, RESEARCH
from tst.sim.org.rules import org_view
from tst.sim.products.phases import develop, run_markets
from tst.sim.products.team import product_team
from tst.sim.rivals.decisions import choose, enter_region, region_candidates
from tst.sim.rivals.startups import founding_region
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person, with_regional_segment

FOUNDER = 1
PRODUCT = FIRST_PRODUCT
CASH_START = 150_000_000


def _act(
    loaded: LoadedData, state: GameState, action: Action, cash: int = CASH_START
) -> ActionResult:
    return apply_action(
        state, action, RngFactory(1), loaded.balance, loaded.game_data, {(1, CASH): cash}, seq=1
    )


def _live(loaded: LoadedData) -> GameState:
    return with_product(
        fresh_game(loaded), quality=60.0, brand=40.0, feature_points=200.0, prices={"smb": 4000}
    )


def _strip_regions(state: GameState) -> GameState:
    return replace(state, regional_markets=(), product_regions=(), regional_segments=())


def test_home_region_replays_v1(loaded: LoadedData) -> None:
    """19.5: the home region keeps v1's D0, prices, incumbents and `market` keys, so other
    regions' markets change nothing at home."""
    b, data = loaded.balance, loaded.game_data
    state = _live(loaded)
    assert state.regional_segments  # v1 incumbents also sell in Europe, regional ones abroad
    with_regions = run_markets(state, RngFactory(9), b, data)
    without = run_markets(_strip_regions(state), RngFactory(9), b, data)
    assert with_regions.state.product_segments == without.state.product_segments
    assert with_regions.state.markets == without.state.markets
    assert {k: v for k, v in with_regions.flows.items()} == without.flows
    # Rivals' revenue includes their regional sales; the player has none abroad.
    assert with_regions.revenue[1] == without.revenue[1]
    sap = next(c for c in state.companies if c.name == "SAP")
    assert without.revenue.get(sap.id, 0) == 0 < with_regions.revenue[sap.id]


def test_launch_in_region(loaded: LoadedData) -> None:
    """Energy 4, $80,000 x 6 / 6 = $80,000 to R&D, live six months later at p_ref x 0.9 (M10d)."""
    state = _live(loaded)
    energy = state.person_state(FOUNDER).energy or 0
    out = _act(loaded, state, LaunchInRegion(FOUNDER, PRODUCT, "europe"))
    after = out.new_state
    assert after.person_state(FOUNDER).energy == energy - 4
    assert after.product_region(PRODUCT, "europe") == ProductRegion(PRODUCT, "europe", 0, 6)
    (seg,) = after.regional_segments_of(PRODUCT, "europe")
    assert (seg.segment, seg.price_cents, seg.customers) == ("smb", 4_500, 0.0)
    (entry,) = out.ledger_entries
    assert {line.account: line.amount for line in entry.lines} == {
        RESEARCH: 8_000_000,
        CASH: -8_000_000,
    }
    assert out.log_items[0].template == "region_launched"
    again = launch_problem(after, PRODUCT, "europe", loaded.balance, loaded.game_data)
    assert again == "it has already launched there"


@pytest.mark.parametrize(
    ("region", "problem"),
    [("north_america", "home region"), ("mars", "unknown region")],
)
def test_launch_rules(loaded: LoadedData, region: str, problem: str) -> None:
    with pytest.raises(GeoRuleError, match=problem):
        _act(loaded, _live(loaded), LaunchInRegion(FOUNDER, PRODUCT, region))


def test_launch_needs_a_live_product_and_cash(loaded: LoadedData) -> None:
    building = with_product(fresh_game(loaded), status="in_development")
    with pytest.raises(GeoRuleError, match="live at home"):
        _act(loaded, building, LaunchInRegion(FOUNDER, PRODUCT, "europe"))
    with pytest.raises(InsufficientCashError):
        _act(loaded, _live(loaded), LaunchInRegion(FOUNDER, PRODUCT, "europe"), cash=100)


def test_regional_price_and_selling_only_once_live(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _act(loaded, _live(loaded), LaunchInRegion(FOUNDER, PRODUCT, "europe")).new_state
    state = _act(
        loaded, state, SetRegionalPrice(FOUNDER, PRODUCT, "europe", "smb", 3_900)
    ).new_state
    assert state.regional_segments_of(PRODUCT, "europe")[0].price_cents == 3_900
    localizing = run_markets(state, RngFactory(2), b, data).state
    assert localizing.regional_segments_of(PRODUCT, "europe")[0].customers == 0.0
    live = run_markets(replace(state, turn=b.markets.localize_months), RngFactory(2), b, data).state
    assert live.regional_segments_of(PRODUCT, "europe")[0].customers > 0


def test_local_presence_regions(loaded: LoadedData) -> None:
    """Presence (an office or 5 people) still counts for sales-led reach; self-serve needs none
    since M10b (23.5: foreign_awareness 1.0)."""
    b, data = loaded.balance, loaded.game_data
    state = _live(loaded)
    geo = reach_context(state, b, data)
    assert geo is not None
    assert geo.awareness_factor(1, "europe") == 1.0 == b.markets.foreign_awareness
    assert "europe" not in geo.present
    leased = _act(loaded, state, LeaseOffice(FOUNDER, "london", 25)).new_state
    geo = reach_context(leased, b, data)
    assert geo is not None and "europe" in geo.present
    remote = replace(
        state, companies=(replace(state.player, work_policy="remote"), *state.companies[1:])
    )
    for pid in range(2, 7):
        person = replace(make_person(loaded, pid), city="berlin")
        remote = with_employee(loaded, remote, person, 6_000_000)
    geo = reach_context(remote, b, data)
    assert geo is not None and "europe" in geo.present


def test_sellers_sell_where_they_work(loaded: LoadedData) -> None:
    """Sales-led capacity in a region: its sellers, plus half of its neighbour's (19.5)."""
    b, data = loaded.balance, loaded.game_data
    state = with_product(
        fresh_game(loaded), prices={"mid_market": 70_000}, quality=60.0, feature_points=200.0
    )
    state = replace(
        state, companies=(replace(state.player, work_policy="remote"), *state.companies[1:])
    )
    for pid, city in ((2, "london"), (3, "san_francisco"), (4, "sao_paulo")):
        person = replace(make_person(loaded, pid, role="account_executive"), city=city)
        state = with_employee(loaded, state, person, 9_000_000)
    geo = reach_context(state, b, data)
    assert geo is not None
    assert geo.seller_weights([2, 3, 4], "europe") == {2: 1.0}
    assert geo.seller_weights([2, 3, 4], "north_america") == {3: 1.0, 4: 0.5}
    assert geo.seller_weights([2, 3, 4], "africa") == {2: 0.5}


def test_cross_region_factor_on_a_split_team(loaded: LoadedData) -> None:
    """19.8 target 3 (factor): builders in two regions lose 5% of output (19.4)."""
    b, data = loaded.balance, loaded.game_data
    state = _live(loaded)
    for pid in (2, 3):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    product = state.product(PRODUCT)
    assert product is not None
    one = product_team(state, org_view(state, 1), product, data.category("b2b_saas"), b, data)
    assert (one.builder_regions, one.region_factor) == (1, 1.0)
    remote = replace(
        state, companies=(replace(state.player, work_policy="remote"), *state.companies[1:])
    )
    remote = with_person(remote, replace(remote.person(3), city="bangalore"))
    two = product_team(remote, org_view(remote, 1), product, data.category("b2b_saas"), b, data)
    assert (two.builder_regions, two.region_factor) == (2, pytest.approx(0.95))
    assert two.base_output(b) < one.base_output(b)


def test_localizing_slows_feature_growth(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = _live(loaded)
    for pid in (2, 3):
        state = with_employee(loaded, state, make_person(loaded, pid), 9_000_000)
    launched = _act(loaded, state, LaunchInRegion(FOUNDER, PRODUCT, "europe")).new_state
    plain, _ = develop(state, RngFactory(5), b, data)
    slow, _ = develop(launched, RngFactory(5), b, data)
    start = state.product(PRODUCT)
    a, c = plain.product(PRODUCT), slow.product(PRODUCT)
    assert start is not None and a is not None and c is not None
    gained, slowed = (
        a.feature_points - start.feature_points,
        c.feature_points - start.feature_points,
    )
    assert slowed == pytest.approx(gained * 0.9)


def test_rivals_enter_empty_regions(loaded: LoadedData) -> None:
    """19.6: need (unserved - 0.4) / 0.4 with cash for 12 months, weighted as enter_segment."""
    b, data = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    salesforce = next(c for c in state.companies if c.name == "Salesforce")
    product = state.company_products(salesforce.id)[0]
    rich = {(salesforce.id, CASH): 10**13}
    found = region_candidates(state, salesforce, 100.0, b, data)
    regions = [c.segment for c in found]
    assert "europe" not in regions and "north_america" not in regions
    assert {c.segment: c.need for c in found}["east_asia"] == pytest.approx(1.0)
    poor = region_candidates(state, salesforce, 6.0, b, data)
    assert all(c.need == 0 for c in poor)
    chosen = None
    for seed in range(40):
        gen = RngFactory(seed).stream(0, "misc", seed)
        pick = choose(state, salesforce, gen, rich, b, data)
        if pick is not None and pick[0].action == "enter_region":
            chosen = pick[0]
            break
    assert chosen is not None and chosen.product_id == product.id
    after, words = enter_region(state, salesforce, product, "east_asia", b, data)
    assert words.startswith("entered East Asia")
    rows = after.regional_segments_of(product.id, "east_asia")
    assert {r.segment for r in rows} == {"smb", "mid_market", "enterprise"}
    assert after.product_region(product.id, "east_asia") is not None


def test_startup_founding_region_is_seeded(loaded: LoadedData) -> None:
    b, data = loaded.balance, loaded.game_data
    state = fresh_game(loaded)
    category = data.category("consumer_apps")
    picks = [founding_region(state, RngFactory(s), 99, category, b, data) for s in range(300)]
    assert picks == [
        founding_region(state, RngFactory(s), 99, category, b, data) for s in range(300)
    ]
    share = picks.count("north_america") / len(picks)
    assert 0.2 < share < 0.4  # 1.00 of 3.31 regional size
    assert set(picks) <= set(data.region_keys) and len(set(picks)) >= 5


def test_regional_rows_hold_customers(loaded: LoadedData) -> None:
    state = _live(loaded)
    seg = RegionalSegment(PRODUCT, "oceania", "smb", 4_000, customers=12.0)
    state = with_regional_segment(state, seg)
    assert state.regional_segments_of(PRODUCT, "oceania") == (seg,)
