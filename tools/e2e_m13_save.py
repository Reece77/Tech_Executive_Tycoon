"""Create and edit saves for the M13 Playwright flows and API tests (an e2e fixture tool).
Never used by the game.

- `eligible <save dir> <name>`: Kestrel, a funded spinout made a stage-3 scale-up: a live
  B2B SaaS product earning about $9M a month, a year of growing, profitable history, and an
  executive-level product lead on staff (a CEO candidate). Banks can be hired at once.
- `listed <save dir> <name>`: `eligible`, then the IPO chain played through the engine with
  the first choice at every step (Morgan Stanley, filed on time, middle ambition, 15%, one
  class, priced at the suggestion): the company is listed, at the start of a quarter.
- `miss <save dir> <name>`: `listed`, with this quarter's guidance set 25% above the
  consensus, so the report at the quarter's end is a miss.

Usage: uv run --project backend python tools/e2e_m13_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from tst.config import Settings
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
from tst.sim.actions import ChooseEvent, HireBanks, SetGuidance
from tst.sim.hiring.models import PersonState
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.markets_public.public import consensus
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Employment
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    listing_of,
    public_of,
    reach_stage,
    with_company,
    with_employment,
    with_person,
    with_person_state,
    with_product,
    with_product_segment,
)

SEED = 5
FOUNDER = 1
EXTRA_CASH = 50_000_000_00
MRR = 9_000_000_00  # 18,000 mid-market customers at $500 a month
MID_MARKET = 18_000.0
PRICE = 50_000
CEO_ROLE = "product_manager"


def _scaleup(state: GameState, data: LoadedData) -> GameState:
    pid, ids = state.next_ids.take("product")
    product = Product(
        id=pid,
        company_id=1,
        category="b2b_saas",
        name="Pipeline",
        status="live",
        quality=75.0,
        feature_points=400.0,
        brand=60.0,
        marketing_budget_cents=0,
        created_turn=state.turn,
        launched_turn=state.turn,
    )
    state = replace(with_product(state, product), next_ids=ids)
    state = with_product_segment(
        state, ProductSegment(pid, "mid_market", PRICE, MID_MARKET, False, 0)
    )
    history = tuple(round(MRR / 1.035**k) for k in range(12, -1, -1))  # ~50% a year
    company = reach_stage(state.player, 3, state.turn)
    company = replace(
        company, mrr_history=history, op_history=(1_000_000_00,) * 12, root_product_id=pid
    )
    state = with_company(state, company)
    # an executive-level product lead: a CEO candidate (25.6)
    person_id, ids = state.next_ids.take("person")
    eid, ids = ids.take("employment")
    state = replace(state, next_ids=ids)
    gen = RngFactory(SEED).stream(0, "misc", 13)
    person = generate_person(
        gen,
        data.game_data,
        data.balance,
        state.turn,
        data.game_data.role(CEO_ROLE),
        "principal",
        "north_america",
        person_id=person_id,
    )
    state = with_person(state, person)
    state = with_employment(
        state,
        Employment(
            id=eid,
            person_id=person_id,
            company_id=1,
            role=CEO_ROLE,
            level="principal",
            salary_cents=30_000_000,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    return with_person_state(state, PersonState(person_id=person_id, morale=70.0))


def _edit(path: Path, change) -> None:  # type: ignore[no-untyped-def]
    with open_session(path) as session, session.begin():
        before = load_state(session)
        sync_state(session, before, change(before))


def _state(path: Path) -> GameState:
    with open_session(path) as session:
        return load_state(session)


def eligible(save_dir: Path, name: str, data: LoadedData) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name="Kestrel", data=data, save_dir=save_dir
    )
    entry = LedgerEntry.transfer(
        turn=0, company_id=1, memo="E2E funding", debit=CASH, credit=COMMON_EQUITY, amount=EXTRA_CASH
    )
    with open_session(path) as session, session.begin():
        session.add(entry_to_row(entry))
    _edit(path, lambda s: _scaleup(s, data))
    return path


def answer_open(path: Path, data: LoadedData) -> list[str]:
    """Answer every open event with its first choice; returns their template ids."""
    state = _state(path)
    done = []
    for event in state.open_events(state.player.id):
        if event.status == "open" and event.choices:
            run_action(path, data, ChooseEvent(FOUNDER, event.id, event.choices[0].key))
            done.append(event.template_id)
    return done


def play_chain(path: Path, data: LoadedData, max_turns: int = 12) -> GameState:
    """Hire the banks and play turns, answering every event with its first choice, until the
    company is listed; then on to the start of a quarter."""
    run_action(path, data, HireBanks(FOUNDER, "morgan_stanley"))
    for _ in range(max_turns):
        run_turn(path, data)
        answer_open(path, data)
        state = _state(path)
        if public_of(state, 1) is not None:
            break
        listing = listing_of(state, 1)
        assert listing is not None and listing.active, listing
    state = _state(path)
    assert public_of(state, 1) is not None, "the IPO did not list"
    while state.turn % 3:
        run_turn(path, data)
        answer_open(path, data)
        state = _state(path)
    return state


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, save_dir, name = argv[0], Path(argv[1]), argv[2]
    data = load_all(Settings().data_dir)
    if mode == "eligible":
        path = eligible(save_dir, name, data)
    elif mode in ("listed", "miss"):
        path = eligible(save_dir, name, data)
        play_chain(path, data)
        if mode == "miss":
            rev, margin = consensus(_state(path), 1)
            run_action(path, data, SetGuidance(FOUNDER, round(rev * 1.25), margin))
    elif mode == "ripen":
        path = existing_save_path(save_dir, name)
    else:
        print(__doc__)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
