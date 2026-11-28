"""M57r-B sub-task 4 (review 10 items 21, 22, 31, 32): the reply checks, the budget's
reservation, constant system prompts and the test guard's adapter. Pure or file-level: no save."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tst.conversations import budget, classifier
from tst.llm.settings import add_spend, month_spend


# --- item 21: the reply's numbers, units and outcome ------------------------------------------
@pytest.mark.parametrize(
    ("reply", "allowed", "outcome", "ok"),
    [
        ("We can do 12 months.", ["12 months"], "open", True),
        # a bare "12" from "12 months" no longer licenses "$12" or "12%"
        ("Fine, $12 it is.", ["12 months"], "open", False),
        ("Twelve point five? No: 12% at most.", ["12 months"], "open", False),
        ("$1,200 is our number.", ["$1,200 a year"], "open", True),
        ("$1,200K is our number.", ["$1,200 a year"], "open", False),  # another unit
        ("We could go to 8.5%.", ["8.5% of the quote"], "open", True),
        # amounts in words
        ("A few hundred thousand more and we're there.", [], "open", False),
        ("Make it twenty percent and we talk.", [], "open", False),
        ("One more thing before we go on.", [], "open", True),
        # the wording may not state an outcome the engine did not decide
        ("We have a deal, congratulations.", [], "open", False),
        ("Agreed, let's move on.", [], "walked", False),
        ("We're done here, goodbye.", [], "open", False),
        ("We're done here, goodbye.", [], "walked", True),
        ("We have a deal, congratulations.", [], "agreed", True),
        ("That is the end of the road; we are walking away.", [], "agreed", False),
        ("You make a fair point about the volume.", [], "agreed", True),
    ],
)
def test_reply_checks_units_words_and_outcome(
    reply: str, allowed: list[str], outcome: classifier.OutcomeClass, ok: bool
) -> None:
    assert (classifier.reply_ok(reply, allowed, 40, outcome=outcome) is not None) is ok


# --- item 22: the folder's reservation ------------------------------------------------------
def test_a_call_costing_more_than_the_remaining_cap_is_refused(tmp_path: Path) -> None:
    add_spend(tmp_path, 0.0, conversation_cents=99.0, conversation_calls=1)
    assert budget.reserve(tmp_path, 100.0, 2.0) is None  # 99 + 2 > 100
    held = budget.reserve(tmp_path, 100.0, 1.0)
    assert held is not None
    assert budget.reserve(tmp_path, 100.0, 0.5) is None  # the open reservation counts
    budget.settle(tmp_path, held, 0.25, 1)
    assert month_spend(tmp_path).conversation_cents == pytest.approx(99.25)
    assert budget.outstanding(tmp_path) == 0.0
    assert budget.reserve(tmp_path, 100.0, 0.5) is not None


def test_simultaneous_reservations_never_pass_the_cap(tmp_path: Path) -> None:
    """Two saves in one folder (or two requests) reading the same remaining balance: the
    reservation is atomic, so of twenty racing calls of 10 cents under a 55-cent cap five
    get through."""
    start = threading.Barrier(20)
    got: list[bool] = []
    lock = threading.Lock()

    def call() -> None:
        start.wait()
        held = budget.reserve(tmp_path, 55.0, 10.0)
        with lock:
            got.append(held is not None)

    threads = [threading.Thread(target=call) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert sum(got) == 5
    assert budget.outstanding(tmp_path) == pytest.approx(50.0)


def test_a_crashed_reservation_lapses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    held = budget.reserve(tmp_path, 10.0, 10.0)
    assert held is not None and budget.reserve(tmp_path, 10.0, 1.0) is None
    later = time.time() + budget.STALE_S + 1
    monkeypatch.setattr(budget.time, "time", lambda: later)
    assert budget.reserve(tmp_path, 10.0, 1.0) is not None


# --- item 31: constant system prompts -------------------------------------------------------
def test_conversation_system_prompts_hold_no_name() -> None:
    """ADR-0023 point 6: the system prompts are constants (formatted only with the kind, the
    move list and limits), never a name, a company or anything the player typed."""
    import inspect

    from tst.conversations import meeting_prompts, prompts, talk_prompts

    for module in (prompts, meeting_prompts, talk_prompts):
        source = inspect.getsource(module)
        for name in ("name=", "org=", "role=", "company"):
            for line in source.splitlines():
                if "SYSTEM.format(" in line:
                    assert name not in line, (module.__name__, line)
        for key, value in vars(module).items():
            if key.endswith("_SYSTEM"):
                assert "{name}" not in value and "{org}" not in value and "{role}" not in value


# --- item 32: the test guard ----------------------------------------------------------------
def test_tests_use_the_mock_for_conversations_and_no_key() -> None:
    import os

    from tst.config import get_settings
    from tst.conversations.common import conversation_adapter

    assert os.environ["TST_CONVERSATION_ADAPTER"] == "mock"
    assert os.environ["TST_LLM_ADAPTER"] == "mock"
    get_settings.cache_clear()
    try:
        assert not get_settings().anthropic_api_key  # the empty value outranks any .env
        assert conversation_adapter(Path("/nonexistent")).name == "mock"
    finally:
        get_settings.cache_clear()
