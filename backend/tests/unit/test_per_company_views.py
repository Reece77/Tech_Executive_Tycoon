"""M12r brief item 7 (Codex review 3 finding 8; ADR-0020 1): the research and
infrastructure view builders take the company they show, and era news names the causing
company apart from the observer. No subsidiary gameplay: the second company here is an
ordinary company given its own project and data centre."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game
from tst.api.facility_views import infrastructure_out
from tst.api.research_views import research_out
from tst.loader import LoadedData
from tst.sim.facilities.models import Facility
from tst.sim.org.models import OrgUnit
from tst.sim.research import eras
from tst.sim.research.models import EraArrival, ResearchLead, ResearchProject
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_facility, with_research_project, with_unit

A, B = 1, 2


def _facility(loaded: LoadedData, fid: int, company: int, capacity: int) -> Facility:
    k = loaded.balance.facility.kinds["data_centre_general"]
    return Facility(
        id=fid,
        company_id=company,
        kind="data_centre_general",
        region="north_america",
        capacity=capacity,
        on_time=capacity,
        ordered_turn=-k.build_months,
        ready_turn=0,
        late_turn=0,
        capex_cents=capacity * k.capex_per_unit_cents,
        input_index=1.0,
        capex_paid_cents=capacity * k.capex_per_unit_cents,
        status="live",
    )


def _two(loaded: LoadedData) -> GameState:
    """Company A with a lab on AI and a 100-CU site; company B with a lab on devices and a
    500-CU site."""
    state = fresh_game(loaded)
    for uid, company, domain, pid in ((50, A, "ai", 60), (51, B, "devices", 61)):
        state = with_unit(
            state, OrgUnit(uid, company, "team", f"Lab {company}", None, None, "office", 0)
        )
        state = with_research_project(state, ResearchProject(pid, company, domain, uid, 0))
    state = with_facility(state, _facility(loaded, 70, A, 100))
    return with_facility(state, _facility(loaded, 71, B, 500))


def test_each_company_gets_its_own_research_view(loaded: LoadedData) -> None:
    state = _two(loaded)
    mine, theirs = research_out(state, loaded, A), research_out(state, loaded, B)
    assert [(p.project_id, p.domain) for p in mine.projects] == [(60, "ai")]
    assert [(p.project_id, p.domain) for p in theirs.projects] == [(61, "devices")]
    assert all(r.company_id != B for d in theirs.rivals for r in d.rivals)
    assert research_out(state, loaded, state.player.id) == mine


def test_each_company_gets_its_own_infrastructure_view(loaded: LoadedData) -> None:
    state = _two(loaded)
    mine, theirs = (
        infrastructure_out(state, loaded, {}, A),
        infrastructure_out(state, loaded, {}, B),
    )
    assert [(f.facility_id, f.units) for f in mine.facilities] == [(70, 100)]
    assert [(f.facility_id, f.units) for f in theirs.facilities] == [(71, 500)]
    assert mine.cloud.can_start and theirs.cloud.can_start


def test_era_news_names_the_causer_apart_from_the_observer(
    loaded: LoadedData, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every company the player controls hears; the one that caused the era hears "your
    research" and its head start, the other hears the causer's name."""
    state = _two(loaded)
    g, b = loaded.game_data, loaded.balance
    era = g.eras.eras[0]
    arrival = EraArrival(era.key, 0, B, 12)
    to_a = eras.era_news(state, g, b, era, arrival, A)
    to_b = eras.era_news(state, g, b, era, arrival, B)
    a_params, b_params = dict(to_a.params), dict(to_b.params)
    assert to_a.company_id == A and to_b.company_id == B
    assert state.company(B).name in str(a_params["when"]) and not a_params["note"]
    assert "your research" in str(b_params["when"]) and b_params["note"]
    group = (state.company(A), state.company(B))
    monkeypatch.setattr(eras, "player_companies", lambda _s: group)
    ahead = replace(state, research_leads=(ResearchLead(B, era.domain, 1000.0),))
    _, logs = eras.arrive_eras(ahead, g, b, RngFactory(1))
    heard = [log.company_id for log in logs if dict(log.params).get("era") == era.label]
    assert heard == [A, B]
