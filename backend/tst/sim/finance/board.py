"""The board (docs/formulas.md 14.6): seats after each priced round and generated directors.

Directors other than the founder are generated people (role `board_member`, not employees)
so later events can name them. Their randomness uses stream `board`, key `(seat_id,)`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import LEVELS, SCORE_MAX, Balance, BoardBalance, GameData, Series
from tst.sim.finance import formulas as f
from tst.sim.finance.captable import last_round, mrr_now_and_then
from tst.sim.finance.models import BoardSeat, SeatKind
from tst.sim.finance.statements import projected_runway
from tst.sim.log import LogItem, inbox_item
from tst.sim.org.executives import cfo_confidence
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
    if len(state.board(company_id)) >= balance.board.max_seats:
        return state  # M10 (20.2): a full board takes no more seats
    seat_id, ids = state.next_ids.take("seat")
    state = replace(state, next_ids=ids)
    if person_id is None and kind != "common":  # a common seat may stay empty (M4c)
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


def adds_common_seat(state: GameState, company_id: int, series: Series, balance: Balance) -> bool:
    """Whether closing `series` adds a common seat beyond the founder's: the founder's
    nominee (14.6, M4c)."""
    have = sum(1 for s in state.board(company_id) if s.kind == "common")
    return balance.board.seats[series].common > max(have, 1)


def nominee_problem(state: GameState, company_id: int, person_id: int) -> str | None:
    """Why someone cannot be the founder's board nominee, or None (14.6, M4c)."""
    employment = state.employment_of(person_id)
    if employment is None or employment.company_id != company_id or not employment.counts_as_staff:
        return f"person {person_id} is not on staff"
    if state.person(person_id).is_founder:
        return "the founder already holds a seat"
    if any(s.person_id == person_id for s in state.board(company_id)):
        return f"person {person_id} is already on the board"
    return None


def default_nominee(state: GameState, company_id: int) -> int | None:
    """The most senior employee: highest level, then longest tenure, then lowest id."""
    staff = [
        e
        for e in state.staff(company_id)
        if nominee_problem(state, company_id, e.person_id) is None
    ]
    if not staff:
        return None
    best = min(staff, key=lambda e: (-LEVELS.index(e.level), e.start_turn, e.person_id))
    return best.person_id


