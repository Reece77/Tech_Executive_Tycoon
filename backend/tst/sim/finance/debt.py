"""Debt (docs/formulas.md 20.3, M10): venture debt and bank loans, their monthly interest and
principal, early repayment, covenants and breaches.

A lender answers at once with no draw: it says yes if the gate holds, and the rate is fixed
at signing (base rate + spread). Phase 7 charges each active loan's interest and principal
from cash, then tests covenants. A breach queues a critical `lender` event for next month
(its choices: a waiver fee, a higher rate, or repaying a quarter); covenants then rest for
`breach.cure_months`; a second breach within `breach.call_window_months` of the first makes
the whole balance due, and a shortfall counts toward bankruptcy (14.7).

Covenants read completed months: the last month's burn and the operating result of the last
`covenant_profit_months` months (CompanyState.op_history, burn_history), with this month's
cash after the payments.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData, Instrument, Lender
from tst.sim.events.models import QueuedEvent
from tst.sim.finance.captable import fd_shares, last_round
from tst.sim.finance.macro import base_rate
from tst.sim.finance.models import CapEntry, FundingRound, Loan
from tst.sim.ledger import CASH, DEBT, INTEREST, AccountCode, LedgerEntry, account_balance
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import BP_DENOMINATOR, Cents, format_money
from tst.sim.state import GameState, with_cap_entry, with_loan, with_queued

MONTHS_PER_YEAR = 12  # tunable-exempt: an annual rate's monthly share
PCT_TO_BP = 100  # tunable-exempt: % to basis points
BREACH_TEMPLATE: Final = "lender_covenant_breach"  # data/events/lender.yaml
CALLED_TEMPLATE: Final = "lender_loan_called"
INSTRUMENT_LABELS: Final[dict[Instrument, str]] = {
    "venture_debt": "Venture debt",
    "bank_loan": "Bank loan",
}


# --- Pricing and the schedule ------------------------------------------------------------------


def rate_bp(base_rate_pct: float, spread_bp: int) -> int:
    """The rate fixed at signing: the base rate (rounded to a basis point) plus the spread."""
    return round(base_rate_pct * PCT_TO_BP) + spread_bp


def monthly_interest_cents(balance_cents: Cents, annual_bp: int) -> Cents:
    """round(balance x rate / 12), exactly, half-to-even (20.3; 20.6: $6M at 6.25% = $31,250)."""
    return round(Fraction(balance_cents * annual_bp, MONTHS_PER_YEAR * BP_DENOMINATOR))


def scheduled_principal(loan: Loan, turn: int) -> Cents:
    """Principal due in `turn`: none in the interest-only months, then the balance spread
    evenly over the months left (equal principal; a partial repayment lowers each payment,
    never extends the term); the whole balance in the last month."""
    m = loan.month_index(turn)
    if m <= loan.interest_only_months or loan.balance_cents <= 0:
        return 0
    left = loan.term_months - m + 1
    if left <= 1:
        return loan.balance_cents
    return min(loan.balance_cents, round(Fraction(loan.balance_cents, left)))


@dataclass(frozen=True, slots=True)
class Payment:
    turn: int
    interest_cents: Cents
    principal_cents: Cents
    balance_after_cents: Cents


def schedule(loan: Loan, from_turn: int) -> tuple[Payment, ...]:
    """The payments from `from_turn` to the end of the term at today's balance and rate (the
    Debt tab's schedule; a breach can change it)."""
    out: list[Payment] = []
    current = loan
    for turn in range(max(from_turn, loan.signed_turn), loan.last_turn + 1):
        if current.balance_cents <= 0:
            break
        interest = monthly_interest_cents(current.balance_cents, current.rate_bp)
        principal = scheduled_principal(current, turn)
        current = replace(current, balance_cents=current.balance_cents - principal)
        out.append(Payment(turn, interest, principal, current.balance_cents))
    return tuple(out)


# --- Gates -------------------------------------------------------------------------------------


def lender_for(instrument: Instrument, year: int, data: GameData) -> Lender | None:
    return next((x for x in data.lenders if x.offers(instrument, year)), None)


