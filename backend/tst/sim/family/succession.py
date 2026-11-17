"""Succession (docs/formulas.md 45.5). By choice, on health grounds, or through the board
(removal with an heir at least "developing" or a professional CEO named). Choosing an heir:
the player now plays the heir, who becomes the founder person (role founder, the founder's
energy, a fresh life: stress family.heir_stress, each trait family.heir_persona_start plus
family.heir_persona_share x the parent's), and the old founder joins the board as adviser.
Choosing a professional CEO: the player stays the family head, acting through the board and
the Automation screen while the CEO runs the company (25.6's CEO, at any stage)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidActionError
from tst.sim.family import dynasty, estate, rules
from tst.sim.family.models import EX_PARTNER, FAMILY_ROLE, Generation
from tst.sim.family.people import family_stream
from tst.sim.finance.board import BOARD_ROLE
from tst.sim.finance.models import BoardSeat
from tst.sim.founder.events import queue
from tst.sim.founder.models import FounderLife
from tst.sim.ledger import LedgerBalances
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public.config import CEO_SCOPES
from tst.sim.markets_public.models import Ceo
from tst.sim.org.ceo_rules import sales_anchors
from tst.sim.people.generator import generate_person
from tst.sim.people.models import FOUNDER_ROLE, Employment
from tst.sim.people.reveal import new_reveal_state
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    ceo_of,
    holding_of,
    life_of,
    with_ceo,
    with_employment,
    with_exec_seat,
    with_family,
    with_family_member,
    with_holding,
    with_life,
    with_person,
    with_person_state,
    with_reveal,
    with_seat,
)

HOWS: Final = ("choice", "health", "board", "death")  # death: M37 (52.4), dynasty years
FOUNDER_LEVEL: Final = "exec"
CEO_KEY: Final = 3  # tunable-exempt: stream key (head_id, 3, 0): a CEO search
CEO_LEVEL: Final = "exec"
TRAIT_MAX: Final = 100.0  # tunable-exempt: traits are 0-100


def can_succeed_on_removal(state: GameState, balance: Balance) -> bool:
    """45.5: removal triggers succession instead of game over with an heir at least
    "developing" or a professional CEO named."""
    if state.family is None:
        return False
    if ceo_of(state, state.player.id) is not None:
        return True
    return bool(rules.eligible_heirs(state, balance, "developing"))


def open_choice(state: GameState, how: str, balance: Balance) -> GameState:
    """The critical choice of successor, next month."""
    family = state.family
    assert family is not None
    if family.succession_open is not None:
        return state
    state = queue(state, state.player.id, "family_succession", state.turn + 1)
    family = state.family
    assert family is not None
    return with_family(state, replace(family, succession_open=how, step_back_open=False))


def on_removal(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """Removal by the board with a successor available (45.5): the directors' votes are
    spent (each voting seat back to board.start, months below 0) and the choice opens."""
    for seat in state.board(state.player.id):
        if seat.votes:
            state = with_seat(
                state,
                replace(
                    seat,
                    months_below=0,
                    confidence=balance.board.start if seat.confidence is not None else None,
                ),
            )
    state = open_choice(state, "board", balance)
    log = inbox_item(state.turn, state.player.id, "board_succession", link_kind="finance")
    return state, [log]


def hand_to_heir(
    state: GameState,
    heir_id: int,
    how: str,
    rng: RngFactory,
    balances: LedgerBalances | None,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    if how not in HOWS:
        raise InvalidActionError(f"unknown succession {how!r}")
    fb = balance.family
    least = "developing" if how == "board" else "not_ready"
    dead = how == "death"  # M37 (52.4): any living family member may have to take over
    members = {m.person_id for m in state.family_members if m.relation != EX_PARTNER}
    if dead and heir_id not in members:
        raise InvalidActionError("the successor at a death must be one of the family")
    if not dead and heir_id not in rules.eligible_heirs(state, balance, least):
        raise InvalidActionError(
            f"an heir must be one of your children, at least {fb.heir_min_age}, in the group"
            + (" and at least developing" if how == "board" else "")
        )
    turn, cid = state.turn, state.player.id
    old = state.person(family.head_id)
    old_life = life_of(state, old.id)
    logs: list[LogItem] = []
    legacy = dynasty.generation_legacy(state, old.id, balance)
    if how in ("health", "death"):  # M37: a death settles the estate at once too (45.6)
        state, more = estate.settle(state, old.id, heir_id, balances, balance, data)
        logs += more
    # Employment: the heir becomes the founder at the player's company; the old founder retires.
    for e in [e for e in state.employments if e.person_id == old.id and e.counts_as_staff]:
        state = with_employment(
            state, replace(e, status="ended", end_turn=turn, end_reason="retired")
        )
    job = state.employment_of(heir_id)
    if job is None:  # M37: a family member outside the group, taking over at a death
        emp_id, ids = state.next_ids.take("employment")
        state = with_employment(
            replace(state, next_ids=ids),
            Employment(
                id=emp_id,
                person_id=heir_id,
                company_id=cid,
                role=FOUNDER_ROLE,
                level=FOUNDER_LEVEL,
                salary_cents=0,
                equity_bp=0,
                start_turn=turn,
                end_turn=None,
                status="active",
            ),
        )
    elif job.company_id == cid:
        state = with_employment(
            state, replace(job, role=FOUNDER_ROLE, level=FOUNDER_LEVEL, unit_id=None)
        )
    else:
        state = with_employment(
            state, replace(job, status="ended", end_turn=turn, end_reason="resigned")
        )
        emp_id, ids = state.next_ids.take("employment")
        state = with_employment(
            replace(state, next_ids=ids),
            Employment(
                id=emp_id,
                person_id=heir_id,
                company_id=cid,
                role=FOUNDER_ROLE,
                level=FOUNDER_LEVEL,
                salary_cents=job.salary_cents,
                equity_bp=0,
                start_turn=turn,
                end_turn=None,
                status="active",
            ),
        )
    for held in state.exec_seats:
        if held.person_id == heir_id:
            state = with_exec_seat(state, replace(held, person_id=None, since_turn=turn))
    ceo = ceo_of(state, cid)
    if ceo is not None and ceo.person_id == heir_id:
        state = with_ceo(state, replace(ceo, ended_turn=turn, end_reason="left"))
    # The people: who the founder is.
    heir = state.person(heir_id)
    old_role = FAMILY_ROLE if dead else BOARD_ROLE  # M37: the dead keep no seat
    state = with_person(state, replace(old, is_founder=False, role=old_role))
    state = with_person(state, replace(heir, is_founder=True, role=None, level=FOUNDER_LEVEL))
    heir = state.person(heir_id)
    old_ps = state.person_state(old.id)
    state = with_person_state(state, replace(old_ps, energy=None))
    cap = (
        balance.ceo.chair_energy
        if ceo_of(state, cid) is not None
        else balance.founder.energy_per_month
    )
    heir_ps = state.person_state(heir_id)
    state = with_person_state(state, replace(heir_ps, energy=max(0, cap - family.family_time)))
    # The heir's life (45.5) and the founder's exact view of themselves.
    state = with_life(state, heir_life(heir_id, old_life, balance))
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=cid,
            person=heir,
            turn=turn,
            rng=rng,
            data=data,
            balance=balance,
            knows_exactly=True,
        ),
    )
    # The board: the heir takes the founder's seat; the old founder joins as adviser.
    adviser_seat = None
    for seat in state.seats:
        if seat.person_id == old.id:
            state = with_seat(state, replace(seat, person_id=heir_id))
    if state.board(cid) and not dead:
        seat_id, ids = state.next_ids.take("seat")
        adviser_seat = BoardSeat(
            id=seat_id, company_id=cid, kind="common", person_id=old.id, seated_turn=turn
        )
        state = with_seat(replace(state, next_ids=ids), adviser_seat)
    holding = holding_of(state)
    if holding is not None and holding.chair_id == old.id:
        state = with_holding(state, replace(holding, chair_id=heir_id))
    # The family's record.
    family = state.family
    assert family is not None
    gens = tuple(
        replace(g, to_turn=turn, legacy=legacy, how=how) if g.to_turn is None else g
        for g in family.generations
    )
    family = replace(
        family,
        head_id=heir_id,
        head_mode="founder",
        generations=(*gens, Generation(person_id=heir_id, from_turn=turn)),
        relationship=0.0,
        partner_since=None,
        married=False,
        marriage_asked=False,
        low_months=0,
        strain_turn=None,
        strain_until=None,
        step_back_delays=0,
        step_back_open=False,
        succession_open=None,
        adviser_id=family.adviser_id if dead else old.id,
        adviser_seat_id=(
            family.adviser_seat_id
            if dead
            else adviser_seat.id
            if adviser_seat is not None
            else None
        ),
        opinions=(),
    )
    family = rules.note(
        family,
        turn,
        "succession",
        f"{rules.full_name(old)} handed over to {rules.full_name(heir)}",
        fb.history,
    )
    state = with_family(state, family)
    for m in state.family_members:
        if m.mentored:
            state = with_family_member(state, replace(m, mentored=False))
    state = rules.check_control(state, balance)
    logs.append(
        inbox_item(
            turn,
            cid,
            "succession_heir",
            link_kind="person",
            link_id=heir_id,
            name=rules.full_name(heir),
            old=rules.full_name(old),
        )
    )
    return state, logs


def heir_life(heir_id: int, parent: FounderLife | None, balance: Balance) -> FounderLife:
    """45.5: stress family.heir_stress; each trait heir_persona_start plus a quarter of the
    parent's."""
    fb = balance.family

    def trait(value: float | None) -> float:
        extra = fb.heir_persona_share * value if value is not None else 0.0
        return min(TRAIT_MAX, fb.heir_persona_start + extra)

    p = parent
    return FounderLife(
        person_id=heir_id,
        stress=fb.heir_stress,
        visionary=trait(p.visionary if p else None),
        ruthless=trait(p.ruthless if p else None),
        beloved=trait(p.beloved if p else None),
        reckless=trait(p.reckless if p else None),
    )


