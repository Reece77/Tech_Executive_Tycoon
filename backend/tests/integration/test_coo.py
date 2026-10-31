"""Ask my COO (docs/formulas.md 17.3; M7b sub-task 6): the briefing offline, answers by the
mock adapter within the budget, the offline reply over budget, the last 20 kept, and no
change to the game."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from tests.integration.test_api_hiring import BASE, hiring_client
from tst.db import coo as coo_db
from tst.db import repository
from tst.db.models import LLMCallLogRow
from tst.llm.offline import TemplateAdapter
from tst.llm.settings import LLMSettings, month_spend, save_settings
from tst.loader import LoadedData


def _path(tmp_path: Path) -> Path:
    return repository.save_path(tmp_path / "saves", "m1b")


def test_briefing_and_a_mock_answer(tmp_path: Path) -> None:
    with hiring_client(tmp_path) as api:
        info = api.get(f"{BASE}/coo")
        assert info["person_id"] is None and info["name"] == "Founder's notebook"
        assert info["max_question_chars"] == 300 and info["answers"] == []
        assert isinstance(info["briefing"], list) and not info["offline"]
        energy = api.get(f"{BASE}/overview")["energy"]["energy"]
        before = api.get(f"{BASE}/overview")
        answer = api.post(f"{BASE}/coo/ask", {"question": "What should I worry about?"})
        assert answer["source"] == "mock" and answer["answer"].startswith("[mock]")
        assert answer["speaker"] == "Founder's notebook"
        assert answer["date_label"] == "Jan 2010"
        after = api.get(f"{BASE}/overview")
        assert after == before and after["energy"]["energy"] == energy  # read-only
        assert api.get(f"{BASE}/coo")["answers"][0]["answer_id"] == answer["answer_id"]
        api.post(f"{BASE}/coo/ask", {"question": "x" * 301}, status=400)
    assert month_spend(tmp_path / "saves").calls == 1
    with repository.open_session(_path(tmp_path)) as session:
        (log,) = session.scalars(select(LLMCallLogRow).where(LLMCallLogRow.purpose == "coo"))
    assert log.model == "mock" and log.outcome == "ok"


def test_over_budget_or_offline_gives_the_briefing(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path) as api:
        save_settings(tmp_path / "saves", LLMSettings(monthly_budget_cents=0))
        answer = api.post(f"{BASE}/coo/ask", {"question": "How are we doing?"})
        assert answer["source"] == "offline"
        assert answer["answer"].startswith("I can't think that through right now.")
    offline = coo_db.ask(_path(tmp_path), loaded, "Anything?", adapter=TemplateAdapter())
    assert offline.source == "offline" and offline.cost_cents == 0


def test_the_last_twenty_answers_are_kept(tmp_path: Path, loaded: LoadedData) -> None:
    with hiring_client(tmp_path):
        pass
    path = _path(tmp_path)
    keep = loaded.balance.coo.keep_answers
    for i in range(keep + 2):
        coo_db.ask(path, loaded, f"Question {i}?")
    kept = coo_db.answers(path)
    assert len(kept) == keep and kept[0].question == f"Question {keep + 1}?"
    assert kept[-1].question == "Question 2?"


def test_answers_are_trimmed_to_the_word_limit() -> None:
    assert coo_db._trim("one two three", 2) == "one two…"
    assert coo_db._trim(" one two ", 2) == "one two"
