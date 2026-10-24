"""Inbox: templated log items become rendered messages for the player company."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.helpers import fresh_game, make_person, with_employee
from tests.unit.test_hiring_phases import Game, _staff_game
from tst.db.inbox import (
    UnknownInboxItemError,
    indefinite_article,
    list_inbox,
    mark_read,
    render,
    unread_count,
)
from tst.db.repository import create_save, open_session, run_action, run_turn
from tst.db.state_io import load_state, sync_state
from tst.loader import LoadedData
from tst.sim.actions import (
    CreatePlan,
    CreateUnit,
    Fire,
    MakeOffer,
    MovePerson,
    OpenSearch,
    SetLeader,
)
from tst.sim.data_models import INBOX_TEMPLATE_KEYS
from tst.sim.log import inbox_item


def test_render_formats_money(loaded: LoadedData) -> None:
    item = inbox_item(3, 1, "fired", name="Ada Mensah", severance_cents=958_333)
    title, body = render(item, loaded.game_data.inbox_templates)
    assert title == "Ada Mensah was let go"
    assert body == "Ada Mensah has left the company. Severance of $9,583.33 was paid."


@pytest.mark.parametrize(
    ("word", "article"),
    [
        ("Account executive", "an"),
        ("Designer", "a"),
        ("exec", "an"),
        ("mid", "a"),
        ("Operations manager", "an"),
        ("junior", "a"),
        ("user researcher", "a"),
    ],
)
def test_indefinite_article(word: str, article: str) -> None:
    assert indefinite_article(word) == article


def test_render_uses_an_before_vowel_sounds(loaded: LoadedData) -> None:
    item = inbox_item(
        1, 1, "candidates_arrived", channel="job post", role="Account executive", count=3, shelf=3
    )
    _, body = render(item, loaded.game_data.inbox_templates)
    assert body.startswith("Your job post search for an Account executive turned up 3")


def test_every_emitted_template_renders(loaded: LoadedData) -> None:
    """Run seeded games that hit hiring, departures, reveals and debt; render every item."""
    templates = loaded.game_data.inbox_templates
    seen: set[str] = set()

    sad = _staff_game(loaded, 2, 0.6, False)
    people = []
    for p in sad.state.people:
        if p.id in (20, 21):  # two over-60s, to exercise retirement
            p = replace(p, birth_turn=-12 * 66)
        if p.id in (22, 23, 24):  # tagged, to exercise monthly reveals
            p = replace(p, tags=("mentor", "maverick"))
        people.append(p)
    sad.state = replace(sad.state, people=tuple(people))
    hiring = Game(loaded, fresh_game(loaded, 6))
    hiring.act(OpenSearch(1, "software_engineer", "job_post"))
    for game, turns in ((sad, 60), (hiring, 3)):
        for t in range(turns):
            game.turn()
            if game is hiring and t == 0:
                for c in game.state.candidates:
                    ask = game.state.person(c.person_id).salary_expectation_cents or 0
                    ratio = 1.4 if c.person_id % 2 else 0.5
                    game.act(MakeOffer(1, c.person_id, round(ask * ratio), 0))
    carrier = replace(make_person(loaded, 30), tags=("culture_carrier",))
    broke = Game(loaded, with_employee(loaded, fresh_game(loaded), carrier, 9_000_000), cash=0)
    broke.act(Fire(1, 30))
    broke.turn()
    lead = make_person(loaded, 40)
    org = Game(loaded, with_employee(loaded, fresh_game(loaded), lead, 9_000_000))
    org.act(CreateUnit(1, "team", "Platform"))
    org.act(MovePerson(1, 40, 1))
    org.act(SetLeader(1, 1, 40))
    org.act(CreatePlan(1, 40, "designer", 1, "network", 10_000))
    org.act(Fire(1, 40))  # the unit loses its leader and the plan pauses
    recruiter = make_person(loaded, 41, "recruiter", "senior")
    delegated = Game(loaded, with_employee(loaded, fresh_game(loaded), recruiter, 9_000_000))
    delegated.state = replace(
        delegated.state, next_ids=replace(delegated.state.next_ids, person=42)
    )
    delegated.act(CreatePlan(1, 41, "software_engineer", 1, "job_post", 12_000))
    for _ in range(4):
        delegated.turn()  # activity summaries, then the plan fills
    games = (sad, hiring, broke, org, delegated)
    items = [i for g in games for r in g.results for i in r.log_items]
    items += [i for g in games for i in g.action_logs]
    for item in items:
        if item.template is None:
            continue
        title, body = render(item, templates)
        assert "{" not in title + body, (item.template, title, body)
        seen.add(item.template)
    print(f"templates exercised: {sorted(seen)}")
    assert seen == set(INBOX_TEMPLATE_KEYS)


def test_inbox_persists_from_turns_and_actions(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "inbox", 6, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
        messages = list_inbox(session, 1)
    assert [m.template for m in messages] == ["candidates_arrived"]
    arrived = messages[0]
    assert arrived.link_kind == "search" and arrived.link_id == 1
    assert arrived.title.endswith("candidates for Software engineer")
    for c in state.candidates:
        ask = state.person(c.person_id).salary_expectation_cents or 0
        run_action(path, loaded, MakeOffer(1, c.person_id, round(ask * 1.5), 0))
    run_turn(path, loaded)
    with open_session(path) as session, session.begin():
        messages = list_inbox(session, 1)
        accepted = [m for m in messages if m.template == "offer_accepted"]
        assert accepted and all(m.link_kind == "person" for m in accepted)
        assert "a year" in accepted[0].body and "$" in accepted[0].body
        assert unread_count(session, 1) == len(messages)
        read = mark_read(session, 1, messages[0].id)
        assert read.read
        with pytest.raises(UnknownInboxItemError):
            mark_read(session, 1, 9999)
    with open_session(path) as session:
        assert unread_count(session, 1) == len(messages) - 1
        assert [m.id for m in list_inbox(session, 1, unread_only=True)] == [
            m.id for m in messages[1:]
        ]
        assert len(list_inbox(session, 1, limit=2)) == 2


def test_fired_culture_carrier_is_stored_and_announced(tmp_path: Path, loaded: LoadedData) -> None:
    """Firing a culture carrier reveals the tag to the company and says so in the inbox."""
    path = create_save(
        "carrier", 2, "funded_spinout", company_name="Co", data=loaded, save_dir=tmp_path
    )
    with open_session(path) as session, session.begin():
        before = load_state(session)
        carrier = replace(make_person(loaded, 2), tags=("culture_carrier",))
        sync_state(session, before, with_employee(loaded, before, carrier, 9_000_000))
    run_action(path, loaded, Fire(1, 2))
    name = f"{carrier.first_name} {carrier.last_name}"
    with open_session(path) as session:
        newest = list_inbox(session, 1)[0]
        tags = session.execute(
            text("SELECT tag, revealed_turn FROM person_tag_reveal WHERE person_id = 2")
        ).all()
    assert newest.title == f"{name}'s departure hit the team"
    assert newest.body == f"The team took {name}'s departure hard; they held the team together."
    assert [tuple(t) for t in tags] == [("culture_carrier", 0)]
