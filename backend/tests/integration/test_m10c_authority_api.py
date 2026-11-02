"""M10c authority through the API (formulas.md 24.1, 24.4): give a seat authority with
guardrails, change and withdraw it; the response never carries the decision quality or the
holder's score."""

from __future__ import annotations

import json
from pathlib import Path

from tests.integration.test_api_hiring import Client
from tests.integration.test_api_scaleup import BASE, api  # noqa: F401
from tst.db.repository import open_session
from tst.db.state_io import load_state


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
