"""Inbox: templated log items become rendered messages for the player company."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.helpers import (
    FIRST_PRODUCT,
    fresh_game,
    make_person,
    mark_interviewed,
    move_directors,
    move_save_directors,
    with_employee,
    with_product,
)
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
    AppointExecutive,
    CreatePlan,
    CreateProduct,
    CreateUnit,
    Fire,
    Interview,
    LaunchProduct,
    MakeOffer,
    MovePerson,
    OpenSearch,
    RemoveExecutive,
    SetLeader,
)
from tst.sim.actions.geo import CloseOffice, LaunchInRegion, LeaseOffice
from tst.sim.data_models import INBOX_TEMPLATE_KEYS
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import GameState, reach_stage, with_company, with_employment, with_event

# Market news (M5) and events (M6) arrive alongside; these tests are about other messages.
NOT_PRODUCT_NOTES = ("market_news", "event", "critical_event")


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


@dataclass
class FinanceGames:
    games: tuple[Game, ...]
    extra: list[LogItem]


def finance_games(loaded: LoadedData) -> FinanceGames:
    from tests.unit.test_board import board_after
    from tests.unit.test_fundraising import garage
    from tests.unit.test_insolvency import broke_game
    from tst.sim.actions import AcceptBridge, AcceptTermSheet, RaiseSafe, StartRound
    from tst.sim.finance.board import board_month

    raised = garage(loaded)  # seed 16: investors answer its seed
    raised.act(RaiseSafe(1, 30_000_000, 100_000_000))  # fills
    raised.turn()
    raised.act(RaiseSafe(1, 30_000_000, 5_000_000_000))  # does not
    raised.act(StartRound(1, "seed", 150_000_000))
    raised.turn()
    best = max(raised.state.term_sheets, key=lambda t: t.pre_money_cents)
    raised.act(AcceptTermSheet(1, best.id))
    raised.turn()  # closes
    lapsed = garage(loaded)
    lapsed.act(StartRound(1, "seed", 150_000_000))
    for _ in range(3):
        lapsed.turn()
    nobody = garage(loaded, seed=2)  # no firm answers this seed's round
    nobody.act(StartRound(1, "seed", 150_000_000))
    nobody.turn()
    bankrupt = broke_game(loaded, "garage_bootstrap")
    for _ in range(3):
        bankrupt.turn()
    bridged = broke_game(loaded, "funded_spinout")
    bridged.turn()
    bridged.act(AcceptBridge(1, bridged.state.safes[0].id))
    bridged.turn()
    unbridged = broke_game(loaded, "funded_spinout")
    unbridged.turn()
    unbridged.balances = {**unbridged.balances, (1, CASH): 100_000_000}
    for _ in range(3):
        unbridged.turn()
    spinout = move_directors(fresh_game(loaded, scenario="funded_spinout"))
    seeded = Game(
        loaded, with_employee(loaded, spinout, make_person(loaded, 2), 9_000_000), 150_000_000
    )
    seeded.turn()  # the first hire, then stage 2 from the seed
    extra: list[LogItem] = []
    state = replace(board_after(loaded, "b"), turn=2)  # March: a meeting
    for _ in range(12):  # no cash, no growth: a warning, then the removal vote
        state, logs = board_month(state, {1: -1}, loaded.balance, loaded.game_data)
        extra += logs
        if state.ended:
            break
        state = replace(state, turn=state.turn + 1)
    # M4c: a Series A with no one to nominate leaves the seat empty; a nominee who leaves.
    from tests.unit.test_board import series_a, spinout_with_staff
    from tst.sim.actions import Fire
    from tst.sim.state import with_company

    empty = Game(loaded, board_after(loaded, "seed"), 500_000_000)
    empty.state = with_company(empty.state, replace(empty.state.player, mrr_history=(10**7,) * 7))
    empty.act(StartRound(1, "a", 600_000_000))
    empty.turn()
    empty.act(AcceptTermSheet(1, next(t for t in empty.state.term_sheets).id))
    empty.turn()
    nominee = spinout_with_staff(loaded)
    series_a(nominee, 2)
    nominee.act(Fire(1, 2))
    # M5: rivals with no cash fail after three month ends (15.1).
    starved = Game(loaded, fresh_game(loaded, 9), 400_000_000)
    starved.balances = {(1, CASH): 400_000_000}
    for _ in range(3):
        starved.turn()
    # M5: a rival approaches; one person stays, another (offered a fortune) goes.
    from tests.unit.test_rivals import _by_name, _with_staff
    from tst.sim.rivals.decisions import approach, approach_note
    from tst.sim.state import with_approach

    poached, pid = _with_staff(loaded)
    rival = poached.state.company(_by_name(poached.state, "Salesforce"))
    poached.state = approach(poached.state, rival, pid, loaded.balance, loaded.game_data)
    extra.append(approach_note(poached.state, poached.state.approaches[0]))
    rich = replace(poached.state.approaches[0], offer_cents=40_000_000)  # a fortune: they go
    poached.state = with_approach(poached.state, rich)
    poached.turn()
    poached.turn()
    loyal, kept = _with_staff(loaded)
    loyal.state = approach(loyal.state, rival, kept, loaded.balance, loaded.game_data)
    made = loyal.state.approaches[0]
    loyal.state = with_approach(loyal.state, replace(made, offer_cents=1))
    loyal.turn()
    loyal.turn()
    return FinanceGames(
        (
            raised,
            lapsed,
            nobody,
            bankrupt,
            bridged,
            unbridged,
            seeded,
            empty,
            nominee,
            starved,
            poached,
            loyal,
        ),
        extra,
    )


def _loan_items(loaded: LoadedData) -> list[LogItem]:
    """M10 (20.3): signing, a breach, a called loan, and a loan repaid."""
    from tst.balance.game import start_game
    from tst.sim.actions import RepayLoan, TakeLoan, apply_action
    from tst.sim.finance.debt import debt_month
    from tst.sim.ledger import apply_entries
    from tst.sim.rng import RngFactory

    b, data = loaded.balance, loaded.game_data
    game = start_game(loaded, 4, scenario="funded_spinout")
    rng = RngFactory(4)
    out = apply_action(
        game.state, TakeLoan(game.founder_id, "venture_debt", 20_000_000), rng, b, data,
        game.balances, seq=1,
    )  # fmt: skip
    items = list(out.log_items)
    state, balances = out.new_state, apply_entries(game.balances, out.ledger_entries)
    loan = state.company_loans(1)[0]
    repaid = apply_action(state, RepayLoan(game.founder_id, loan.id), rng, b, data, balances, seq=2)
    items += repaid.log_items
    for turn in (state.turn, state.turn + b.debt.breach.cure_months + 1):
        state = replace(state, turn=turn)
        state = replace(
            state,
            companies=tuple(
                replace(c, burn_history=(10**12,)) if c.is_player else c for c in state.companies
            ),
        )
        state, entries, logs = debt_month(state, balances, b, data)
        balances = apply_entries(balances, entries)
        items += logs
    return items


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
                game.state = mark_interviewed(game.state)
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
    # M3a: a launch, first customers, an ARR milestone, sales capacity and a product nobody
    # works on.
    products = Game(loaded, fresh_game(loaded, 7))
    products.state = with_product(
        products.state,
        status="in_development",
        quality=30,
        feature_points=40,
        brand=30,
        prices={"smb": 4000, "mid_market": 70_000},
        root=False,
    )
    products.state = with_product(
        products.state, name="Ledger", customers={"smb": 3000.0}, root=False
    )
    products.act(LaunchProduct(1, FIRST_PRODUCT))
    products.turn()
    # M4a: SAFEs that fill and do not, rounds that close, find no investor or lapse, the
    # board's meetings, warnings and removal vote, insolvency, bridges and bankruptcy.
    # M8: a division, an executive appointed and removed, and one who leaves.
    scale = Game(loaded, _stage_3(loaded))
    scale.act(CreateUnit(1, "division", "Platform"))
    scale.act(AppointExecutive(1, "cto", 50))
    scale.act(RemoveExecutive(1, "cto"))
    scale.act(AppointExecutive(1, "cfo", 51))
    scale.act(Fire(1, 51))
    # M9: an office leased and closed; a product launched in a region that goes live.
    geo = Game(loaded, with_product(fresh_game(loaded, 8), quality=60, feature_points=200))
    geo.act(LeaseOffice(1, "berlin", 25))
    geo.act(CloseOffice(1, geo.state.company_offices(1)[0].id))
    geo.act(LaunchInRegion(1, FIRST_PRODUCT, "europe"))
    for _ in range(3):
        geo.turn()
    finance = finance_games(loaded)
    games = (sad, hiring, broke, org, delegated, products, scale, geo, *finance.games)
    items = [i for g in games for r in g.results for i in r.log_items]
    items += [i for g in games for i in g.action_logs] + finance.extra
    items += _loan_items(loaded)  # M10
    items += _m10b_items(loaded)
    for item in items:
        if item.template is None:
            continue
        title, body = render(item, templates)
        assert "{" not in title + body, (item.template, title, body)
        seen.add(item.template)
    print(f"templates exercised: {sorted(seen)}")
    assert seen == set(INBOX_TEMPLATE_KEYS)


def _m10b_items(loaded: LoadedData) -> list[LogItem]:
    """A counter-offer that keeps someone, and the month-end line on the month's choices."""
    from tests.unit.test_event_effects import _open
    from tst.sim.events.effects import apply_choice
    from tst.sim.events.models import Effect, EventChoice
    from tst.sim.rng import RngFactory
    from tst.sim.turn import TurnContext, snapshot_and_month_end_report

    state = with_employee(loaded, fresh_game(loaded), make_person(loaded, 60), 9_000_000)
    state = with_product(state, customers={"smb": 100.0})
    e = state.employment_of(60)
    assert e is not None
    state = with_employment(
        state, replace(e, status="notice", end_turn=state.turn + 1, end_reason="resigned")
    )
    product = state.company_products(1)[0].id
    effects = (
        Effect("retain", "person:60"),
        Effect("modifier", f"product:{product}", 5.0, "awareness", 3),
    )
    event = _open(state, (EventChoice("A", "Counter", effects),), severity="critical")
    state = with_event(state, event)
    state, _, logs = apply_choice(state, event, "A", loaded.balance, loaded.game_data, auto=False)
    ctx = TurnContext(
        state=state,
        decisions=Decisions(),
        rng=RngFactory(1),
        balance=loaded.balance,
        data=loaded.game_data,
        opening_balances={(1, "1000_cash"): 10**9},
        balances={(1, "1000_cash"): 10**9},
    )
    out = snapshot_and_month_end_report(ctx)
    return [*logs, *out.log_items]


