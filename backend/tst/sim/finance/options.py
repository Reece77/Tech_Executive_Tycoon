"""Employee options (docs/formulas.md 14.2): grants on hire from the unallocated pool, the
pool limit on offers, monthly vesting, forfeiture on leaving, and the retention factor."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, FinanceBalance
from tst.sim.finance import formulas as f
from tst.sim.finance.captable import fd_shares, pool_entry, share_price, unallocated
from tst.sim.finance.models import OptionGrant
from tst.sim.money import BP_DENOMINATOR
from tst.sim.people.models import Employment
from tst.sim.state import GameState, with_cap_entry, with_grant


def offer_shares(state: GameState, company_id: int, equity_bp: int) -> int:
    """An offer's equity as options at today's FD."""
    return f.shares_for_bp(equity_bp, fd_shares(state, company_id))


def pending_offer_shares(state: GameState, company_id: int, *, excluding: int = 0) -> int:
    """Options promised by pending offers, less `excluding` bp of an offer being replaced."""
    bp = sum(o.equity_bp for o in state.pending_offers(company_id)) - excluding
    return offer_shares(state, company_id, max(bp, 0))


def pool_left_shares(state: GameState, company_id: int) -> int:
    """The unallocated pool less what pending offers promise (14.2, formulas.md 7)."""
    return max(unallocated(state, company_id) - pending_offer_shares(state, company_id), 0)


def pool_left_bp(state: GameState, company_id: int) -> int:
    """pool_left_shares in bp of FD, rounded down: what one more offer may still carry."""
    fd = fd_shares(state, company_id)
    return pool_left_shares(state, company_id) * BP_DENOMINATOR // fd if fd else 0


def grant_on_hire(state: GameState, employment: Employment) -> GameState:
    """round(bp x FD / 10000) options from the unallocated pool, vesting from the hire turn.
    The pool limit on offers means it is always there; it is clamped all the same."""
    if employment.equity_bp <= 0 or state.grant_for(employment.id) is not None:
        return state
    pool = pool_entry(state, employment.company_id)
    if pool is None:
        return state
    shares = min(offer_shares(state, employment.company_id, employment.equity_bp), pool.shares)
    if shares <= 0:
        return state
    grant_id, ids = state.next_ids.take("grant")
    state = replace(state, next_ids=ids)
    state = with_cap_entry(state, replace(pool, shares=pool.shares - shares))
    return with_grant(
        state,
        OptionGrant(
            id=grant_id,
            company_id=employment.company_id,
            person_id=employment.person_id,
            employment_id=employment.id,
            granted=shares,
            start_turn=employment.start_turn,
        ),
    )


def settle_leavers(state: GameState) -> GameState:
    """Grants of people whose employment has ended: unvested options go back to the pool;
    vested ones stay with them (14.2)."""
    ended = {e.id for e in state.employments if not e.counts_as_staff}
    for grant in state.grants:
        if grant.status != "active" or grant.employment_id not in ended:
            continue
        returned = grant.granted - grant.vested
        state = with_grant(state, replace(grant, forfeited=returned, status="ended"))
        pool = pool_entry(state, grant.company_id)
        if pool is not None and returned:
            state = with_cap_entry(state, replace(pool, shares=pool.shares + returned))
    return state


def months_served(grant: OptionGrant, turn: int) -> int:
    """Whole months worked by the end of `turn`, counting the hire month."""
    return turn - grant.start_turn + 1


def vest(state: GameState, balance: Balance) -> GameState:
    """Phase 7: each active grant's vested count for the month just ending (14.2)."""
    for grant in state.grants:
        if grant.status != "active":
            continue
        vested = f.vested_shares(grant.granted, months_served(grant, state.turn), balance.finance)
        if vested != grant.vested:
            state = with_grant(state, replace(grant, vested=vested))
    return state


def next_vesting(grant: OptionGrant, turn: int, fb: FinanceBalance) -> tuple[int, int] | None:
    """The first turn from `turn` whose month end vests more of an active grant, and how
    many options vest then (M4b: the profile and cap table show it); None once fully vested."""
    if grant.status != "active":
        return None
    for t in range(max(turn, grant.start_turn), grant.start_turn + fb.vesting_months):
        vested = f.vested_shares(grant.granted, months_served(grant, t), fb)
        if vested > grant.vested:
            return t, vested - grant.vested
    return None


def at_cliff(grant: OptionGrant, turn: int, fb: FinanceBalance) -> bool:
    """`turn`'s month end is the grant's cliff (the first options vest)."""
    return months_served(grant, turn) == fb.cliff_months


def retention(state: GameState, employment: Employment, balance: Balance) -> float:
    """The resignation multiplier from unvested options (14.2, formulas.md 10)."""
    grant = state.grant_for(employment.id)
    if grant is None:
        return 1.0
    return f.retention_factor(
        grant.unvested,
        share_price(state, employment.company_id),
        employment.salary_cents,
        balance.finance,
    )
