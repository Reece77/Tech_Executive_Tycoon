"""Phase 12 for the founder's own investments (docs/formulas.md 37, M26), after the founder's
life (M24) and before the event director. Order: the month's startup rounds are recorded
from the phase's entries; angel stakes dilute, pay out, list or are written off; concealed
conflicts may come out; sensitive trades go public, investigations open and findings land;
listed rivals' quarterly dividends on the founder's shares; the market index; the family
office's month; net worth at the month end.

A founder who never invests changes nothing but the records: the rounds, the index and the
net-worth history (37.6 target 5)."""

from __future__ import annotations

from dataclasses import replace

from tst.sim.data_models import Balance, GameData
from tst.sim.founder import angel, family_office, shares
from tst.sim.founder.wealth import net_worth
from tst.sim.ledger import LedgerBalances, LedgerEntry, apply_entries
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_angel_stake, with_wealth_point


def investing_month(
    state: GameState,
    entries: tuple[LedgerEntry, ...],
    rng: RngFactory,
    balances: LedgerBalances,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if state.ended:
        return state, (), ()
    logs: list[LogItem] = []
    state, rounds = angel.record_month_rounds(state, entries, balance)
    if state.angel_stakes:
        state, stake_logs = angel.stakes_month(state, rounds, balance, data)
        logs += stake_logs
        state, found = _conflicts_found(state, balance)
        logs += found
    if state.personal_trades:
        state, trade_logs = shares.trades_month(state, rng, balances, balance, data)
        logs += trade_logs
    posted: list[LedgerEntry] = []
    if state.public_holdings:
        state, posted, div_logs = shares.dividends_month(state, balances, balance, data)
        logs += div_logs
    state = family_office.index_month(state, balances, balance, data)
    if state.family_offices:
        state, office_logs = family_office.office_month(state, rng, balance, data)
        logs += office_logs
    founder = state.founder_of(state.player.id)
    if founder is not None:
        after = apply_entries(balances, tuple(posted))
        state = with_wealth_point(state, net_worth(state, founder.id, after, balance, data))
    return state, tuple(posted), tuple(logs)


def _conflicts_found(state: GameState, balance: Balance) -> tuple[GameState, list[LogItem]]:
    """37.2: a concealed conflict of interest comes out in its (hidden) month: credibility
    and every board seat's confidence fall."""
    from tst.sim.press.moments import adjust_credibility
    from tst.sim.state import listed_id, with_seat

    pb = balance.personal
    logs: list[LogItem] = []
    for stake in state.angel_stakes:
        if stake.coi_found_turn != state.turn:
            continue
        cid = state.player.id
        state = adjust_credibility(
            state, cid, pb.coi_cred, "a hidden conflict of interest", balance
        )
        for seat in state.board(listed_id(state)):
            if seat.confidence is not None:
                state = with_seat(
                    state, replace(seat, confidence=max(0.0, seat.confidence + pb.coi_board))
                )
        state = with_angel_stake(state, replace(stake, coi_answer="found"))
        logs.append(
            inbox_item(
                state.turn,
                cid,
                "conflict_found",
                company=state.company(stake.company_id).name,
            )
        )
    return state, logs
