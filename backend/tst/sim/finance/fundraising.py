"""Fundraising (docs/formulas.md 14.3-14.5, ADR-0018): investors' base value, SAFE answers,
term sheets, and closing a priced round. Randomness uses stream `finance`, key `(safe_id,)`
for a SAFE and `(round_id, firm_index)` for a firm's answer to a round.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction

import numpy as np

from tst.sim.calendar import MONTHS_PER_YEAR, format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData, Series
from tst.sim.finance import formulas as f
from tst.sim.finance.board import seat_board
from tst.sim.finance.captable import (
    fd_shares,
    last_round,
    mrr_now_and_then,
    person_shares,
    pool_entry,
    unallocated,
)
from tst.sim.finance.models import (
    PREFERRED_CLASS,
    SAFE_HOLDERS,
    SERIES_LABELS,
    CapEntry,
    Safe,
    TermSheet,
)
from tst.sim.ledger import CASH, GENERAL_ADMIN, PREFERRED_EQUITY, SAFES, LedgerEntry
from tst.sim.log import LinkKind, LogItem, inbox_item
from tst.sim.money import BP_DENOMINATOR, Cents
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_cap_entry,
    with_round,
    with_safe,
    with_seat,
    with_term_sheet,
)

FINANCE_LINK: LinkKind = "finance"


def finance_stream(rng: RngFactory, turn: int, *key: int) -> np.random.Generator:
    """Stream `finance` (ADR-0018 section 5): key (safe_id,) for a SAFE's answer, or
    (round_id, firm_index) for a firm's answer to a round. The two key lengths never meet."""
    return rng.stream(turn, "finance", *key)


# --- 14.3 Investors' view of value -----------------------------------------------------------


def company_growth(state: GameState, company_id: int, balance: Balance) -> float:
    now, then = mrr_now_and_then(state, company_id, balance)
    return f.growth_6(now, then, balance.finance)


def arr_cents(state: GameState, company_id: int, balance: Balance) -> Cents:
    now, _ = mrr_now_and_then(state, company_id, balance)
    return now * MONTHS_PER_YEAR


def climate(state: GameState, data: GameData) -> float:
    year, _ = turn_to_ym(state.turn)
    return data.climate.of(year)


def base_value(state: GameState, company_id: int, balance: Balance, data: GameData) -> Cents:
    """V_base from last month end's MRR and its 6-month growth, the funding climate, a live
    product and headcount (14.3). Never shown (14.9)."""
    live = any(p.status == "live" for p in state.company_products(company_id))
    return f.base_value_cents(
        arr_cents(state, company_id, balance),
        company_growth(state, company_id, balance),
        climate(state, data),
        live,
        len(state.staff(company_id)),
        balance.finance,
    )


# --- SAFEs -----------------------------------------------------------------------------------


def outstanding_safes(state: GameState, company_id: int) -> tuple[Safe, ...]:
    return tuple(s for s in state.company_safes(company_id) if s.status == "outstanding")


def safe_fraction(state: GameState, company_id: int) -> Fraction:
    return f.safe_fraction(
        [(s.amount_cents, s.cap_cents) for s in outstanding_safes(state, company_id)]
    )


def safe_entries(
    state: GameState, safe: Safe, balance: Balance, memo: str
) -> tuple[LedgerEntry, ...]:
    """Money in on a SAFE (debit cash, credit 2600_safes) and its legal fee (14.4)."""
    entries = [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=safe.company_id,
            memo=memo,
            debit=CASH,
            credit=SAFES,
            amount=safe.amount_cents,
        )
    ]
    fee = balance.finance.safe.fee_cents
    if fee:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=safe.company_id,
                memo=f"Legal fee: {memo}",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=fee,
            )
        )
    return tuple(entries)


def _pct(fraction: Fraction | float) -> str:
    return f"{float(fraction) * 100:.1f}%"


