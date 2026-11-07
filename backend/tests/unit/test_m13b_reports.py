"""M13b sub-task 4 (formulas.md 27.2): quarterly reports led by decisions, in the executive's
voice from displayed personality; the CEO's letter to the Chair; no hidden value in a report
or its LLM prompt."""

from __future__ import annotations

import re
from dataclasses import replace

from tests.helpers import with_product
from tests.unit.test_m10c_executives import EXEC, _company, _give, _right_seed, _run
from tst.events.context import text_prompt
from tst.loader import LoadedData
from tst.sim.org.models import SEATS, ExecDecision
from tst.sim.org.reports import ceo_letter, report_text
from tst.sim.org.voices import voice_for
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, with_exec_decision

NUMBER = re.compile(r"\d")
ROLES = {
    "cto": "software_engineer",
    "cro": "account_executive",
    "cmo": "marketer",
    "coo": "operations_manager",
    "cfo": "finance_manager",
    "cpo": "product_manager",
}


def _quarter_end(loaded: LoadedData, seat: str) -> GameState:
    state = _company(loaded, seat, ROLES[seat], staff=3)
    state = with_product(state, customers={"smb": 120.0})
    state = _give(replace(state, turn=2), seat, loaded.balance)  # March: a report month
    product = state.company_products(1)[0]
    return with_exec_decision(
        state,
        ExecDecision(1, 1, seat, EXEC, 2, f"set {product.name}'s marketing to $9,000 a month"),
    )


def test_each_report_names_an_action_and_a_number(loaded: LoadedData) -> None:
    for seat in SEATS:
        state = _quarter_end(loaded, seat)
        text = report_text(state, seat, EXEC, 5_000_000, loaded.balance, loaded.game_data)
        assert "marketing to $9,000" in text, (seat, text)  # the action
        assert "quality now" in text  # where the product stands, tied to the action
        assert NUMBER.search(text), (seat, text)
        assert "{" not in text


def test_every_voice_renders_for_every_seat(loaded: LoadedData) -> None:
    """Template output for every seat in every voice (27.2): force each voice by the
    executive's displayed personality."""
    seen = set()
    for voice in loaded.game_data.voices:
        for seat in SEATS:
            state = _quarter_end(loaded, seat)
            person = state.person(EXEC)
            reveal = state.reveal(1, EXEC)
            assert reveal is not None
            traits = {"ambition": 10.0, "risk_appetite": 10.0, "sociability": 10.0}
            if voice.rule is not None:
                traits[voice.rule.trait] = 20.0 if voice.rule.at_least is not None else 1.0
            person = replace(person, personality=person.personality.updated(traits))
            reveal = replace(
                reveal,
                attributes=tuple(
                    (k, replace(r, hw=0.0, offset=0.0)) if k in traits else (k, r)
                    for k, r in reveal.attributes
                ),
            )
            state = replace(
                state,
                people=tuple(person if p.id == EXEC else p for p in state.people),
                reveals=tuple(
                    reveal if r.person_id == EXEC and r.observer_company_id == 1 else r
                    for r in state.reveals
                ),
            )
            chosen = voice_for(state, 1, EXEC, loaded.game_data.voices)
            text = report_text(state, seat, EXEC, 5_000_000, loaded.balance, loaded.game_data)
            assert "{" not in text and NUMBER.search(text)
            seen.add(chosen.key)
    assert seen == {v.key for v in loaded.game_data.voices}


def test_the_report_speaks_of_its_pitch(loaded: LoadedData) -> None:
    from tests.unit.test_m13b_pitches import _cpo, _pitching_seed
    from tests.unit.test_m13b_pitches import _run as pitch_run

    state = _cpo(loaded)
    out, _, _, _ = pitch_run(loaded, state, _pitching_seed(loaded, state))
    (pitch,) = out.pending_pitches(1)
    text = report_text(
        replace(out, turn=2), "cpo", EXEC, 5_000_000, loaded.balance, loaded.game_data
    )
    assert pitch.title in text and "in 24 months (pending)" in text


def test_no_hidden_value_in_a_report_or_its_prompt(loaded: LoadedData) -> None:
    """Plant unmistakable true values (ambition, skills, potential): the report and the LLM
    prompt built from it show none of them; the voice follows the displayed range (27.6)."""
    for seat in SEATS:
        state = _quarter_end(loaded, seat)
        person = state.person(EXEC)
        planted = person.personality.updated({"ambition": 17.777, "risk_appetite": 3.333})
        skills = person.skills.updated({k: 13.579 for k in person.skills.as_dict()})
        person = replace(person, personality=planted, skills=skills, potential_ability=187.6)
        state = replace(state, people=tuple(person if p.id == EXEC else p for p in state.people))
        text = report_text(state, seat, EXEC, 5_000_000, loaded.balance, loaded.game_data)
        system, user = text_prompt("exec_report", [text], state.player.name)
        blob = system + user
        for value in ("17.777", "17.78", "3.333", "13.579", "13.58", "187.6"):
            assert value not in blob, (seat, value)
        reveal = state.reveal(1, EXEC)
        assert reveal is not None
        lo, hi = revealed_range(person, reveal, "ambition")
        voice = voice_for(state, 1, EXEC, loaded.game_data.voices)
        if voice.key == "blunt":
            assert (lo + hi) / 2 >= 14


def test_the_ceo_writes_a_letter_to_the_chair(loaded: LoadedData) -> None:
    from tests.unit.test_m13_ceo import CEO, staffed, with_ceo_appointed

    state = with_ceo_appointed(staffed())
    letter = ceo_letter(
        state, CEO, ("cto", "cro", "products"), 5_000_000, loaded.balance, loaded.game_data
    )
    assert letter.startswith("Dear Chair,") and "I ran CTO, CRO, products." in letter
    assert "Across the company:" in letter and NUMBER.search(letter)


def test_quarterly_reports_still_come_from_run_executives(loaded: LoadedData) -> None:
    state = _quarter_end(loaded, "cto")
    seed = _right_seed(loaded, state, "cto", right=True)
    _, _, logs, _ = _run(loaded, state, seed)
    reports = [i for i in logs if i.template == "exec_report"]
    assert reports and "$9,000" in str(dict(reports[0].params)["report"])


def test_a_report_after_a_marked_quarter_shows_start_and_now(loaded: LoadedData) -> None:
    """M15b (an M13b follow-up): with the last quarter's marks, a report reads "41 -> 47"."""
    from tst.sim.org.reports import mark_quarter
    from tst.sim.state import with_product as put

    state = _quarter_end(loaded, "cmo")
    marked = mark_quarter(state, loaded.balance)
    product = marked.company_products(1)[0]
    assert {m.product_id for m in marked.quarter_marks} == {product.id}
    later = put(marked, replace(product, quality=product.quality + 6))
    text = report_text(later, "cmo", EXEC, 5_000_000, loaded.balance, loaded.game_data)
    assert f"quality {product.quality:.0f} -> {product.quality + 6:.0f}" in text, text
    assert mark_quarter(replace(state, turn=3), loaded.balance).quarter_marks == ()  # April
