"""Licensing, leaks and rivals' research (formulas.md 21.5, 21.6; M11 sub-task 5)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import with_product
from tests.unit.test_research import FOUNDER, _lab_game, _unit
from tst.loader import LoadedData
from tst.sim.actions.research import LicenseIn, LicenseOut, StartProject
from tst.sim.errors import ResearchRuleError
from tst.sim.ledger import CASH, LICENSE_REVENUE, RESEARCH
from tst.sim.research import licensing
from tst.sim.research.formulas import license_price_cents
from tst.sim.research.models import ResearchLead
from tst.sim.research.projects import add_lead
from tst.sim.research.rivals import (
    month_start,
    research_needs,
    rival_research_month,
    start_research,
)
from tst.sim.rivals.models import PoachApproach
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_employment

SALESFORCE, IBM = 2, 17


def _lines(entries, company: int, account: str) -> int:  # type: ignore[no-untyped-def]
    return sum(
        line.amount
        for e in entries
        if e.company_id == company
        for line in e.lines
        if line.account == account
    )


def test_license_in(loaded: LoadedData) -> None:
    """Up to their lead - 10 - yours, offered as the public ceiling (the displayed range's
    low end; M12r), price $150,000 x points x (1 + ARR / $20M), paid once; the licensor
    books licence revenue (21.5)."""
    game = _lab_game(loaded, staff=1)
    game.state = add_lead(game.state, SALESFORCE, "devices", 40.0)
    b, g = loaded.balance, loaded.game_data
    ceiling = licensing.public_license_in_limit(game.state, b, g, 1, SALESFORCE, "devices")
    assert 0 < ceiling <= 30
    energy = game.state.person_state(FOUNDER).energy or 0
    with pytest.raises(ResearchRuleError, match="ask for fewer points"):
        game.act(LicenseIn(FOUNDER, SALESFORCE, "devices", ceiling + 1))
    cash = game.cash
    game.act(LicenseIn(FOUNDER, SALESFORCE, "devices", ceiling))
    assert game.state.research_lead(1, "devices") == ceiling
    price = license_price_cents(ceiling, 0, loaded.balance)
    assert price == ceiling * loaded.balance.rnd.license.price_per_point_cents
    assert game.cash == cash - price
    assert game.balances[(SALESFORCE, LICENSE_REVENUE)] == -price
    assert game.state.person_state(FOUNDER).energy == energy - loaded.balance.rnd.license.energy
    licence = game.state.licenses[0]
    assert (licence.licensor_id, licence.licensee_id, licence.points) == (SALESFORCE, 1, ceiling)
    while more := licensing.public_license_in_limit(game.state, b, g, 1, SALESFORCE, "devices"):
        game.act(LicenseIn(FOUNDER, SALESFORCE, "devices", more))
    assert game.state.research_lead(1, "devices") <= 30
    with pytest.raises(ResearchRuleError, match="not more than 10"):
        game.act(LicenseIn(FOUNDER, SALESFORCE, "devices", 1))


def test_a_direct_competitor_says_no(loaded: LoadedData) -> None:
    """Salesforce sells B2B SaaS to SMB, as the player does: no software platform licence."""
    game = _lab_game(loaded, staff=1)
    game.state = with_product(game.state, prices={"smb": 4000})
    game.state = add_lead(game.state, SALESFORCE, "software_platform", 40.0)
    with pytest.raises(ResearchRuleError, match="direct competitor"):
        game.act(LicenseIn(FOUNDER, SALESFORCE, "software_platform", 5))
    assert (
        licensing.refusal(game.state, loaded.game_data, loaded.balance, 1, IBM, "devices")
        == "its lead is not more than 10 points ahead of yours"
    )


def test_license_out_earns_royalties(loaded: LoadedData) -> None:
    game = _lab_game(loaded, staff=1)
    game.state = add_lead(game.state, 1, "software_platform", 30.0)
    ceiling = licensing.public_license_out_limit(
        game.state, loaded.balance, loaded.game_data, 1, SALESFORCE, "software_platform"
    )
    assert 0 < ceiling < 20
    with pytest.raises(ResearchRuleError, match="ask for fewer points"):
        game.act(LicenseOut(FOUNDER, SALESFORCE, "software_platform", ceiling + 1))
    game.act(LicenseOut(FOUNDER, SALESFORCE, "software_platform", ceiling))
    assert game.state.research_lead(SALESFORCE, "software_platform") == ceiling
    licence = game.state.licenses[0]
    assert licence.royalty_bp == 200
    assert licence.royalty_end_turn == game.state.turn + 23
    entries = licensing.royalties(game.state, loaded.balance, loaded.game_data)
    revenue = licensing.product_revenue(game.state, SALESFORCE, {"b2b_saas"})
    assert revenue > 0
    assert _lines(entries, 1, CASH) == round(revenue * 0.02)
    assert _lines(entries, SALESFORCE, RESEARCH) == round(revenue * 0.02)
    late = replace(game.state, turn=game.state.turn + 24)
    assert licensing.royalties(late, loaded.balance, loaded.game_data) == ()


def test_a_leaving_researcher_leaks(loaded: LoadedData) -> None:
    """A researcher on a project who joins a rival gives it min(10, 0.1 x your lead)."""
    game = _lab_game(loaded, staff=2)
    unit = _unit(game)
    game.act(StartProject(FOUNDER, unit, "ai"))
    state = add_lead(game.state, 1, "ai", 40.0)
    employment = state.employment_of(2)
    assert employment is not None and employment.unit_id == unit
    state = with_employment(state, replace(employment, status="ended", end_reason="poached"))
    approach = PoachApproach(1, IBM, 2, 10_000_000, state.turn, status="accepted")
    before = replace(state, approaches=(approach,))
    after = replace(state, approaches=(replace(approach, status="joined"),))
    out, logs = licensing.leaks(before, after, loaded.balance, loaded.game_data)
    assert out.research_lead(IBM, "ai") == pytest.approx(4.0)
    assert logs[0].template == "research_leak"
    again, _ = licensing.leaks(after, after, loaded.balance, loaded.game_data)
    assert again.research_lead(IBM, "ai") == 0


def test_rivals_research(loaded: LoadedData) -> None:
    """need = (best lead - own) / 15 (+0.3 near an era); 6 months at 0.8 x d / 10 a month,
    builder pool +10% while it runs; startups never research (21.6)."""
    game = _lab_game(loaded, staff=1)
    state: GameState = replace(
        game.state, research_leads=(ResearchLead(1, "software_platform", 30.0),)
    )
    company = state.company(SALESFORCE)
    needs = {
        n.domain: n.need for n in research_needs(state, company, loaded.balance, loaded.game_data)
    }
    assert needs["software_platform"] == 1.0
    assert set(needs) == {"software_platform", "infrastructure"}
    assert (
        research_needs(state, replace(company, is_startup=True), loaded.balance, loaded.game_data)
        == []
    )
    builders = next(p for p in state.company_pools(SALESFORCE) if p.function == "builder")
    state, words = start_research(
        state, company, "software_platform", loaded.balance, loaded.game_data
    )
    assert words == "started Software platform research"
    grown = next(p for p in state.company_pools(SALESFORCE) if p.function == "builder")
    assert grown.headcount == pytest.approx(builders.headcount * 1.1)
    quiet = loaded.balance.model_copy(
        update={"rnd": loaded.balance.rnd.model_copy(update={"breakthrough_chance": 0.0})}
    )
    for month in range(6):
        state = rival_research_month(
            replace(state, turn=state.turn + (month > 0)), RngFactory(1), quiet
        )
    assert state.research_lead(SALESFORCE, "software_platform") == pytest.approx(6 * 0.8 * 14 / 10)
    assert not state.active_projects(SALESFORCE)
    state = month_start(replace(state, turn=state.turn + 1), quiet)  # the next month (M12r)
    back = next(p for p in state.company_pools(SALESFORCE) if p.function == "builder")
    assert back.headcount == pytest.approx(builders.headcount)


def test_rival_research_pays_its_premium_every_month(loaded: LoadedData) -> None:
    """M12r finding 5 (Codex review 3): a six-month rival research action pays the builder
    pool's +10% in each of its six monthly payrolls (phase 6, after phase 3), the last month
    included; the pool is back to normal for the next month's payroll (21.6, 21.10)."""
    from tst.sim.hiring.phases import monthly_costs

    game = _lab_game(loaded, staff=1)
    state: GameState = replace(
        game.state, research_leads=(ResearchLead(1, "software_platform", 30.0),)
    )
    b, g = loaded.balance, loaded.game_data
    quiet = b.model_copy(update={"rnd": b.rnd.model_copy(update={"breakthrough_chance": 0.0})})

    def payroll(s: GameState) -> int:
        return sum(amount for _, _, amount in monthly_costs(s, SALESFORCE, b, g))

    base = payroll(state)
    state, _ = start_research(state, state.company(SALESFORCE), "software_platform", b, g)
    premium = payroll(state) - base
    builders = sum(
        p.headcount for p in game.state.company_pools(SALESFORCE) if p.function == "builder"
    )
    assert premium > 0 and builders > 0
    premiums = []
    for month in range(7):
        state = replace(state, turn=state.turn + (month > 0))
        state = month_start(state, quiet)  # phase 1
        state = rival_research_month(state, RngFactory(1), quiet)  # phase 3
        premiums.append(payroll(state) - base)  # phase 6
    assert premiums[:6] == [premium] * 6
    assert sum(premiums[:6]) == 6 * premium
    assert premiums[6] == 0
