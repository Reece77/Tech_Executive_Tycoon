"""Debt and macro responses (M10, docs/formulas.md 20.4). Only months already reached are
shown: history up to the month the player is in, then the months phase 1 has set."""

from __future__ import annotations

from collections.abc import Mapping

from tst.api.schemas.capital import (
    CovenantOut,
    LoanOut,
    LoanPreviewOut,
    LoansOut,
    LoanTermsOut,
    MacroIndicatorOut,
    MacroMonthOut,
    MacroOut,
    PaymentOut,
)
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.data_models import INSTRUMENTS, Instrument
from tst.sim.finance import debt, macro
from tst.sim.finance.captable import fd_shares
from tst.sim.finance.models import Loan
from tst.sim.money import Cents, format_money
from tst.sim.state import GameState

STATUS_LABELS = {"active": "Active", "repaid": "Repaid", "called": "Called by the lender"}


def _month(m: macro.MacroMonth) -> MacroMonthOut:
    return MacroMonthOut(
        turn=m.turn,
        label=format_turn(m.turn),
        base_rate=round(m.base_rate, 4),
        climate=round(m.climate, 4),
        confidence=round(m.confidence, 2),
        ai_index=round(m.ai_index, 4),
    )


def macro_months(
    state: GameState, stored: Mapping[int, macro.MacroMonth], data: LoadedData
) -> list[macro.MacroMonth]:
    """The last `history_months` months and the current one, oldest first; never a later
    month (20.4). A month with no stored row (a save from before M10) is history."""
    gd = data.game_data
    current = macro.now(state, gd)
    out = []
    for turn in range(max(0, current.turn - data.balance.macro.history_months), current.turn):
        m = stored.get(turn) or macro.history_month(turn, gd)
        if m is not None:
            out.append(m)
    return [*out, current]


def macro_out(
    state: GameState, stored: Mapping[int, macro.MacroMonth], data: LoadedData
) -> MacroOut:
    gd, mb = data.game_data, data.balance.macro
    months = macro_months(state, stored, data)
    cur = months[-1]
    year_ago = next((m for m in months if m.turn == cur.turn - 12), None)
    factor = macro.confidence_factor(cur.confidence, mb.confidence_exponent)
    downturn = cur.in_downturn(mb.downturn.months)

    def change(now: float, then: float | None, unit: str, scale: float = 1.0) -> str:
        if then is None:
            return "no year-ago figure"
        diff = (now - then) * scale
        return f"{diff:+.2f}{unit} on a year ago"

    rate_then = year_ago.base_rate if year_ago is not None else None
    segments = " and ".join(gd.segment(s).label for s in mb.confidence_segments)
    indicators = [
        MacroIndicatorOut(
            key="base_rate",
            label="Base rate",
            value=cur.base_rate,
            display=f"{cur.base_rate:.2f}%",
            context=f"Loans price off it; {change(cur.base_rate, rate_then, ' points')}",
        ),
        MacroIndicatorOut(
            key="climate",
            label="Venture climate",
            value=cur.climate,
            display=f"x {cur.climate:.2f}",
            context="Multiplies the ARR multiple investors pay and how many answer a round",
        ),
        MacroIndicatorOut(
            key="confidence",
            label="Consumer confidence",
            value=cur.confidence,
            display=f"{cur.confidence:.0f}",
            context=f"Adoption x {factor:.2f} in {segments}",
        ),
        MacroIndicatorOut(
            key="ai_index",
            label="AI compute cost",
            value=cur.ai_index,
            display=f"x {cur.ai_index:.2f} of 2010",
            context="AI hosting costs follow it",
        ),
    ]
    last = macro.last_history_turn(gd)
    return MacroOut(
        current=_month(cur),
        indicators=indicators,
        months=[_month(m) for m in months],
        adoption_factor=round(factor, 4),
        downturn=downturn,
        history_ends_label=format_turn(last),
        after_history=state.turn > last,
    )


# --- Loans -------------------------------------------------------------------------------------


def _payment(p: debt.Payment) -> PaymentOut:
    return PaymentOut(
        turn=p.turn,
        label=format_turn(p.turn),
        interest_cents=p.interest_cents,
        principal_cents=p.principal_cents,
        balance_after_cents=p.balance_after_cents,
    )


