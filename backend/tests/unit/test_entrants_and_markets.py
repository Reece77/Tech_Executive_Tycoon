"""M8 new markets and scheduled entrants (formulas.md 18.6, 18.7)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, rival_cash, with_product
from tst.loader import LoadedData
from tst.sim.actions.products import launch_problems
from tst.sim.calendar import ym_to_turn
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH
from tst.sim.products.phases import product_costs
from tst.sim.rivals.startups import alive_startups, found_entrants, is_entrant
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.turn import advance_turn


def at(state: GameState, turn: int) -> GameState:
    return replace(state, turn=turn)


@pytest.mark.parametrize("seed", range(1, 11))
def test_every_entrant_is_founded_in_its_month(loaded: LoadedData, seed: int) -> None:
    """18.9 target 6: founding needs no draw, so every seed sees every entrant."""
    data = loaded.game_data
    state = fresh_game(loaded, seed=seed)
    for entrant in data.entrants:
        month = ym_to_turn(entrant.year, entrant.month)
        before, _, _ = found_entrants(at(state, month - 1), RngFactory(seed), loaded.balance, data)
        assert entrant.name not in {c.name for c in before.companies}
        state, entries, moves = found_entrants(
            at(state, month), RngFactory(seed), loaded.balance, data
        )
        company = next(c for c in state.companies if c.name == entrant.name)
        assert company.founded_turn == month and company.is_startup and is_entrant(company, data)
        assert [m.action for m in moves] == ["founded"]
        assert entries[0].lines[0].amount == entrant.cash_cents
        staff = state.staff(company.id)
        assert len(staff) == entrant.staff
        assert {e.level for e in staff} == {"senior"}
        (product,) = state.company_products(company.id)
        assert product.category == entrant.category
        assert {s.segment for s in state.segments_of(product.id)} == set(entrant.segments)
        again, _, _ = found_entrants(state, RngFactory(seed), loaded.balance, data)
        assert sum(1 for c in again.companies if c.name == entrant.name) == 1


def test_entrant_people_are_seeded(loaded: LoadedData) -> None:
    data = loaded.game_data
    month = ym_to_turn(2011, 9)
    state = at(fresh_game(loaded), month)

    def people(seed: int) -> list[tuple[str, float]]:
        out, _, _ = found_entrants(state, RngFactory(seed), loaded.balance, data)
        stripe = next(c for c in out.companies if c.name == "Stripe")
        return [
            (out.person(e.person_id).first_name, out.person(e.person_id).skills["sales"])
            for e in out.staff(stripe.id)
        ]

    assert people(7) == people(7)
    assert people(7) != people(8)


def test_entrants_do_not_count_toward_the_startup_cap(loaded: LoadedData) -> None:
    data = loaded.game_data
    state, _, _ = found_entrants(
        at(fresh_game(loaded), ym_to_turn(2010, 3)), RngFactory(1), loaded.balance, data
    )
    assert len(alive_startups(state)) == 1
    assert alive_startups(state, data) == []


def test_square_is_founded_in_a_played_march_2010(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    balances = {**rival_cash(state, loaded), (1, CASH): 500_000_000}
    for _ in range(3):
        out = advance_turn(
            state, Decisions(), RngFactory(3), loaded.balance, loaded.game_data, balances
        )
        for e in out.ledger_entries:
            for line in e.lines:
                balances[(e.company_id, line.account)] = (
                    balances.get((e.company_id, line.account), 0) + line.amount
                )
        state = out.new_state
        founded = [m for m in out.rival_moves if m.action == "founded" and "Square" in m.detail]
        assert bool(founded) == (state.turn - 1 == ym_to_turn(2010, 3))


def test_fintech_launch_needs_compliance_quality(loaded: LoadedData) -> None:
    state = with_product(
        fresh_game(loaded),
        category="fintech",
        prices={"smb": 6000},
        status="in_development",
        quality=27.0,
        feature_points=1000.0,
        root=False,
    )
    product = state.company_products(1)[-1]
    assert any(
        "of the 30 needed" in p
        for p in launch_problems(state, product, loaded.balance, loaded.game_data)
    )
    ok = replace(product, quality=31.0)
    assert launch_problems(state, ok, loaded.balance, loaded.game_data) == []


def test_ai_hosting_follows_the_compute_index(loaded: LoadedData) -> None:
    state = with_product(
        fresh_game(loaded),
        category="ai_models",
        prices={"smb": 10_000},
        customers={"smb": 100.0},
        root=False,
    )
    index = loaded.game_data.compute_index
    for year in (2010, 2016, 2023, 2024):
        hosting, _ = product_costs(at(state, ym_to_turn(year, 6)), 1, loaded.game_data)
        assert hosting == round(100 * 4000 * index.of(year))


def test_new_markets_exist_from_2010(loaded: LoadedData) -> None:
    state = fresh_game(loaded)
    for cat in ("fintech", "ai_models"):
        for seg in loaded.game_data.category(cat).segment_keys:
            market = state.market(cat, seg)
            assert market is not None and market.addressable > 0
    names = {c.name for c in state.companies}
    assert {"PayPal", "Intuit", "Fiserv", "IBM", "Nuance"} <= names