def seat_board(
    state: GameState,
    company_id: int,
    series: Series,
    lead_firm: str,
    round_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    nominee_id: int | None = None,
    founder_id: int | None = None,
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Grow the board to its size after `series` (14.6). The lead takes an investor seat if
    it has none; further investor seats go to firms on the cap table without one. A second
    common seat goes to the founder's nominee if they are still on staff, else it is empty
    and the inbox asks the founder to name one (M4c)."""
    want = balance.board.seats[series]
    seats = state.board(company_id)
    if founder_id is None:  # given at game start, before the founder is in the state
        founder = state.founder_of(company_id)
        founder_id = founder.id if founder is not None else None
    logs: list[LogItem] = []
    for _ in range(want.common - sum(1 for s in seats if s.kind == "common")):
        has_founder = any(s.person_id == founder_id for s in seats)
        person = founder_id if founder_id is not None and not has_founder else None
        nominee_ok = (
            nominee_id is not None and nominee_problem(state, company_id, nominee_id) is None
        )
        if person is None and nominee_ok:
            person = nominee_id
        state = _add_seat(
            state, company_id, "common", rng, balance, data, round_id=round_id, person_id=person
        )
        seats = state.board(company_id)
        if person is None:
            logs.append(inbox_item(state.turn, company_id, "board_seat_empty", link_kind="finance"))
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
    return state, tuple(logs)


def vacate_departed(state: GameState) -> tuple[GameState, tuple[LogItem, ...]]:
    """A nominee who leaves the company leaves their common seat empty (14.6, M4c)."""
    staff = {e.person_id for e in state.employments if e.counts_as_staff}
    logs: list[LogItem] = []
    for seat in state.seats:
        if seat.kind != "common" or seat.person_id is None or seat.person_id in staff:
            continue
        person = state.person(seat.person_id)
        if person.is_founder:
            continue
        state = with_seat(state, replace(seat, person_id=None))
        logs.append(
            inbox_item(
                state.turn,
                seat.company_id,
                "nominee_left",
                link_kind="finance",
                name=f"{person.first_name} {person.last_name}",
            )
        )
    return state, tuple(logs)


# --- Monthly confidence (phase 10) -----------------------------------------------------------


def growth_term(state: GameState, company_id: int, balance: Balance) -> float:
    """growth_weight x clamp(g6 / g_exp - 1, -1, 1); 0 while there are fewer than 6 months
    of revenue, or the no-product penalty once a year has passed since the last round with
    nothing live (14.6)."""
    bb = balance.board
    latest = last_round(state, company_id)
    if latest is None:
        return 0.0
    now, then = mrr_now_and_then(state, company_id, balance)
    if then <= 0:
        live = any(p.status == "live" for p in state.company_products(company_id))
        waited = state.turn - (latest.closed_turn or 0) >= bb.no_product_after_turns
        return bb.no_product_penalty if waited and not live else 0.0
    g6 = f.growth_6(now, then, balance.finance)
    return f.growth_points(g6, bb.expected_growth[latest.series], bb)


def actual_growth(state: GameState, company_id: int, balance: Balance) -> float | None:
    """The annualized 6-month MRR growth the board compares with its expectation; None while
    there are fewer than 6 months of revenue (14.6)."""
    now, then = mrr_now_and_then(state, company_id, balance)
    return f.growth_6(now, then, balance.finance) if then > 0 else None


def next_meeting_turn(turn: int, bb: BoardBalance) -> int:
    """The first turn from `turn` whose month end has a quarterly board meeting."""
    t = turn
    while turn_to_ym(t)[1] not in bb.meeting_months:
        t += 1
    return t


def average_confidence(state: GameState, company_id: int) -> float | None:
    """The board's mood: the mean of the voting directors' confidence (common seats hold none)."""
    values = [s.confidence for s in state.board(company_id) if s.confidence is not None]
    return sum(values) / len(values) if values else None


def board_month(
    state: GameState, cash_cents: dict[int, int], balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 10: every director's confidence moves toward its target; quarter ends bring a
    meeting summary (and a warning below 40); a majority voting to remove ends the game."""
    bb = balance.board
    logs: list[LogItem] = []
    for company in state.ledger_companies():
        seats = state.board(company.id)
        if not any(s.votes for s in seats):
            continue
        runway = projected_runway(state, company.id, cash_cents.get(company.id, 0), balance, data)
        growth = growth_term(state, company.id, balance)
        runway_pts = f.runway_points(runway, bb)
        cfo = cfo_confidence(state, company.id, balance)  # M8 (18.3): 0 before stage 3
        for seat in seats:
            if seat.confidence is None:
                continue
            patience = data.firm(seat.firm).patience if seat.firm else 0.0
            target = f.confidence_target(growth, runway_pts, patience, bb)
            b = f.next_confidence(seat.confidence, target, bb)
            if cfo:
                b = min(SCORE_MAX, max(0.0, b + cfo))
            below = seat.months_below + 1 if b < bb.removal_below else 0
            history = (*seat.history, b)[-bb.history_months :]
            state = with_seat(
                state, replace(seat, confidence=b, months_below=below, history=history)
            )
        avg = average_confidence(state, company.id)
        _, month = turn_to_ym(state.turn)
        if avg is not None and month in bb.meeting_months:
            confidence = f"{avg:.0f}"
            logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    "board_meeting",
                    link_kind="finance",
                    confidence=confidence,
                    label=f.confidence_label(avg, bb),
                )
            )
            if avg < bb.warning_below:
                logs.append(
                    inbox_item(
                        state.turn,
                        company.id,
                        "board_warning",
                        link_kind="finance",
                        confidence=confidence,
                        removal=f"{bb.removal_below:.0f}",
                        months=bb.removal_months,
                    )
                )
        seats = state.board(company.id)
        votes = sum(1 for s in seats if s.votes and s.months_below >= bb.removal_months)
        if 2 * votes > len(seats):  # a majority of all seats; a tie keeps the founder
            state = replace(
                state,
                save_meta=replace(
                    state.save_meta, game_state="founder_removed", ended_turn=state.turn
                ),
            )
            logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    "founder_removed",
                    link_kind="finance",
                    votes=votes,
                    seats=len(seats),
                )
            )
    return state, tuple(logs)
