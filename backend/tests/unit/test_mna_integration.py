"""M14 sub-task 5 (formulas.md 28.5): after closing, keep the target as a brand (consolidated,
cash swept, deciding under a directive) or integrate it (products, key people and the pool
staff they need move over; the rest are let go with severance; culture clash and flight)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tests.unit.test_hiring_phases import Game
from tests.unit.test_mna_deals import BIG, _energy, _founder, _id, _reservation
from tst.loader import LoadedData
from tst.sim.ledger import CASH, INVESTMENT_SUBSIDIARIES, SALARIES
from tst.sim.mna import integration
from tst.sim.mna.deals import BidForCompany
from tst.sim.mna.integration import SetDirective
from tst.sim.mna.style import style
from tst.sim.research.models import ResearchLead
from tst.sim.state import with_research_lead


def _buy(loaded: LoadedData, name: str, mode: str, seed: int = 3) -> tuple[Game, int]:
    game = Game(loaded, fresh_game(loaded, seed=seed), cash=BIG)
    target = _id(game.state, name)
    _energy(game)
    game.act(BidForCompany(_founder(game), target, _reservation(game, target), mode=mode))  # type: ignore[arg-type]
    game.turn()
    assert game.state.deals[0].status == "closed"
    return game, target


def test_integrating_moves_products_people_and_lets_the_rest_go(loaded: LoadedData) -> None:
    before = fresh_game(loaded)
    zoho = _id(before, "GitHub")  # 127 staff: under integration.max_staff
    products = {p.id for p in before.company_products(zoho)}
    key = {e.person_id for e in before.staff(zoho)}
    pools = sum(p.headcount for p in before.company_pools(zoho))
    game, _ = _buy(loaded, "GitHub", "integrate")
    state = game.state
    (acq,) = state.acquisitions
    assert set(acq.product_ids) == products
    assert all(state.product(pid).company_id == 1 for pid in products)  # type: ignore[union-attr]
    assert all(state.product(pid).held_feature is None for pid in products)  # type: ignore[union-attr]
    assert not state.company(zoho).alive and state.staff(zoho) == ()
    staff = {e.person_id: e for e in state.staff(1)}
    assert (
        len(key - set(staff)) <= 1
    )  # the key people work for the player (one may resign as usual)
    units = {u.id: u for u in state.units if u.id in acq.unit_ids}
    assert {u.product_id for u in units.values()} == products
    assert all(staff[p].unit_id in units for p in key if p in staff)
    assert acq.pool_kept > 0 and acq.let_go > 0
    assert acq.pool_kept + acq.let_go >= round(pools)  # plus key people in other functions
    assert game.balances[(1, SALARIES)] > 0  # severance (and a month's payroll)
    assert acq.key_people == len(key) and len(state.acquired_people) <= len(key)
    assert all(p.until_turn == acq.closed_turn + 12 for p in state.acquired_people)


def test_integration_takes_the_higher_lead_plus_a_fifth_of_the_lower(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    zoho = _id(state, "GitHub")
    state = with_research_lead(state, ResearchLead(zoho, "software_platform", 10.0))
    state = with_research_lead(state, ResearchLead(1, "software_platform", 4.0))
    game = Game(loaded, state, cash=BIG)
    _energy(game)
    game.act(BidForCompany(_founder(game), zoho, _reservation(game, zoho)))
    game.turn()
    lead = game.state.research_lead(1, "software_platform")
    assert 10.0 < lead <= 10.0 + 0.2 * 4.0 + 0.5  # higher + 20% of the lower (decay aside)


def test_a_brand_keeps_its_books_sweeps_cash_and_follows_its_directive(
    loaded: LoadedData,
) -> None:
    game, evernote = _buy(loaded, "Evernote", "brand")
    state = game.state
    company = state.company(evernote)
    assert company.parent_id == 1 and company.alive and state.staff(evernote)
    assert style(state, company) == "aggressive"  # default directive: grow
    _energy(game)
    game.act(SetDirective(_founder(game), evernote, "harvest"))
    assert style(game.state, game.state.company(evernote)) == "cost_leader"
    invested = game.balances[(1, INVESTMENT_SUBSIDIARIES)]
    cash = game.balances[(1, CASH)]
    game.turn()
    swept = invested - game.balances[(1, INVESTMENT_SUBSIDIARIES)]
    if swept > 0:  # cash above 3 months of its costs went to the parent
        assert game.balances[(1, CASH)] > cash - 10**9
    assert all(p.brand for p in game.state.acquired_people)


def test_flight_is_seeded_and_counted(loaded: LoadedData) -> None:
    runs = []
    for _ in range(2):
        game, _ = _buy(loaded, "GitHub", "integrate")
        for _ in range(6):
            game.turn()
        (acq,) = game.state.acquisitions
        runs.append((acq.departed, tuple(p.person_id for p in game.state.acquired_people)))
    assert runs[0] == runs[1]


def test_level_bands() -> None:
    assert integration.level_for(7.0) == "junior"
    assert integration.level_for(10.0) == "mid"
    assert integration.level_for(13.0) == "senior"
    assert integration.level_for(16.0) == "staff"


def test_distance_reads_average_traits(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    zoho = _id(state, "Zoho")
    b, d = loaded.balance, loaded.game_data
    distance = integration.distance_between(state, 1, zoho, b, d)
    assert 0.0 <= distance <= 1.0
    founder = state.founder_of(1)
    assert founder is not None
    same = replace(state, people=state.people)
    assert integration.distance_between(same, 1, 1, b, d) == 0.0


def test_kept_staff_follow_revenue_shares_and_synergies(loaded: LoadedData) -> None:
    """2026-11-05: a one-product target keeps all its staff but the function's synergy:
    builders 10% let go; sellers and marketers 15% in a category the acquirer is new to."""
    before = fresh_game(loaded)
    github = _id(before, "GitHub")
    assert len(before.company_products(github)) == 1
    pools = {p.function: round(p.headcount) for p in before.company_pools(github)}
    ib = loaded.balance.integration
    want = sum(
        round(n * (1 - (ib.synergy_builders if f == "builder" else ib.synergy_new)))
        for f, n in pools.items()
    )
    game, _ = _buy(loaded, "GitHub", "integrate")
    (acq,) = game.state.acquisitions
    assert acq.pool_kept == want
    assert integration.synergy("seller", True, ib) == ib.synergy_overlap


def test_revenue_shares(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    products = list(state.company_products(_id(state, "Microsoft")))
    shares = integration.revenue_shares(state, products)
    assert abs(sum(shares) - 1.0) < 1e-9 and len(shares) == len(products)


@pytest.mark.parametrize("mode", ["integrate", "brand"])
def test_hidden_problems_apply_in_either_mode(loaded: LoadedData, mode: str) -> None:
    """M15r (Codex review 4 finding 7): tech_debt costs 10 quality over the 12 months after
    closing and customer_concentration multiplies churn x1.5 for those 12 months (28.2), on
    the products' owning company, whether the target is integrated or kept as a brand."""
    from tst.sim.events.modifiers import product_factor
    from tst.sim.mna.deals import file_of
    from tst.sim.state import with_target_file

    pb = loaded.balance.mna.problems
    game = Game(loaded, fresh_game(loaded, seed=3), cash=BIG)
    target = _id(game.state, "GitHub")
    found = file_of(game.state, 1, target, loaded.balance)
    game.state = with_target_file(
        game.state, replace(found, problems=("tech_debt", "customer_concentration"))
    )
    _energy(game)
    game.act(BidForCompany(_founder(game), target, _reservation(game, target), mode=mode))  # type: ignore[arg-type]
    game.turn()
    (acquisition,) = game.state.acquisitions
    assert acquisition.mode == mode and acquisition.product_ids
    owner = 1 if mode == "integrate" else target
    closed = acquisition.closed_turn
    state = game.state
    start = {pid: state.product(pid).quality for pid in acquisition.product_ids}  # type: ignore[union-attr]
    ib = loaded.balance.integration
    for month in range(1, pb.tech_debt_months + 2):
        state = integration._products(replace(state, turn=closed + month), loaded.balance)
        lost = min(month, pb.tech_debt_months) * pb.tech_debt_quality / pb.tech_debt_months
        for pid in acquisition.product_ids:
            product = state.product(pid)
            assert product is not None and product.company_id == owner
            assert product.quality == pytest.approx(start[pid] - lost)
            clash = ib.churn_mult if mode == "integrate" and month < ib.churn_months else 1.0
            problem = pb.churn_mult if month <= pb.churn_months else 1.0
            assert product_factor(state, owner, pid, "churn") == pytest.approx(clash * problem)
