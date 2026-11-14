"""Divorce (docs/formulas.md 45.2): below family.divorce_below for family.divorce_months the
partner leaves with half the personal cash and investments and family.divorce_share of the
head's shares in each company, which become an independent holder (ADR-0018). Persona
Beloved falls; History records it."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from tst.sim.data_models import Balance
from tst.sim.family import rules
from tst.sim.family.models import EX_PARTNER, FamilyMember
from tst.sim.family.transfers import move_book, move_person_shares
from tst.sim.finance.captable import person_shares
from tst.sim.founder import persona
from tst.sim.founder.investing_models import PublicHolding
from tst.sim.founder.models import ANGEL, FAMILY_OFFICE, PERSONAL_CASH, PUBLIC_SHARES
from tst.sim.founder.personal import book_balances
from tst.sim.log import LogItem, inbox_item
from tst.sim.state import (
    GameState,
    life_of,
    with_angel_stake,
    with_family,
    with_family_member,
    with_life,
    with_public_holding,
)

SOURCE = "settlement"


def split(cents: int, share: float) -> int:
    return int(Fraction(cents) * Fraction(share).limit_denominator(10_000))  # tunable-exempt


def divorce(
    state: GameState, partner: FamilyMember, balance: Balance
) -> tuple[GameState, list[LogItem]]:
    family = state.family
    assert family is not None
    fb = balance.family
    head_id = family.head_id
    pid = partner.person_id
    share = fb.divorce_share
    memo = "Divorce settlement"
    books = book_balances(state.personal_book, head_id)
    # Personal cash and the family office: half of each balance moves.
    for account in (PERSONAL_CASH, FAMILY_OFFICE):
        state = move_book(
            state, head_id, pid, account, split(books.get(account, 0), share), memo, SOURCE
        )
    # Public holdings and angel stakes: half of each record, at book cost.
    moved_public = 0
    for h in [h for h in state.public_holdings if h.person_id == head_id and h.shares > 0]:
        shares = split(h.shares, share)
        cost = split(h.cost_cents, share)
        if not shares:
            continue
        state = with_public_holding(
            state, replace(h, shares=h.shares - shares, cost_cents=h.cost_cents - cost)
        )
        state = with_public_holding(state, PublicHolding(pid, h.company_id, shares, cost))
        moved_public += cost
    state = move_book(state, head_id, pid, PUBLIC_SHARES, moved_public, memo, SOURCE)
    moved_angel = 0
    next_id = max((s.id for s in state.angel_stakes), default=0) + 1
    for s in [s for s in state.angel_stakes if s.person_id == head_id and s.status == "open"]:
        ppm = split(s.stake_ppm, share)
        cost = split(s.cost_cents, share)
        if not ppm:
            continue
        state = with_angel_stake(
            state, replace(s, stake_ppm=s.stake_ppm - ppm, cost_cents=s.cost_cents - cost)
        )
        state = with_angel_stake(
            state, replace(s, id=next_id, person_id=pid, stake_ppm=ppm, cost_cents=cost)
        )
        next_id += 1
        moved_angel += cost
    state = move_book(state, head_id, pid, ANGEL, moved_angel, memo, SOURCE)
    # Shares in every company: the partner becomes an independent holder.
    for company in state.companies:
        held = person_shares(state, company.id, head_id)
        if held > 0:
            state = move_person_shares(
                state, company.id, head_id, split(held, share), to_person=pid
            )
    state = with_family_member(state, replace(partner, relation=EX_PARTNER, left_turn=state.turn))
    family = state.family
    assert family is not None
    family = replace(
        family,
        relationship=0.0,
        low_months=0,
        married=False,
        marriage_asked=False,
        partner_since=None,
        strain_until=None,
    )
    name = rules.full_name(state.person(pid))
    family = rules.note(family, state.turn, "divorce", f"Divorced {name}", fb.history)
    state = with_family(state, family)
    life = life_of(state, head_id)
    if life is not None:
        life = persona.raise_trait(
            life, "beloved", -fb.divorce_beloved, "a divorce", state.turn, balance
        )
        state = with_life(state, life)
    state = rules.check_control(state, balance)
    log = inbox_item(
        state.turn, state.player.id, "family_divorce", link_kind="person", link_id=pid, name=name
    )
    return state, [log]