def appoint_professional(
    state: GameState,
    person_id: int | None,
    how: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LogItem]]:
    """45.5: a professional CEO (from inside, or found by a search) runs the company; the
    player leads the family from the board (family-head mode)."""
    family = state.family
    if family is None:
        raise InvalidActionError("there is no family")
    cid = state.player.id
    current = ceo_of(state, cid)
    if current is None:
        if person_id is None:
            person_id = _best_insider(state, balance)
        if person_id is None:
            state, person_id = _search_hire(state, rng, balance, data)
        e = state.employment_of(person_id)
        if e is None or e.company_id != cid or state.person(person_id).is_founder:
            raise InvalidActionError(f"person {person_id} is not on staff")
        ceo_id, ids = state.next_ids.take("ceo")
        state = with_ceo(
            replace(state, next_ids=ids),
            Ceo(
                id=ceo_id,
                company_id=cid,
                person_id=person_id,
                since_turn=state.turn,
                scopes=CEO_SCOPES,
                price_anchors=sales_anchors(state, cid, data),
            ),
        )
        founder = state.person(family.head_id)
        ps = state.person_state(founder.id)
        if ps.energy is not None:
            state = with_person_state(
                state, replace(ps, energy=min(ps.energy, balance.ceo.chair_energy))
            )
    else:
        person_id = current.person_id
    family = state.family
    assert family is not None
    ceo_person = state.person(person_id)
    family = rules.note(
        replace(family, head_mode="family_head", succession_open=None, step_back_open=False),
        state.turn,
        "professional_ceo",
        f"{rules.full_name(ceo_person)} became CEO; you lead the family from the board",
        balance.family.history,
    )
    state = with_family(state, family)
    log = inbox_item(
        state.turn,
        cid,
        "succession_ceo",
        link_kind="person",
        link_id=person_id,
        name=rules.full_name(ceo_person),
        how=how,
    )
    return state, [log]