def venture_round(state: GameState, company_id: int, balance: Balance) -> FundingRound | None:
    """The priced round venture debt can follow: the latest, if it closed within the window."""
    latest = last_round(state, company_id)
    if latest is None or latest.closed_turn is None or latest.amount_cents is None:
        return None
    if state.turn >= latest.closed_turn + balance.debt.venture.window_turns:
        return None
    return latest


def arr_now(state: GameState, company_id: int) -> Cents:
    """ARR from last month end's MRR (14.3)."""
    company = state.company(company_id)
    return (company.mrr_history[-1] if company.mrr_history else 0) * MONTHS_PER_YEAR


def capacity_cents(
    state: GameState, company_id: int, instrument: Instrument, balance: Balance
) -> Cents:
    """How much more the instrument can lend now: venture debt up to 30% of the round it
    follows (less what was borrowed against it); a bank up to 1 x ARR (less what is owed)."""
    loans = [x for x in state.company_loans(company_id) if x.instrument == instrument]
    if instrument == "venture_debt":
        rnd = venture_round(state, company_id, balance)
        if rnd is None or rnd.amount_cents is None:
            return 0
        limit = rnd.amount_cents * balance.debt.venture.max_of_round_bp // BP_DENOMINATOR
        used = sum(x.principal_cents for x in loans if x.round_id == rnd.id)
        return max(0, limit - used)
    limit = arr_now(state, company_id) * balance.debt.bank.max_of_arr_bp // BP_DENOMINATOR
    return max(0, limit - sum(x.balance_cents for x in loans if x.active))


def gate_problem(
    state: GameState, company_id: int, instrument: Instrument, balance: Balance, data: GameData
) -> str | None:
    """Why the instrument is not offered now (20.3), or None."""
    if instrument == "venture_debt":
        if venture_round(state, company_id, balance) is None:
            months = balance.debt.venture.window_turns
            return f"venture debt follows a priced round, within {months} months of it closing"
    else:
        bb = balance.debt.bank
        company = state.company(company_id)
        if company.stage < bb.stage:
            return f"a bank lends from stage {bb.stage}"
        recent = company.op_history[-bb.profit_months :]
        if len(recent) < bb.profit_months or any(x <= 0 for x in recent):
            return f"a bank wants an operating profit in each of the last {bb.profit_months} months"
    if lender_for(instrument, turn_to_ym(state.turn)[0], data) is None:
        return "no lender offers it this year"
    if capacity_cents(state, company_id, instrument, balance) < balance.debt.min_cents:
        return "the limit is already borrowed"
    return None


def amount_problem(
    state: GameState,
    company_id: int,
    instrument: Instrument,
    amount_cents: Cents,
    balance: Balance,
    data: GameData,
) -> str | None:
    problem = gate_problem(state, company_id, instrument, balance, data)
    if problem is not None:
        return problem
    most = capacity_cents(state, company_id, instrument, balance)
    if not balance.debt.min_cents <= amount_cents <= most:
        return f"the amount must be {format_money(balance.debt.min_cents)} to {format_money(most)}"
    return None


@dataclass(frozen=True, slots=True)
class LoanTerms:
    """What a lender would offer now (the Take a loan dialog)."""

    instrument: Instrument
    lender: Lender | None
    rate_bp: int
    term_months: int
    interest_only_months: int
    max_cents: Cents
    warrant_bp: int
    problem: str | None


def terms(
    state: GameState, company_id: int, instrument: Instrument, balance: Balance, data: GameData
) -> LoanTerms:
    venture = instrument == "venture_debt"
    vb, bb = balance.debt.venture, balance.debt.bank
    spread = vb.spread_bp if venture else bb.spread_bp
    return LoanTerms(
        instrument=instrument,
        lender=lender_for(instrument, turn_to_ym(state.turn)[0], data),
        rate_bp=rate_bp(base_rate(state, data), spread),
        term_months=vb.term_months if venture else bb.term_months,
        interest_only_months=vb.interest_only_months if venture else 0,
        max_cents=capacity_cents(state, company_id, instrument, balance),
        warrant_bp=vb.warrant_bp if venture else 0,
        problem=gate_problem(state, company_id, instrument, balance, data),
    )


