"""Moving wealth between people (docs/formulas.md 45.2, 45.5, 45.6): shares on a cap table
(ADR-0018) and balances between two personal books (32.2), each move a pair of balanced
entries, so every book balances and an account's total across the two books is unchanged."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.finance.captable import person_shares
from tst.sim.finance.models import CapEntry, HolderKind
from tst.sim.founder.models import PERSONAL_INCOME, PERSONAL_SPENDING
from tst.sim.founder.wealth import post
from tst.sim.state import GameState, with_cap_entry


def take_person_shares(state: GameState, company_id: int, person_id: int, shares: int) -> GameState:
    """Remove `shares` from a person's entries, oldest first."""
    left = shares
    mine = [
        e
        for e in state.company_cap(company_id)
        if e.holder_kind == "person" and e.person_id == person_id
    ]
    for entry in sorted(mine, key=lambda e: e.id):
        take = min(left, entry.shares)
        if take:
            state = with_cap_entry(state, replace(entry, shares=entry.shares - take))
        left -= take
        if not left:
            break
    if left:
        raise ValueError(f"person {person_id} holds fewer than {shares} shares")
    return state


def give_shares(
    state: GameState,
    company_id: int,
    shares: int,
    *,
    person_id: int | None = None,
    group: str | None = None,
) -> GameState:
    """Add `shares` of common to a person's entry or a named group's, creating one."""
    if shares <= 0:
        return state
    kind: HolderKind = "person" if person_id is not None else "group"
    for e in sorted(state.company_cap(company_id), key=lambda e: e.id):
        if e.holder_kind != kind or e.share_class != "common":
            continue
        if (kind == "person" and e.person_id == person_id) or (kind == "group" and e.name == group):
            return with_cap_entry(state, replace(e, shares=e.shares + shares))
    entry_id, ids = state.next_ids.take("cap_entry")
    entry = CapEntry(
        id=entry_id,
        company_id=company_id,
        holder_kind=kind,
        share_class="common",
        shares=shares,
        acquired_turn=state.turn,
        person_id=person_id,
        name=group,
    )
    return with_cap_entry(replace(state, next_ids=ids), entry)


def move_person_shares(
    state: GameState,
    company_id: int,
    from_id: int,
    shares: int,
    *,
    to_person: int | None = None,
    to_group: str | None = None,
) -> GameState:
    if shares <= 0:
        return state
    if shares > person_shares(state, company_id, from_id):
        raise ValueError("not enough shares to move")
    state = take_person_shares(state, company_id, from_id, shares)
    return give_shares(state, company_id, shares, person_id=to_person, group=to_group)


def move_book(
    state: GameState,
    from_id: int,
    to_id: int,
    account: str,
    cents: int,
    memo: str,
    source: str,
) -> GameState:
    """`cents` of `account` leave one book (Dr 9300, Cr account) and arrive in another
    (Dr account, Cr 9400)."""
    if cents <= 0:
        return state
    state = post(state, from_id, memo, source, PERSONAL_SPENDING, account, cents)
    return post(state, to_id, memo, source, account, PERSONAL_INCOME, cents)
