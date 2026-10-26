"""The board (docs/formulas.md 14.6): seats after each priced round and generated directors.

Directors other than the founder are generated people (role `board_member`, not employees)
so later events can name them. Their randomness uses stream `board`, key `(seat_id,)`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData, Series
from tst.sim.finance.models import BoardSeat, SeatKind
from tst.sim.people.generator import generate_person
from tst.sim.people.models import Person
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_person, with_seat

BOARD_ROLE: Final = "board_member"  # not an employee role; not in roles.yaml


def new_director(
    state: GameState, seat_id: int, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, Person]:
    """A generated director with the next person id (stream board, key seat id)."""
    person_id, ids = state.next_ids.take("person")
    gen = rng.stream(state.turn, "board", seat_id)
    person = generate_person(
        gen,
        data,
        balance,
        state.turn,
        data.role(balance.board.director_role),
        balance.board.director_level,
        balance.founder.default_region,
        person_id=person_id,
    )
    person = replace(person, role=BOARD_ROLE, salary_expectation_cents=None, tags=())
    return replace(with_person(state, person), next_ids=ids), person


def _add_seat(
    state: GameState,
    company_id: int,
    kind: SeatKind,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    *,
    round_id: int | None,
    firm: str | None = None,
    person_id: int | None = None,
) -> GameState:
    seat_id, ids = state.next_ids.take("seat")
    state = replace(state, next_ids=ids)
    if person_id is None:
        state, director = new_director(state, seat_id, rng, balance, data)
        person_id = director.id
    seat = BoardSeat(
        id=seat_id,
        company_id=company_id,
        kind=kind,
        person_id=person_id,
        seated_turn=state.turn,
        firm=firm,
        round_id=round_id,
        confidence=None if kind == "common" else balance.board.start,
    )
    return with_seat(state, seat)


def seat_board(
    state: GameState,
    company_id: int,
    series: Series,
    lead_firm: str,
    round_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> GameState:
    """Grow the board to its size after `series` (14.6). The lead takes an investor seat if
    it has none; further investor seats go to firms on the cap table without one."""
    want = balance.board.seats[series]
    seats = state.board(company_id)
    founder = state.founder_of(company_id)
    for _ in range(want.common - sum(1 for s in seats if s.kind == "common")):
        has_founder = any(s.person_id == (founder.id if founder else -1) for s in seats)
        person = founder.id if founder is not None and not has_founder else None
        state = _add_seat(
            state, company_id, "common", rng, balance, data, round_id=round_id, person_id=person
        )
        seats = state.board(company_id)
    holders = [
        e.firm
        for e in sorted(state.company_cap(company_id), key=lambda e: (-e.shares, e.id))
        if e.holder_kind == "firm" and e.firm is not None
    ]
    for _ in range(want.investor - sum(1 for s in seats if s.kind == "investor")):
        seated = {s.firm for s in seats if s.kind == "investor"}
        candidates = [lead_firm, *holders]
        firm = next((f for f in candidates if f not in seated), lead_firm)
        state = _add_seat(
            state, company_id, "investor", rng, balance, data, round_id=round_id, firm=firm
        )
        seats = state.board(company_id)
    for _ in range(want.independent - sum(1 for s in seats if s.kind == "independent")):
        state = _add_seat(state, company_id, "independent", rng, balance, data, round_id=round_id)
        seats = state.board(company_id)
    return state