def warrant_shares(fd: int, warrant_bp: int) -> int:
    """Shares that make the lender hold `warrant_bp` of FD after they are issued."""
    if warrant_bp <= 0:
        return 0
    return round(Fraction(fd * warrant_bp, BP_DENOMINATOR - warrant_bp))


def sign(
    state: GameState,
    company_id: int,
    instrument: Instrument,
    amount_cents: Cents,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, Loan, tuple[LedgerEntry, ...]]:
    """Sign a loan the gate allows: the money in (debit cash, credit 2500_debt) and a venture
    lender's warrants on the cap table. Callers check `amount_problem` first."""
    t = terms(state, company_id, instrument, balance, data)
    assert t.lender is not None
    loan_id, ids = state.next_ids.take("loan")
    state = replace(state, next_ids=ids)
    rnd = venture_round(state, company_id, balance) if instrument == "venture_debt" else None
    shares = warrant_shares(fd_shares(state, company_id), t.warrant_bp)
    loan = Loan(
        id=loan_id,
        company_id=company_id,
        instrument=instrument,
        lender=t.lender.key,
        principal_cents=amount_cents,
        balance_cents=amount_cents,
        rate_bp=t.rate_bp,
        signed_turn=state.turn,
        term_months=t.term_months,
        interest_only_months=t.interest_only_months,
        round_id=rnd.id if rnd is not None else None,
        warrant_shares=shares,
    )
    state = with_loan(state, loan)
    if shares:
        entry_id, ids = state.next_ids.take("cap_entry")
        state = with_cap_entry(
            replace(state, next_ids=ids),
            CapEntry(
                id=entry_id,
                company_id=company_id,
                holder_kind="group",
                share_class="warrant",
                shares=shares,
                acquired_turn=state.turn,
                name=t.lender.name,
            ),
        )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo=f"{INSTRUMENT_LABELS[instrument]}: {t.lender.name}",
        debit=CASH,
        credit=DEBT,
        amount=amount_cents,
    )
    return state, loan, (entry,)


def repay(
    state: GameState, loan: Loan, amount_cents: Cents, memo: str
) -> tuple[GameState, Loan, tuple[LedgerEntry, ...]]:
    """Pay `amount_cents` of principal from cash now (no fee, 20.3). The whole balance closes
    the loan as repaid."""
    amount = min(amount_cents, loan.balance_cents)
    if amount <= 0:
        return state, loan, ()
    left = loan.balance_cents - amount
    loan = replace(
        loan,
        balance_cents=left,
        principal_paid_cents=loan.principal_paid_cents + amount,
        status="repaid" if left == 0 else loan.status,
        closed_turn=state.turn if left == 0 else loan.closed_turn,
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=loan.company_id,
        memo=memo,
        debit=DEBT,
        credit=CASH,
        amount=amount,
    )
    return with_loan(state, loan), loan, (entry,)


# --- Covenants -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Covenant:
    """A covenant's test now: what is measured, what it must be, and the headroom (the
    measure minus the requirement; below zero is a breach)."""

    description: str
    measure_cents: Cents
    required_cents: Cents

    @property
    def headroom_cents(self) -> Cents:
        return self.measure_cents - self.required_cents

    @property
    def holds(self) -> bool:
        return self.headroom_cents >= 0


def covenants(state: GameState, loan: Loan, cash_cents: Cents, balance: Balance) -> list[Covenant]:
    """Venture debt: cash at least 3 months of last month's burn. Bank loan: the operating
    result over the last 3 months above zero, and cash at least 10% of the balance (20.3)."""
    company = state.company(loan.company_id)
    if loan.instrument == "venture_debt":
        vb = balance.debt.venture
        burn = company.burn_history[-1] if company.burn_history else 0
        need = round(Fraction(vb.covenant_burn_months).limit_denominator() * burn)
        return [
            Covenant(f"Cash covers {vb.covenant_burn_months:g} months of burn", cash_cents, need)
        ]
    bb = balance.debt.bank
    profit = sum(company.op_history[-bb.covenant_profit_months :])
    cash_need = loan.balance_cents * bb.covenant_cash_bp // BP_DENOMINATOR
    return [
        # "Above zero": a result of exactly zero breaches, so the requirement is one cent.
        Covenant(f"Operating profit over {bb.covenant_profit_months} months", profit, 1),
        Covenant(
            f"Cash covers {bb.covenant_cash_bp / 100:g}% of the balance", cash_cents, cash_need
        ),
    ]