def loan_out(state: GameState, loan: Loan, cash: Cents, data: LoadedData) -> LoanOut:
    b = data.balance
    plan = debt.schedule(loan, state.turn) if loan.active else ()
    tested = debt.tested(loan, state.turn, b)
    resting = (
        None
        if tested or loan.breach_turn is None
        else format_turn(loan.breach_turn + b.debt.breach.cure_months + 1)
    )
    return LoanOut(
        id=loan.id,
        instrument=loan.instrument,
        instrument_label=debt.INSTRUMENT_LABELS[loan.instrument],
        lender=debt.lender_name(loan, data.game_data),
        principal_cents=loan.principal_cents,
        signed_turn=loan.signed_turn,
        signed_label=format_turn(loan.signed_turn),
        warrant_shares=loan.warrant_shares,
        balance_cents=loan.balance_cents,
        rate_bp=loan.rate_bp,
        status=loan.status,
        status_label=STATUS_LABELS[loan.status],
        term_months=loan.term_months,
        interest_only_months=loan.interest_only_months,
        ends_label=format_turn(loan.last_turn),
        interest_paid_cents=loan.interest_paid_cents,
        principal_paid_cents=loan.principal_paid_cents,
        next_payment=_payment(plan[0]) if plan else None,
        covenants=[
            CovenantOut(
                description=c.description,
                measure_cents=c.measure_cents,
                required_cents=c.required_cents,
                headroom_cents=c.headroom_cents,
                holds=c.holds,
            )
            for c in (debt.covenants(state, loan, cash, b) if loan.active else [])
        ],
        covenants_resting_until_label=resting,
        breaches=loan.breaches,
        schedule=[_payment(p) for p in plan],
    )


def _covenant_words(instrument: Instrument, data: LoadedData) -> str:
    d = data.balance.debt
    if instrument == "venture_debt":
        return f"Cash at least {d.venture.covenant_burn_months:g} months of last month's burn"
    return (
        f"An operating profit over the last {d.bank.covenant_profit_months} months, and cash "
        f"at least {d.bank.covenant_cash_bp / 100:g}% of the balance"
    )


def _breach_words(data: LoadedData) -> str:
    br = data.balance.debt.breach
    return (
        f"A breach brings the lender's terms: a {br.waiver_fee_bp / 100:g}% waiver fee, a rate "
        f"{br.rate_up_bp / 100:g} points higher, or repaying {br.repay_bp / 100:g}% at once. A "
        f"second breach within {br.call_window_months} months makes the whole balance due."
    )


def terms_out(state: GameState, instrument: Instrument, data: LoadedData) -> LoanTermsOut:
    t = debt.terms(state, state.player.id, instrument, data.balance, data.game_data)
    return LoanTermsOut(
        instrument=instrument,
        instrument_label=debt.INSTRUMENT_LABELS[instrument],
        eligible=t.problem is None,
        problem=t.problem,
        lender=t.lender.name if t.lender else None,
        rate_bp=t.rate_bp,
        term_months=t.term_months,
        interest_only_months=t.interest_only_months,
        max_cents=t.max_cents,
        min_cents=data.balance.debt.min_cents,
        warrant_bp=t.warrant_bp,
        covenant=_covenant_words(instrument, data),
        breach=_breach_words(data),
        energy=data.balance.debt.take_energy,
    )


def loans_out(state: GameState, cash: Cents, data: LoadedData) -> LoansOut:
    loans = sorted(state.company_loans(state.player.id), key=lambda x: (not x.active, -x.id))
    return LoansOut(
        loans=[loan_out(state, x, cash, data) for x in loans],
        offers=[terms_out(state, i, data) for i in INSTRUMENTS],
        debt_cents=sum(x.balance_cents for x in loans if x.active),
        repay_energy=data.balance.debt.repay_energy,
    )


def loan_preview_out(
    state: GameState, instrument: str, amount_cents: Cents, data: LoadedData
) -> LoanPreviewOut:
    """The first month's payment and the warrants if the loan were signed now. Nothing is
    saved."""
    if instrument not in INSTRUMENTS:
        return LoanPreviewOut(
            problem=f"unknown instrument {instrument!r}", first_payment=None, rate_bp=0,
            warrant_shares=0,
        )  # fmt: skip
    kind: Instrument = instrument
    company = state.player.id
    b, gd = data.balance, data.game_data
    t = debt.terms(state, company, kind, b, gd)
    problem = debt.amount_problem(state, company, kind, amount_cents, b, gd)
    loan = Loan(
        id=0,
        company_id=company,
        instrument=kind,
        lender="",
        principal_cents=amount_cents,
        balance_cents=amount_cents,
        rate_bp=t.rate_bp,
        signed_turn=state.turn,
        term_months=t.term_months,
        interest_only_months=t.interest_only_months,
    )
    plan = debt.schedule(loan, state.turn) if amount_cents > 0 else ()
    return LoanPreviewOut(
        problem=problem,
        first_payment=_payment(plan[0]) if plan else None,
        rate_bp=t.rate_bp,
        warrant_shares=debt.warrant_shares(fd_shares(state, company), t.warrant_bp),
    )


__all__ = ["format_money", "loan_preview_out", "loans_out", "macro_months", "macro_out"]