def _best_insider(state: GameState, balance: Balance) -> int | None:
    """The best senior-or-above employee by displayed CEO-seat fit, outside the family."""
    from tst.sim.org.executives import level_allowed

    family_ids = rules.family_people(state)
    staff = [
        e
        for e in state.staff(state.player.id)
        if e.status == "active"
        and e.person_id not in family_ids
        and not state.person(e.person_id).is_founder
        and level_allowed(e.level, balance)
    ]
    if not staff:
        return None
    return max(
        staff, key=lambda e: (rules.shown_ceo_fit(state, e.person_id, balance), -e.person_id)
    ).person_id


def _search_hire(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, int]:
    """An executive search's hire (13): a generated executive at their asking salary."""
    family = state.family
    assert family is not None
    person_id, ids = state.next_ids.take("person")
    state = replace(state, next_ids=ids)
    gen = family_stream(rng, state.turn, family.head_id, CEO_KEY, 0)
    role = data.role(balance.board.director_role)
    person = generate_person(
        gen, data, balance, state.turn, role, CEO_LEVEL, state.person(family.head_id).region,
        person_id=person_id,
    )  # fmt: skip
    state = with_person(state, person)
    state = with_reveal(
        state,
        new_reveal_state(
            observer_company_id=state.player.id,
            person=person,
            turn=state.turn,
            rng=rng,
            data=data,
            balance=balance,
        ),
    )
    emp_id, ids = state.next_ids.take("employment")
    state = with_employment(
        replace(state, next_ids=ids),
        Employment(
            id=emp_id,
            person_id=person.id,
            company_id=state.player.id,
            role=person.role or role.key,
            level=person.level or CEO_LEVEL,
            salary_cents=person.salary_expectation_cents or 0,
            equity_bp=0,
            start_turn=state.turn,
            end_turn=None,
            status="active",
        ),
    )
    return state, person.id