def tested(loan: Loan, turn: int, balance: Balance) -> bool:
    """Covenants rest for `cure_months` after a breach (M10 decision)."""
    cure = balance.debt.breach.cure_months
    return loan.breach_turn is None or turn > loan.breach_turn + cure


def queue_lender_event(state: GameState, loan: Loan, template: str) -> GameState:
    queued_id, ids = state.next_ids.take("queued")
    return with_queued(
        replace(state, next_ids=ids),
        QueuedEvent(
            id=queued_id,
            company_id=loan.company_id,
            template_id=template,
            due_turn=state.turn + 1,
            source_event_id=None,  # the engine queued it, not an event
            loan_id=loan.id,
        ),
    )


def lender_name(loan: Loan, data: GameData) -> str:
    return next((x.name for x in data.lenders if x.key == loan.lender), loan.lender)


def debt_month(
    state: GameState,
    balances: Mapping[tuple[int, AccountCode], Cents],
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    """Phase 7: each active loan's interest (to 7000_interest) and principal (from 2500_debt),
    both from cash; then covenants, a breach's lender event, or a called loan (20.3)."""
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    paid: dict[int, Cents] = {}
    for loan in state.loans:
        if not loan.active or loan.signed_turn > state.turn:
            continue
        name = lender_name(loan, data)
        interest = monthly_interest_cents(loan.balance_cents, loan.rate_bp)
        principal = scheduled_principal(loan, state.turn)
        if interest:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=loan.company_id,
                    memo=f"Interest: {name}",
                    debit=INTEREST,
                    credit=CASH,
                    amount=interest,
                )
            )
        loan = replace(loan, interest_paid_cents=loan.interest_paid_cents + interest)
        state = with_loan(state, loan)
        paid[loan.company_id] = paid.get(loan.company_id, 0) + interest
        if principal:
            state, loan, posted = repay(state, loan, principal, f"Principal: {name}")
            entries += posted
            paid[loan.company_id] += principal
            if not loan.active:
                logs.append(
                    inbox_item(
                        state.turn,
                        loan.company_id,
                        "loan_repaid",
                        link_kind="finance",
                        lender=name,
                        amount_cents=loan.principal_cents,
                    )
                )
    bb = balance.debt.breach
    for loan in state.loans:
        if not loan.active or not tested(loan, state.turn, balance):
            continue
        cash = account_balance(balances, loan.company_id, CASH) - paid.get(loan.company_id, 0)
        broken = [c for c in covenants(state, loan, cash, balance) if not c.holds]
        if not broken:
            continue
        name = lender_name(loan, data)
        if loan.breach_turn is not None and state.turn - loan.breach_turn <= bb.call_window_months:
            due = loan.balance_cents
            state, loan, posted = repay(state, loan, due, f"Loan called: {name}")
            loan = replace(loan, status="called", breaches=loan.breaches + 1)
            state = with_loan(state, loan)
            entries += posted
            paid[loan.company_id] = paid.get(loan.company_id, 0) + due
            logs.append(
                inbox_item(
                    state.turn,
                    loan.company_id,
                    "loan_called",
                    link_kind="finance",
                    lender=name,
                    amount_cents=due,
                )
            )
            if loan.company_id == state.player.id:
                state = queue_lender_event(state, loan, CALLED_TEMPLATE)
            continue
        loan = replace(loan, breach_turn=state.turn, breaches=loan.breaches + 1)
        state = with_loan(state, loan)
        logs.append(
            inbox_item(
                state.turn,
                loan.company_id,
                "covenant_breached",
                link_kind="finance",
                lender=name,
                covenant=broken[0].description,
            )
        )
        if loan.company_id == state.player.id:
            state = queue_lender_event(state, loan, BREACH_TEMPLATE)
    return state, tuple(entries), tuple(logs)
