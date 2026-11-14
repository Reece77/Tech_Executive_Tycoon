"""M27a automation API (formulas.md 40.8, 40.11): the Automation screen, giving and taking back
an area, a played month's digest through the API, and the digest's LLM prompt, with no true
score, quality probability or draw anywhere (hidden-value test)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from tests.helpers import make_person, with_employee
from tests.integration.test_api_hiring import hiring_client
from tst.db.repository import load_state, open_session
from tst.db.state_io import sync_state
from tst.events.service import Writer, write_text
from tst.llm.offline import MockLLMAdapter
from tst.llm.settings import LLMSettings
from tst.loader import LoadedData
from tst.sim.automation import digest, owners
from tst.sim.org.formulas import decision_quality
from tst.sim.state import reach_stage, with_company, with_employment

SAVE = "m1b"
LEAD = 50
SKILL = 13.37  # an odd true value, easy to spot


def _seed(tmp_path: Path, loaded: LoadedData) -> Path:
    """Stage 3 with a senior recruiter (skills all 13.37) and an engineer leaving."""
    path = tmp_path / "saves" / f"{SAVE}.tst.sqlite"
    with open_session(path) as session, session.begin():
        before = load_state(session)
        person = make_person(loaded, LEAD, "recruiter", "senior")
        person = replace(
            person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), SKILL))
        )
        state = with_employee(loaded, before, person, 12_000_000)
        leaver = make_person(loaded, LEAD + 1, "software_engineer", "mid")
        state = with_employee(loaded, state, leaver, 9_000_000)
        e = state.employment_of(LEAD + 1)
        assert e is not None
        state = with_employment(state, replace(e, status="notice", end_turn=state.turn + 1))
        state = with_company(state, reach_stage(state.player, 3, 0))
        state = replace(state, next_ids=replace(state.next_ids, person=LEAD + 2))
        sync_state(session, before, state)
    return path


def _hidden(loaded: LoadedData, path: Path) -> list[str]:
    with open_session(path) as session:
        state = load_state(session)
    score = owners.true_area_score(state, 1, "hiring", LEAD, loaded.balance)
    p = decision_quality(score, loaded.balance.automation.quality)
    return [f"{score:.2f}", f"{p:.3f}", f"{p:.0%}", str(SKILL)]


def test_automation_screen_give_take_back_and_the_digest(
    tmp_path: Path, loaded: LoadedData
) -> None:
    with hiring_client(tmp_path) as api:
        path = _seed(tmp_path, loaded)
        base = f"/api/saves/{SAVE}"
        out = api.get(f"{base}/automation")
        areas = {a["area"]: a for a in out["areas"]}
        assert areas["hiring"]["status"] == "manage"
        assert [c["person_id"] for c in areas["hiring"]["candidates"]] == [LEAD]
        assert areas["treasury"]["status"] == "cant"
        assert "finance manager" in areas["treasury"]["reason"]
        plan = api.get(f"{base}/automation/plan")
        assert [a["area"] for a in plan["assignments"]] == ["hiring"]
        given = api.post(f"{base}/automation/owner", {"area": "hiring", "person_id": LEAD})
        hiring = next(a for a in given["automation"]["areas"] if a["area"] == "hiring")
        assert hiring["status"] == "automated" and hiring["owner"]["person_id"] == LEAD
        api.post(f"{base}/advance")  # the digest never blocks Continue (40.4)
        d = api.get(f"{base}/automation/digest")
        assert d is not None and d["areas"][0]["area"] == "hiring"
        assert d["inbox_item_id"] is not None
        record = api.get(f"{base}/automation/record/{LEAD}")
        assert record["areas"] == ["Hiring"]
        everything = json.dumps(
            [api.get(f"{base}/automation"), d, record, api.get(f"{base}/inbox")]
        )
        for hidden in _hidden(loaded, path):
            assert hidden not in everything, hidden
        api.post(f"{base}/automation/take-back", {"area": "hiring"})
        back = api.get(f"{base}/automation")
        assert next(a for a in back["areas"] if a["area"] == "hiring")["status"] == "manage"
        api.post(f"{base}/automation/owner", {"area": "treasury", "person_id": LEAD}, status=400)


def test_the_digest_prompt_holds_no_hidden_value(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        path = _seed(tmp_path, loaded)
        api.post(f"/api/saves/{SAVE}/automation/owner", {"area": "hiring", "person_id": LEAD})
        api.post(f"/api/saves/{SAVE}/advance")
    with open_session(path) as session:
        state = load_state(session)
    d = digest.build(state, state.turn - 1, loaded.balance, loaded.game_data)
    assert d is not None
    adapter = MockLLMAdapter()
    writer = Writer(adapter, LLMSettings(), lambda: 1_000_000.0)
    write_text(state, "digest", state.turn - 1, None, writer, (d.opening, digest.facts(d)))
    prompts = " ".join(c.system + c.user for c in adapter.calls)
    assert prompts  # the opening was asked for
    for hidden in _hidden(loaded, path):
        assert hidden not in prompts, hidden


def test_the_inbox_hides_digest_items_by_default(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        _seed(tmp_path, loaded)
        base = f"/api/saves/{SAVE}"
        api.post(f"{base}/automation/owner", {"area": "hiring", "person_id": LEAD})
        api.post(f"{base}/advance")
        shown = api.get(f"{base}/inbox")["items"]
        everything = api.get(f"{base}/inbox?include_digest=true")["items"]
        assert all(not i["in_digest"] for i in shown)
        assert len(everything) >= len(shown)
        assert any(i["kind"] == "digest" for i in shown)  # the digest itself stays
