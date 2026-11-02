"""M10c authority through the API (formulas.md 24.1, 24.4): give a seat authority with
guardrails, change and withdraw it; the response never carries the decision quality or the
holder's score."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import answer_events
from tests.integration.test_api_hiring import Client
from tests.integration.test_api_scaleup import BASE, api  # noqa: F401
from tst.db.repository import open_session
from tst.db.state_io import load_state
from tst.loader import LoadedData


def _seat(out: dict, seat: str) -> dict:  # type: ignore[type-arg]
    return next(s for s in out["seats"] if s["seat"] == seat)


def test_give_change_and_withdraw_authority(api: tuple[Client, Path]) -> None:  # noqa: F811
    client, path = api
    out = client.get(f"{BASE}/scaleup")
    cto = _seat(out, "cto")
    assert cto["authority"]["enabled"] is False
    assert cto["authority"]["guardrails"]["headcount_cap"] == 30
    assert _seat(out, "cpo")["authority"] is None  # no authority for the CPO (24.1)
    client.post(f"{BASE}/scaleup/seats/cto/authority", {"enabled": True}, status=400)  # vacant
    client.post(f"{BASE}/scaleup/seats/cto/appoint", {"person_id": 2})
    out = client.post(
        f"{BASE}/scaleup/seats/cto/authority",
        {"enabled": True, "guardrails": {"headcount_cap": 12, "protected_units": []}},
    )
    cto = _seat(out["scaleup"], "cto")
    assert cto["authority"]["enabled"] is True and cto["authority"]["since_label"]
    assert cto["authority"]["guardrails"]["headcount_cap"] == 12
    client.post(
        f"{BASE}/scaleup/seats/cto/authority",
        {"enabled": True, "guardrails": {"bogus": 1}},
        status=400,
    )
    client.post(
        f"{BASE}/scaleup/seats/cto/authority",
        {"enabled": True, "guardrails": {"headcount_cap": -1}},
        status=400,
    )
    with open_session(path) as session:
        state = load_state(session)
    a = state.authority(1, "cto")
    assert a is not None and a.enabled and a.number("headcount_cap") == 12
    out = client.post(f"{BASE}/scaleup/seats/cto/authority", {"enabled": False})
    assert _seat(out["scaleup"], "cto")["authority"]["enabled"] is False
    blob = json.dumps(out).lower()
    for hidden in ("quality", "probability", "true_score", "score"):
        assert f'"{hidden}"' not in blob  # 24.4: never the score or the probability


def test_a_cfo_proposal_blocks_continue_until_answered(
    api: tuple[Client, Path],  # noqa: F811
    loaded: LoadedData,
) -> None:
    """24.1: below its runway threshold the CFO proposes funding; the proposal blocks
    Continue (23.1) until approved (the action is taken) or declined."""
    client, path = api
    client.post(f"{BASE}/scaleup/seats/cfo/appoint", {"person_id": 21})
    client.post(f"{BASE}/scaleup/seats/cfo/authority", {"enabled": True})
    answer_events(path, loaded)
    client.post(f"{BASE}/advance")
    out = client.get(f"{BASE}/scaleup")
    pending = [p for p in out["proposals"] if p["status"] == "pending"]
    assert len(pending) == 1 and pending[0]["seat"] == "cfo"
    proposal = pending[0]
    assert client.get(f"{BASE}/events")["blocking_proposal_ids"] == [proposal["proposal_id"]]
    blocked = client.post(f"{BASE}/advance", status=409)
    assert blocked["proposal_ids"] == [proposal["proposal_id"]]
    assert "1 proposal" in blocked["message"]
    done = client.post(f"{BASE}/scaleup/proposals/{proposal['proposal_id']}/approve")
    status = next(
        p["status"]
        for p in done["scaleup"]["proposals"]
        if p["proposal_id"] == proposal["proposal_id"]
    )
    assert status == "approved"
    with open_session(path) as session:
        state = load_state(session)
    if proposal["kind"] == "round":
        assert any(r.status == "open" for r in state.company_rounds(1))
    else:
        assert state.company_loans(1)
    assert client.get(f"{BASE}/events")["blocking_proposal_ids"] == []


def test_a_declined_or_unanswered_proposal(
    api: tuple[Client, Path],  # noqa: F811
    loaded: LoadedData,
) -> None:
    """Declined: nothing is taken. Unanswered when Holiday or a script plays the month: it
    lapses (only the player's own Continue is blocked)."""
    from tst.db import repository

    client, path = api
    client.post(f"{BASE}/scaleup/seats/cfo/appoint", {"person_id": 21})
    client.post(f"{BASE}/scaleup/seats/cfo/authority", {"enabled": True})
    answer_events(path, loaded)
    client.post(f"{BASE}/advance")
    (first,) = [p for p in client.get(f"{BASE}/scaleup")["proposals"] if p["status"] == "pending"]
    client.post(f"{BASE}/scaleup/proposals/{first['proposal_id']}/decline")
    client.post(f"{BASE}/scaleup/proposals/{first['proposal_id']}/approve", status=400)
    with open_session(path) as session:
        state = load_state(session)
    assert not any(r.status == "open" for r in state.company_rounds(1))
    assert state.proposals[0].status == "declined"
    # A quarter later the CFO proposes again; Holiday's month lets it lapse.
    for _ in range(loaded.balance.exec_authority.report_months + 2):
        answer_events(path, loaded)
        repository.run_turn(path, loaded)
    with open_session(path) as session:
        statuses = [p.status for p in load_state(session).proposals]
    assert statuses[0] == "declined" and "lapsed" in statuses[1:]
