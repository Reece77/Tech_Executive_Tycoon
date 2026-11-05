"""Create and edit saves for the M14b Playwright flows (an e2e fixture tool). Never used by
the game.

Every save is Kestrel, a funded spinout with $50M of extra cash made a stage-2 company: a live
B2B SaaS product (Pipeline, mid-market, against Salesforce, Oracle and Zoho) and a team of
engineers in a Product team, with what the company has learned about each of them.

- `launch <save dir> <name>`: two more B2B SaaS products in development, Forge (ready to
  launch) and Anvil (early). Forge is launched through the engine and a month is played, so
  the launch press moment waits as this month's event.
- `ready <save dir> <name>`: Anvil reaches launch quality and feature score with a price, as
  months of development would give it.
- `layoffs <save dir> <name>`: a launch press moment for Pipeline waits as this month's event
  (one month played), with twelve on the staff, so one firing is not a layoff.
- `jab <save dir> <name>`: Salesforce's CEO took a public jab at Kestrel (the statement and
  its inbox note, as phase 12 makes them): the jab press moment waits as this month's event
  (one month played).
- `poached <save dir> <name>`: a senior engineer has just accepted Salesforce's approach (on
  notice, the inbox note sent) and a recruiter is on staff.

Usage: uv run --project backend python tools/e2e_m14b_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
from tst.db.inbox import inbox_rows
from tst.db.mappers import entry_to_row
from tst.db.repository import (
    create_save,
    existing_save_path,
    load_state,
    open_session,
    run_action,
    run_turn,
)
from tst.db.state_io import sync_state
from tst.loader import LoadedData, load_all
from tst.sim.actions import CreateUnit, LaunchProduct, apply_action
from tst.sim.actions.products import launch_problems
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.press.moments import queue_moment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rivals import characters
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
    with_reveal,
)

SEED = 5
FOUNDER = 1
EXTRA_CASH = 50_000_000_00
CATEGORY = "b2b_saas"
SEGMENT = "mid_market"
PRICE = 50_000  # $500 a month
CUSTOMERS = 1_200.0  # $600k MRR: a stage-2 company
RIVAL = "Salesforce"
TEAM = [  # (role, level, salary in cents): the Product team
    ("software_engineer", "senior", 15_000_000),
    ("software_engineer", "senior", 15_000_000),
    ("software_engineer", "mid", 11_000_000),
    ("software_engineer", "mid", 11_000_000),
    ("software_engineer", "mid", 11_000_000),
    ("software_engineer", "junior", 8_000_000),
    ("product_manager", "senior", 14_000_000),
    ("designer", "mid", 10_000_000),
    ("sales_representative", "mid", 8_000_000),
    ("account_executive", "mid", 9_000_000),
    ("marketer", "mid", 9_000_000),
]


def _add_product(
    state: GameState, name: str, status: str, quality: float, fp: float, customers: float
) -> tuple[GameState, int]:
    pid, ids = state.next_ids.take("product")
    live = status == "live"
    product = Product(
        id=pid,
        company_id=1,
        category=CATEGORY,
        name=name,
        status=status,  # type: ignore[arg-type]
        quality=quality,
        feature_points=fp,
        brand=45.0 if live else 0.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn if live else None,
        first_customer_turn=state.turn if live else None,
    )
    state = replace(with_product(state, product), next_ids=ids)
    price = PRICE if live or name == "Forge" else None
    state = with_product_segment(state, ProductSegment(pid, SEGMENT, price, customers, False, 0))
    return state, pid


def _hire(
    state: GameState,
    data: LoadedData,
    role: str,
    level: str,
    salary: int,
    unit: int | None,
    n: int,
) -> GameState:
    """An employee as a hire leaves them: the company knows them as a hire does."""
    person_id, ids = state.next_ids.take("person")
    eid, ids = ids.take("employment")
    state = replace(state, next_ids=ids)
    gen = RngFactory(SEED).stream(0, "misc", 140 + n)
    person = generate_person(
        gen,
        data.game_data,
        data.balance,
        state.turn,
        data.game_data.role(role),
        level,
        "north_america",
        person_id=person_id,
    )
    state = with_person(state, person)
    reveal = new_reveal_state(
        observer_company_id=1,
        person=person,
        turn=state.turn,
        rng=RngFactory(SEED),
        data=data.game_data,
        balance=data.balance,
    )
    state = with_reveal(state, reveal)
    state = with_employment(
        state,
        Employment(
            id=eid,
            person_id=person_id,
            company_id=1,
            role=role,
            level=level,
            salary_cents=salary,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
            unit_id=unit,
        ),
    )
    return with_person_state(state, PersonState(person_id=person_id, morale=68.0))


def _company(state: GameState, data: LoadedData, extra: list[tuple[str, str, int]]) -> GameState:
    state, pid = _add_product(state, "Pipeline", "live", 62.0, 260.0, CUSTOMERS)
    mrr = round(CUSTOMERS * PRICE)
    company = reach_stage(state.player, 2, state.turn)
    history = tuple(round(mrr / 1.05**k) for k in range(12, -1, -1))
    company = replace(company, mrr_history=history, root_product_id=pid)
    state = with_company(state, company)
    out = apply_action(
        state,
        CreateUnit(FOUNDER, "team", "Product"),
        RngFactory(SEED),
        data.balance,
        data.game_data,
        {},
        seq=1,
    )
    state = out.new_state
    unit = max(u.id for u in state.units)
    for n, (role, level, salary) in enumerate([*TEAM, *extra]):
        state = _hire(state, data, role, level, salary, unit, n)
    return state


def _edit(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def _create(
    save_dir: Path, name: str, data: LoadedData, extra: list[tuple[str, str, int]] | None = None
) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0,
        company_id=1,
        memo="E2E funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=EXTRA_CASH,
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
    _edit(path, lambda s: _company(s, data, extra or []))
    return path


def _rival(state: GameState) -> int:
    return next(c.id for c in state.companies if c.is_rival and c.name == RIVAL)


def _named(state: GameState, name: str) -> int:
    return next(p.id for p in state.company_products(1) if p.name == name)


def launch(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)

    def products(s: GameState) -> GameState:
        s, _ = _add_product(s, "Forge", "in_development", 40.0, 260.0, 0.0)
        s, _ = _add_product(s, "Anvil", "in_development", 12.0, 40.0, 0.0)
        return s

    _edit(path, products)
    run_action(path, data, LaunchProduct(FOUNDER, _named(_state(path), "Forge")))
    run_turn(path, data)  # the launch press moment's event shows this month
    return path


def ready(path: Path, data: LoadedData) -> None:
    def ripen(s: GameState) -> GameState:
        anvil = s.product(_named(s, "Anvil"))
        s = with_product(s, replace(anvil, quality=40.0, feature_points=260.0))
        (seg,) = s.segments_of(anvil.id)
        s = with_product_segment(s, replace(seg, price_cents=PRICE))
        problems = launch_problems(s, s.product(anvil.id), data.balance, data.game_data)
        assert not problems, problems
        return s

    _edit(path, ripen)


def layoffs(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    _edit(path, lambda s: queue_moment(s, 1, "launch", {"product_id": _named(s, "Pipeline")}))
    run_turn(path, data)
    return path


def jab(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data)
    logs: list[LogItem] = []

    def queue(s: GameState) -> GameState:
        """What phase 12 does when a rival's CEO jabs (29.4): the statement, then the moment."""
        rival = _rival(s)
        their = next(p.id for p in s.company_products(rival) if p.category == CATEGORY)
        s, said = characters._speak(s, rival, "jab", their, 1)
        logs.extend(said)
        facts: dict[str, int | str] = {
            "rival_id": rival,
            "product_id": _named(s, "Pipeline"),
            "segment": SEGMENT,
        }
        return queue_moment(s, 1, "jab", facts)

    _edit(path, queue)
    with open_session(path) as session, session.begin():
        session.add_all(inbox_rows(logs, 1, data.game_data.inbox_templates))
    run_turn(path, data)
    return path