def _stage_3(loaded: LoadedData) -> GameState:
    state = fresh_game(loaded)
    for pid in (50, 51):
        state = with_employee(loaded, state, make_person(loaded, pid, level="senior"), 12_000_000)
    return with_company(state, reach_stage(state.player, 3, 0))


def test_inbox_persists_from_turns_and_actions(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "inbox", 6, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_turn(path, loaded)
    with open_session(path) as session:
        state = load_state(session)
        messages = list_inbox(session, 1)
    assert [m.template for m in messages if m.template not in NOT_PRODUCT_NOTES] == [
        "candidates_arrived"
    ]
    arrived = next(m for m in messages if m.template == "candidates_arrived")
    assert arrived.link_kind == "search" and arrived.link_id == 1
    assert arrived.title.endswith("candidates for Software engineer")
    for c in state.candidates:
        ask = state.person(c.person_id).salary_expectation_cents or 0
        run_action(path, loaded, Interview(1, c.person_id))
        run_action(path, loaded, MakeOffer(1, c.person_id, round(ask * 1.5), 0))
    run_turn(path, loaded)
    with open_session(path) as session, session.begin():
        # an event answered at Continue archives itself, read (23.1, M10b)
        messages = list_inbox(session, 1, archived=False)
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
    move_save_directors(path)
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


def test_product_notes_reach_the_inbox(tmp_path: Path, loaded: LoadedData) -> None:
    path = create_save(
        "prodinbox", 6, "funded_spinout", company_name="Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, CreateProduct(1, "Pipeline", "b2b_saas", ("smb",)))
    run_turn(path, loaded)  # nobody works on it
    with open_session(path) as session:
        [message] = [m for m in list_inbox(session, 1) if m.template not in NOT_PRODUCT_NOTES]
    assert message.template == "product_rotting"
    assert (message.link_kind, message.link_id) == ("product", FIRST_PRODUCT)
    assert message.title == "Pipeline is slipping"
    assert "Assign a unit to it." in message.body


def test_upgrade_to_0012_keeps_items_unarchived(tmp_path: Path, loaded: LoadedData) -> None:
    """M4c: migration 0012 adds inbox_item.archived; existing items stay in the inbox."""
    from tst.db import migrate

    path = create_save(
        "arch", 6, "ex_big_tech_founders", company_name="Co", data=loaded, save_dir=tmp_path
    )
    run_action(path, loaded, OpenSearch(1, "software_engineer", "job_post"))
    run_turn(path, loaded)
    migrate.downgrade(path, "0011_board_nominee")
    assert migrate.ensure_current(path) is not None
    with open_session(path) as session:
        items = list_inbox(session, 1, archived=False)
        assert items and not any(m.archived for m in items)
        assert list_inbox(session, 1, archived=True) == []
