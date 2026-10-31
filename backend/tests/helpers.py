"""Shared builders for tests: a fresh game with candidates, employees and products."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from tst.loader import LoadedData
from tst.sim.hiring.models import Candidate, PersonState, Search
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment, Person
from tst.sim.people.reveal import new_reveal_state
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import (
    GameState,
    with_candidate,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_product_segment,
    with_reveal,
    with_search,
)
from tst.sim.state import with_product as put_product

_FRESH: dict[tuple[int, int, str, tuple[str, ...] | None], GameState] = {}


def fresh_game(
    loaded: LoadedData,
    seed: int = 3,
    scenario: str = "ex_big_tech_founders",
    mission: tuple[str, ...] | None = None,
) -> GameState:
    """A new game's state. new_game is pure and the state immutable, so one per arguments
    is built and shared (tests build hundreds; M6 sub-task 0)."""
    key = (id(loaded), seed, scenario, mission)
    if key not in _FRESH:
        _FRESH[key] = _new_game(loaded, seed, scenario, mission)
    return _FRESH[key]


def _new_game(
    loaded: LoadedData, seed: int, scenario: str, mission: tuple[str, ...] | None
) -> GameState:
    scenario_def = loaded.game_data.scenario(scenario)
    assert scenario_def is not None
    state, _ = new_game(
        save_name="t",
        master_seed=seed,
        scenario=scenario_def,
        difficulty="standard",
        company_name="Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
        mission=mission,
    )
    return move_directors(state)


def rival_cash(state: GameState, loaded: LoadedData) -> dict[tuple[int, str], int]:
    """Opening cash of every incumbent, as new_game posts it (M5, 15.1): add it to a test's
    ledger balances so rivals are not insolvent from the first month."""
    from tst.sim.ledger import CASH
    from tst.sim.rivals.setup import opening_cash_cents

    return {
        (c.id, CASH): opening_cash_cents(state, c.id, loaded.game_data)
        for c in state.companies
        if not c.is_player
    }


def last_hire(state: GameState, company_id: int = 1) -> Employment:
    """The company's newest employment (rivals' key people have employments too, M5)."""
    return max((e for e in state.employments if e.company_id == company_id), key=lambda e: e.id)


DIRECTOR_IDS_FROM = 900  # test fixtures put employees at ids 2.., so directors move out of the way
FIRST_PRODUCT = 18  # the first product id after the 17 incumbent products (M8 added five)
INCUMBENTS = 17  # incumbent companies (ids 2..18)


def move_directors(state: GameState) -> GameState:
    """Re-id generated board directors (the funded spinout's seed director) to 900.. so test
    fixtures can put employees at fixed ids from 2. Real games never need this: every id
    comes from next_ids."""
    directors = sorted({s.person_id for s in state.seats if s.kind != "common"})
    if not directors:
        return state
    new_id = {old: DIRECTOR_IDS_FROM + i for i, old in enumerate(directors)}
    people = tuple(
        sorted((replace(p, id=new_id.get(p.id, p.id)) for p in state.people), key=lambda p: p.id)
    )
    seats = tuple(replace(s, person_id=new_id.get(s.person_id, s.person_id)) for s in state.seats)
    return replace(state, people=people, seats=seats)


def move_save_directors(path: Path) -> None:
    """move_directors for a save file: the same re-id in every table keyed by person id."""
    from sqlalchemy import text

    from tst.db.models import Base
    from tst.db.repository import open_session

    with open_session(path) as session, session.begin():
        rows = session.execute(
            text("SELECT person_id FROM board_seat WHERE kind != 'common' ORDER BY person_id")
        ).all()
        session.execute(text("PRAGMA defer_foreign_keys = ON"))
        for i, (old,) in enumerate(rows):
            new = DIRECTOR_IDS_FROM + i
            for table in Base.metadata.sorted_tables:
                if "person_id" in table.c and table.name != "decision_log":
                    session.execute(
                        text(f"UPDATE {table.name} SET person_id = :n WHERE person_id = :o"),
                        {"n": new, "o": old},
                    )
            session.execute(text("UPDATE person SET id = :n WHERE id = :o"), {"n": new, "o": old})


def make_person(
    loaded: LoadedData, person_id: int, role: str = "software_engineer", level: str = "mid"
) -> Person:
    gen = RngFactory(person_id).stream(0, "misc", person_id)
    return generate_person(
        gen,
        loaded.game_data,
        loaded.balance,
        0,
        loaded.game_data.role(role),
        level,
        "north_america",
        person_id=person_id,
    )


def with_candidates(
    loaded: LoadedData,
    state: GameState,
    count: int,
    role: str = "software_engineer",
    *,
    interviewed: bool = False,
) -> GameState:
    """Add an open job-post search and `count` candidates known as strangers.

    `interviewed` marks them as interviewed (the ADR-0016 offer precondition) without
    narrowing anything, for tests about offers rather than interviews.
    """
    search_id, ids = state.next_ids.take("search")
    state = with_search(
        state,
        Search(search_id, 1, role, "job_post", actor_id=1, opened_turn=state.turn),
    )
    first, ids = ids.take_many("person", count)
    state = replace(state, next_ids=ids)
    for pid in range(first, first + count):
        person = make_person(loaded, pid, role)
        state = with_person(state, person)
        state = with_candidate(
            state,
            Candidate(
                person_id=pid,
                company_id=1,
                search_id=search_id,
                channel="job_post",
                created_turn=state.turn,
                expires_turn=state.turn + loaded.balance.hiring.candidate_shelf_turns,
                interviewed_turn=state.turn if interviewed else None,
            ),
        )
        state = with_reveal(
            state,
            new_reveal_state(
                observer_company_id=1,
                person=person,
                turn=state.turn,
                rng=RngFactory(state.save_meta.master_seed),
                data=loaded.game_data,
                balance=loaded.balance,
            ),
        )
    return state


def mark_interviewed(state: GameState) -> GameState:
    """Mark every open candidate as interviewed this turn (the ADR-0016 offer precondition)
    without narrowing knowledge or drawing anything, for tests about offers."""
    return replace(
        state,
        candidates=tuple(
            replace(c, interviewed_turn=state.turn)
            if c.status == "open" and c.interviewed_turn is None
            else c
            for c in state.candidates
        ),
    )


def with_employee(
    loaded: LoadedData,
    state: GameState,
    person: Person,
    salary_cents: int,
    equity_bp: int = 0,
    morale: float = 65.0,
) -> GameState:
    emp_id, ids = state.next_ids.take("employment")
    state = replace(state, next_ids=ids)
    state = with_person(state, person)
    state = with_employment(
        state,
        Employment(
            id=emp_id,
            person_id=person.id,
            company_id=1,
            role=person.role or "software_engineer",
            level=person.level or "mid",
            salary_cents=salary_cents,
            equity_bp=equity_bp,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    state = with_person_state(state, PersonState(person_id=person.id, morale=morale))
    # Real hires keep the knowledge record they had as candidates.
    return with_reveal(
        state,
        new_reveal_state(
            observer_company_id=1,
            person=person,
            turn=state.turn,
            rng=RngFactory(state.save_meta.master_seed),
            data=loaded.game_data,
            balance=loaded.balance,
        ),
    )


def with_product(
    state: GameState,
    *,
    product_id: int | None = None,
    category: str = "b2b_saas",
    prices: dict[str, int | None] | None = None,
    status: str = "live",
    quality: float = 40.0,
    feature_points: float = 0.0,
    brand: float = 10.0,
    budget_cents: int = 0,
    customers: dict[str, float] | None = None,
    root: bool = True,
    name: str = "Pipeline",
) -> GameState:
    """A player product (default: live B2B SaaS in SMB at $40), worked on by the root."""
    pid, ids = (product_id, state.next_ids) if product_id else state.next_ids.take("product")
    prices = {"smb": 4000} if prices is None else prices
    product = Product(
        id=pid,
        company_id=1,
        category=category,
        name=name,
        status=status,  # type: ignore[arg-type]
        quality=quality,
        feature_points=feature_points,
        brand=brand,
        marketing_budget_cents=budget_cents,
        created_turn=state.turn,
        launched_turn=state.turn if status != "in_development" else None,
    )
    state = replace(put_product(state, product), next_ids=ids)
    for seg, price in prices.items():
        held = (customers or {}).get(seg, 0.0)
        segment = ProductSegment(pid, seg, price, held, False, state.turn)
        state = with_product_segment(state, segment)
    if root:
        state = with_company(state, replace(state.player, root_product_id=pid))
    return state


def fund_save(path: Path, cents: int) -> None:
    """Extra owner's money on turn 0, for tests about speed or flows rather than solvency:
    since M4 three months of negative cash end the game (formulas.md 14.7)."""
    from tst.db.mappers import entry_to_row
    from tst.db.repository import open_session
    from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry

    entry = LedgerEntry.transfer(
        turn=0, company_id=1, memo="Test funding", debit=CASH, credit=COMMON_EQUITY, amount=cents
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))


def event_cash_cents(path: Path, company_id: int = 1, through_turn: int | None = None) -> int:
    """Cash moved by answered events (M6, formulas.md 16.3): their ledger entries carry an
    "Event:" memo. Tests about overheads add it to the expected cash."""
    from sqlalchemy import func, select

    from tst.db.models import LedgerEntryRow, LedgerLineRow
    from tst.db.repository import open_session
    from tst.sim.ledger import CASH

    stmt = (
        select(func.coalesce(func.sum(LedgerLineRow.amount_cents), 0))
        .join(LedgerEntryRow, LedgerLineRow.entry_id == LedgerEntryRow.id)
        .where(
            LedgerEntryRow.company_id == company_id,
            LedgerEntryRow.memo.like("Event:%"),
            LedgerLineRow.account_code == CASH,
        )
    )
    if through_turn is not None:
        stmt = stmt.where(LedgerEntryRow.turn <= through_turn)
    with open_session(path) as session:
        return int(session.scalar(stmt) or 0)


def answer_critical(path: Path, loaded: LoadedData) -> None:
    """Answer any open critical event with its first choice, as a player must before Continue
    (M6, ADR-0006 amended). Scripts that run a company low on cash call this each month."""
    from tst.db.repository import load_state, open_session, run_action
    from tst.sim.actions import ChooseEvent

    with open_session(path) as session:
        state = load_state(session)
    founder = state.founder_of(state.player.id)
    for event in state.open_events(state.player.id):
        if event.severity == "critical" and event.status == "open" and founder is not None:
            run_action(path, loaded, ChooseEvent(founder.id, event.id, event.choices[0].key))


def play_turn(path: Path, loaded: LoadedData) -> Any:
    """run_turn after answering any open critical event (M6)."""
    from tst.db.repository import run_turn

    answer_critical(path, loaded)
    return run_turn(path, loaded)


def open_event(
    path: Path,
    loaded: LoadedData,
    template: str = "low_morale_checkin",
    *,
    severity: str = "major",
    person_ids: tuple[int, ...] = (),
) -> int:
    """Stand in for the director: queue one event for this month in a save and let the event
    service write it with templates (M6). Returns the event id."""
    from tst.db.events import write_pending
    from tst.db.repository import load_state, write_session
    from tst.db.state_io import sync_state
    from tst.llm.offline import TemplateAdapter
    from tst.sim.events.models import GameEvent
    from tst.sim.state import with_event

    spec = loaded.game_data.event_template(template)
    with write_session(path) as session:
        state = load_state(session)
        event_id, ids = state.next_ids.take("event")
        event = GameEvent(
            id=event_id,
            company_id=1,
            turn=state.turn,
            template_id=template,
            category=spec.category,
            severity=severity,  # type: ignore[arg-type]
            trigger=spec.trigger,
            strength=1.0,
            person_ids=person_ids,
            months=2 if spec.trigger == "runway_short" else None,
            cash_base_cents=50_000_000,
        )
        sync_state(session, state, with_event(replace(state, next_ids=ids), event))
    write_pending(path, loaded, adapter=TemplateAdapter())
    return event_id