def answer_safes(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7: angels and seed funds answer each pending SAFE once, all or nothing (14.4)."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for safe in state.safes:
        if safe.status != "pending" or safe.raised_turn > state.turn:
            continue
        base = base_value(state, safe.company_id, balance, data)
        p = f.safe_probability(base, safe.cap_cents, balance.finance.safe)
        filled = float(finance_stream(rng, state.turn, safe.id).random()) < p
        safe = replace(
            safe, status="outstanding" if filled else "declined", resolved_turn=state.turn
        )
        state = with_safe(state, safe)
        params = {"amount_cents": safe.amount_cents, "cap_cents": safe.cap_cents}
        if filled:
            entries += safe_entries(state, safe, balance, "SAFE")
            pct = _pct(Fraction(safe.amount_cents, safe.cap_cents))
            logs.append(
                inbox_item(
                    state.turn,
                    safe.company_id,
                    "safe_filled",
                    link_kind=FINANCE_LINK,
                    pct=pct,
                    **params,
                )
            )
        else:
            logs.append(
                inbox_item(
                    state.turn, safe.company_id, "safe_declined", link_kind=FINANCE_LINK, **params
                )
            )
    return state, tuple(entries), tuple(logs)


# --- Rounds ----------------------------------------------------------------------------------


def next_series(state: GameState, company_id: int) -> Series | None:
    """The series that follows the last priced round: seed, a, b; None after Series B."""
    latest = last_round(state, company_id)
    if latest is None:
        return "seed"
    return {"seed": "a", "a": "b"}.get(latest.series)  # type: ignore[return-value]


def series_problem(state: GameState, company_id: int, series: str, balance: Balance) -> str | None:
    """Why a series cannot be raised now (14.5 gates), or None."""
    expected = next_series(state, company_id)
    if expected is None:
        return "there is no round after Series B until v2"
    if series != expected:
        return f"the next round is the {SERIES_LABELS[expected]}"
    gate = balance.finance.round.gate_arr_cents.get(expected)
    if gate is not None and arr_cents(state, company_id, balance) < gate:
        return f"the {SERIES_LABELS[expected]} needs ARR of at least ${gate // 100:,}"
    return None


def deliver_term_sheets(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 7 of the turn a round opens: each firm that invests in the series answers with
    probability response x climate, quoting V_pre and an amount (14.5)."""
    rb = balance.finance.round
    logs: list[LogItem] = []
    for rnd in state.rounds:
        if rnd.status != "open" or rnd.opened_turn != state.turn or state.sheets_of(rnd.id):
            continue
        base = base_value(state, rnd.company_id, balance, data)
        mood = climate(state, data)
        count = 0
        for index, firm in enumerate(data.investors):
            if rnd.series not in firm.series:
                continue
            gen = finance_stream(rng, state.turn, rnd.id, index)
            answers = float(gen.random()) < f.response_chance(firm.response, mood, rb.max_response)
            z = float(gen.standard_normal())
            if not answers:
                continue
            pre = f.quoted_pre_money_cents(base, firm.bias, z, rb.valuation_noise_sd)
            amount = f.offered_amount_cents(
                rnd.target_cents,
                firm.check_min_cents,
                firm.check_max_cents,
                pre,
                rb.max_amount_of_pre,
            )
            sheet_id, ids = state.next_ids.take("term_sheet")
            state = replace(state, next_ids=ids)
            state = with_term_sheet(
                state,
                TermSheet(
                    id=sheet_id,
                    round_id=rnd.id,
                    firm=firm.key,
                    pre_money_cents=pre,
                    amount_cents=amount,
                    status="offered",
                    offered_turn=state.turn,
                    expires_turn=rnd.expires_turn,
                ),
            )
            count += 1
        label = SERIES_LABELS[rnd.series]
        if count == 0:
            state = with_round(state, replace(rnd, status="failed"))
            logs.append(
                inbox_item(
                    state.turn,
                    rnd.company_id,
                    "no_term_sheets",
                    link_kind=FINANCE_LINK,
                    series=label,
                )
            )
        else:
            logs.append(
                inbox_item(
                    state.turn,
                    rnd.company_id,
                    "term_sheets_arrived",
                    link_kind=FINANCE_LINK,
                    link_id=rnd.id,
                    count=count,
                    series=label,
                    target_cents=rnd.target_cents,
                    deadline=format_turn(rnd.expires_turn),
                )
            )
    return state, tuple(logs)


def lapse_rounds(state: GameState) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 7: an open round with no accepted term sheet by its last turn lapses (14.5)."""
    logs: list[LogItem] = []
    for rnd in state.rounds:
        if rnd.status != "open" or rnd.expires_turn > state.turn or rnd.opened_turn == state.turn:
            continue
        state = with_round(state, replace(rnd, status="lapsed"))
        for sheet in state.sheets_of(rnd.id):
            if sheet.status == "offered":
                state = with_term_sheet(state, replace(sheet, status="lapsed"))
        logs.append(
            inbox_item(
                state.turn,
                rnd.company_id,
                "round_lapsed",
                link_kind=FINANCE_LINK,
                series=SERIES_LABELS[rnd.series],
            )
        )
    return state, tuple(logs)


@dataclass(frozen=True, slots=True)
class RoundPlan:
    """What closing at these terms would do (the round preview and the close itself)."""

    closing: f.Closing
    fd_before: int
    unallocated_before: int
    safe_fraction: Fraction
    converting: tuple[Safe, ...]


def plan_close(
    state: GameState, company_id: int, pre_money_cents: Cents, amount_cents: Cents, balance: Balance
) -> RoundPlan:
    target = Fraction(balance.finance.pool_target_bp, BP_DENOMINATOR)
    frac = safe_fraction(state, company_id)
    fd = fd_shares(state, company_id)
    pool = unallocated(state, company_id)
    closing = f.close_round(fd, frac, pool, pre_money_cents, amount_cents, target)
    return RoundPlan(closing, fd, pool, frac, outstanding_safes(state, company_id))


def _add_entry(state: GameState, **fields: object) -> GameState:
    entry_id, ids = state.next_ids.take("cap_entry")
    entry = CapEntry(id=entry_id, acquired_turn=state.turn, **fields)  # type: ignore[arg-type]
    return with_cap_entry(replace(state, next_ids=ids), entry)


def close_rounds(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 1: an accepted round closes with the 14.5 closing function: the pool top-up,
    SAFE conversion, new preferred shares, the money, fees and the board seat."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for rnd in state.rounds:
        if rnd.status != "accepted" or rnd.accepted_sheet_id is None:
            continue
        sheet = state.term_sheet(rnd.accepted_sheet_id)
        assert sheet is not None
        company = rnd.company_id
        previous = last_round(state, company)
        plan = plan_close(state, company, sheet.pre_money_cents, sheet.amount_cents, balance)
        c = plan.closing
        pool = pool_entry(state, company)
        if pool is not None and c.pool_shares:
            state = with_cap_entry(state, replace(pool, shares=pool.shares + c.pool_shares))
        if c.safe_shares:
            state = _add_entry(
                state,
                company_id=company,
                holder_kind="group",
                share_class="safe_conversion",
                shares=c.safe_shares,
                name=SAFE_HOLDERS,
                round_id=rnd.id,
            )
        state = _add_entry(
            state,
            company_id=company,
            holder_kind="firm",
            share_class=PREFERRED_CLASS[rnd.series],
            shares=c.new_shares,
            firm=sheet.firm,
            round_id=rnd.id,
        )
        converted = sum(s.amount_cents for s in plan.converting)
        for safe in plan.converting:
            state = with_safe(state, replace(safe, status="converted", converted_round_id=rnd.id))
        previous_price = previous.price if previous is not None else None
        down = previous_price is not None and c.price < previous_price
        state = with_round(
            state,
            replace(
                rnd,
                status="closed",
                closed_turn=state.turn,
                lead_firm=sheet.firm,
                pre_money_cents=sheet.pre_money_cents,
                amount_cents=sheet.amount_cents,
                fd_before=plan.fd_before,
                pool_shares=c.pool_shares,
                safe_shares=c.safe_shares,
                new_shares=c.new_shares,
                fd_pre=c.fd_pre,
                down_round=down,
            ),
        )
        label = SERIES_LABELS[rnd.series]
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company,
                memo=f"{label}: {data.firm(sheet.firm).name}",
                debit=CASH,
                credit=PREFERRED_EQUITY,
                amount=sheet.amount_cents,
            )
        )
        if converted:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=company,
                    memo=f"SAFEs convert at the {label}",
                    debit=SAFES,
                    credit=PREFERRED_EQUITY,
                    amount=converted,
                )
            )
        rb = balance.finance.round
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=company,
                memo=f"Legal fees: {label}",
                debit=GENERAL_ADMIN,
                credit=CASH,
                amount=f.round_fee_cents(sheet.amount_cents, rb.fee_min_cents, rb.fee_bp),
            )
        )
        if down:  # every sitting director, once (14.6)
            for seat in state.board(company):
                if seat.confidence is not None:
                    hit = f.clamp_confidence(seat.confidence + balance.board.down_round_hit)
                    state = with_seat(state, replace(seat, confidence=hit))
        state = seat_board(state, company, rnd.series, sheet.firm, rnd.id, rng, balance, data)
        founder = state.founder_of(company)
        founder_pct = (
            _pct(Fraction(person_shares(state, company, founder.id), fd_shares(state, company)))
            if founder is not None
            else "0%"
        )
        logs.append(
            inbox_item(
                state.turn,
                company,
                "round_closed",
                link_kind=FINANCE_LINK,
                link_id=rnd.id,
                series=label,
                lead=data.firm(sheet.firm).name,
                amount_cents=sheet.amount_cents,
                pre_cents=sheet.pre_money_cents,
                price=f"${float(c.price) / 100:.4f}",
                founder_pct=founder_pct,
            )
        )
    return state, tuple(entries), tuple(logs)
