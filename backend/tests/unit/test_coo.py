"""Ask my COO (formulas.md 17.3; M7b): who answers, and one test for each briefing issue."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.helpers import fresh_game, make_person, with_employee, with_product
from tst.loader import LoadedData
from tst.sim import coo
from tst.sim.events.models import GameEvent
from tst.sim.hiring.models import Search
from tst.sim.rivals.models import RivalMove
from tst.sim.state import GameState, with_event, with_rival_move, with_search

PLENTY = 10**12  # cents: no runway issue


def _keys(state: GameState, loaded: LoadedData, cash: int = PLENTY) -> list[str]:
    return [i.key for i in coo.briefing(state, cash, loaded.balance, loaded.game_data)]


def _staffed(loaded: LoadedData, *people: tuple[int, str, str, int]) -> GameState:
    state = fresh_game(loaded)
    for pid, role, level, morale in people:
        state = with_employee(loaded, state, make_person(loaded, pid, role, level), 9_000_000)
        ps = state.person_state(pid)
        from tst.sim.state import with_person_state

        state = with_person_state(state, replace(ps, morale=float(morale)))
    return state


def test_nothing_urgent(loaded: LoadedData) -> None:
    assert _keys(fresh_game(loaded), loaded) == []


def test_runway_under_twelve_months(loaded: LoadedData) -> None:
    state = _staffed(loaded, (2, "software_engineer", "mid", 65))
    issues = coo.briefing(state, 100_000, loaded.balance, loaded.game_data)
    assert [i.key for i in issues] == ["runway"] and issues[0].link_kind == "finance"
    assert "Runway is down to 0 months" in issues[0].text


def _event(state: GameState, severity: str, status: str = "open") -> GameState:
    event_id, ids = state.next_ids.take("event")
    event = GameEvent(
        id=event_id,
        company_id=1,
        turn=state.turn,
        template_id="t",
        category="finance",
        severity=severity,  # type: ignore[arg-type]
        trigger="quiet_month",
        strength=1.0,
        status=status,  # type: ignore[arg-type]
        title=f"A {severity} matter",
    )
    return with_event(replace(state, next_ids=ids), event)


def test_open_critical_or_major_event(loaded: LoadedData) -> None:
    state = _event(_event(_event(fresh_game(loaded), "minor"), "major"), "critical")
    issues = coo.briefing(state, PLENTY, loaded.balance, loaded.game_data)
    assert [i.key for i in issues] == ["event", "event"]
    assert "critical" in issues[0].text and "major" in issues[1].text  # critical first
    assert issues[0].link_kind == "event" and issues[0].link_id is not None
    assert _keys(_event(fresh_game(loaded), "major", status="answered"), loaded) == []


def test_rotting_product(loaded: LoadedData) -> None:
    state = with_product(fresh_game(loaded))
    product = state.company_products(1)[0]
    from tst.sim.state import with_product as put

    rotting = put(state, replace(product, rotting=True))
    issues = coo.briefing(rotting, PLENTY, loaded.balance, loaded.game_data)
    assert [i.key for i in issues] == ["rotting"] and issues[0].link_id == product.id
    assert _keys(state, loaded) == []


def test_low_shown_morale(loaded: LoadedData) -> None:
    state = _staffed(loaded, (2, "software_engineer", "mid", 39), (3, "designer", "mid", 41))
    issues = coo.briefing(state, PLENTY, loaded.balance, loaded.game_data)
    assert [(i.key, i.link_id) for i in issues] == [("morale", 2)]


def test_unit_over_its_span(loaded: LoadedData, monkeypatch: pytest.MonkeyPatch) -> None:
    state = _staffed(loaded, (2, "software_engineer", "mid", 65))
    assert _keys(state, loaded) == []
    monkeypatch.setattr(coo, "span_limit", lambda *_: 0)  # the founder now manages too many
    issues = coo.briefing(state, PLENTY, loaded.balance, loaded.game_data)
    assert [(i.key, i.link_kind) for i in issues] == [("span", "org")]


def test_role_open_more_than_three_months(loaded: LoadedData) -> None:
    state = replace(fresh_game(loaded), turn=10)
    old = Search(id=1, company_id=1, role="designer", channel="job_post", actor_id=1, opened_turn=6)
    new = Search(id=2, company_id=1, role="marketer", channel="job_post", actor_id=1, opened_turn=7)
    issues = coo.briefing(
        with_search(with_search(state, old), new), PLENTY, loaded.balance, loaded.game_data
    )
    assert [(i.key, i.link_id) for i in issues] == [("role_open", 1)]
    assert "4 months" in issues[0].text


def test_board_confidence_under_fifty(loaded: LoadedData, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(coo, "average_confidence", lambda *_: 49.0)
    assert _keys(fresh_game(loaded), loaded) == ["board"]
    monkeypatch.setattr(coo, "average_confidence", lambda *_: 50.0)
    assert _keys(fresh_game(loaded), loaded) == []


def test_rival_price_cut_in_your_segments(loaded: LoadedData) -> None:
    state = replace(with_product(fresh_game(loaded)), turn=5)
    rival_product = next(
        p for p in state.products if p.company_id != 1 and p.category == "b2b_saas"
    )

    def cut(segment: str, turn: int) -> RivalMove:
        return RivalMove(
            id=turn * 10 + len(segment),
            company_id=rival_product.company_id,
            turn=turn,
            action="price_cut",
            product_id=rival_product.id,
            segment=segment,
        )

    assert _keys(with_rival_move(state, cut("enterprise", 4)), loaded) == []  # not your segment
    assert _keys(with_rival_move(state, cut("smb", 3)), loaded) == []  # not last month
    issues = coo.briefing(
        with_rival_move(state, cut("smb", 4)), PLENTY, loaded.balance, loaded.game_data
    )
    assert [(i.key, i.link_id) for i in issues] == [("price_cut", rival_product.company_id)]


def test_at_most_five_most_urgent_first(loaded: LoadedData) -> None:
    people = [(pid, "software_engineer", "mid", 20) for pid in range(2, 9)]
    state = _event(_staffed(loaded, *people), "major")
    issues = coo.briefing(state, 100_000, loaded.balance, loaded.game_data)
    assert len(issues) == loaded.balance.coo.max_issues
    assert [i.key for i in issues][:3] == ["runway", "event", "morale"]


def test_who_answers(loaded: LoadedData) -> None:
    assert coo.coo_of(fresh_game(loaded)) is None  # the founder's notebook
    state = _staffed(loaded, (2, "software_engineer", "mid", 65), (3, "designer", "senior", 65))
    assert coo.coo_of(state) == 3  # highest level
    state = _staffed(
        loaded,
        (2, "software_engineer", "principal", 65),
        (3, "operations_manager", "mid", 65),
        (4, "operations_manager", "mid", 65),
    )
    assert coo.coo_of(state) == 3  # an operations manager first; ties: longest tenure