def poached(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = _create(save_dir, name, data, [("recruiter", "mid", 9_000_000)])
    run_turn(path, data)  # a month of history before the approach
    state = _state(path)
    engineer = next(
        e
        for e in state.staff(1)
        if e.role == "software_engineer" and e.level == "senior" and e.status == "active"
    )
    rival = _rival(state)

    def poach(s: GameState) -> GameState:
        e = s.employment_of(engineer.person_id)
        assert e is not None
        notice = replace(e, status="notice", end_turn=s.turn + 1, end_reason="poached")
        return with_employment(s, notice)

    _edit(path, poach)
    person = state.person(engineer.person_id)
    note = inbox_item(
        state.turn,
        1,
        "poach_accepted",
        link_kind="person",
        link_id=person.id,
        name=f"{person.first_name} {person.last_name}",
        rival=state.company(rival).name,
    )
    with open_session(path) as session, session.begin():
        session.add_all(inbox_rows([note], 1, data.game_data.inbox_templates))
    return path


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "launch":
        path = launch(save_dir, name, data)
    elif mode == "layoffs":
        path = layoffs(save_dir, name, data)
    elif mode == "jab":
        path = jab(save_dir, name, data)
    elif mode == "poached":
        path = poached(save_dir, name, data)
    elif mode == "ready":
        path = existing_save_path(save_dir, name)
        ready(path, data)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
