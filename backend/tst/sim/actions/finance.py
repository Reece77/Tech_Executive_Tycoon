"""Finance actions (ADR-0014, docs/formulas.md 14.4-14.7): raise on a SAFE, start a
priced round, accept a term sheet (naming a board nominee where it adds a common seat),
accept a bridge, name a nominee to an empty common seat (M4c). They take effect at once
and spend the founder's energy; investors answer at the next Continue.

Every rule an action could break raises `FinanceRuleError`, changing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import INSTRUMENTS, SERIES, Balance, GameData, Instrument
from tst.sim.errors import FinanceRuleError, UnknownSafeError, UnknownTermSheetError
from tst.sim.finance import debt
from tst.sim.finance.board import adds_common_seat, default_nominee, nominee_problem
from tst.sim.finance.captable import open_round
from tst.sim.finance.fundraising import safe_fraction, series_problem
from tst.sim.finance.insolvency import bridge_amount
from tst.sim.finance.models import FundingRound, Safe, SheetStatus
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.money import format_money
from tst.sim.state import GameState, with_round, with_safe, with_seat, with_term_sheet

# --- Action types ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RaiseSafe:
    actor_id: int
    amount_cents: int
    cap_cents: int  # post-money valuation cap
    kind: Literal["raise_safe"] = "raise_safe"


@dataclass(frozen=True, slots=True)
class StartRound:
    actor_id: int
    series: str  # seed, a or b
    target_cents: int
    kind: Literal["start_round"] = "start_round"


@dataclass(frozen=True, slots=True)
class AcceptTermSheet:
    actor_id: int
    sheet_id: int
    # The founder's board nominee when the round adds a common seat (M4c); None: the most
    # senior employee.
    nominee_id: int | None = None
    kind: Literal["accept_term_sheet"] = "accept_term_sheet"


@dataclass(frozen=True, slots=True)
class AcceptBridge:
    actor_id: int
    safe_id: int
    kind: Literal["accept_bridge"] = "accept_bridge"


@dataclass(frozen=True, slots=True)
class NameNominee:
    actor_id: int
    seat_id: int
    person_id: int
    kind: Literal["name_nominee"] = "name_nominee"


@dataclass(frozen=True, slots=True)
class TakeLoan:
    """Sign venture debt or a bank loan (M10, 20.3): energy 10; the lender answers at once."""

    actor_id: int
    instrument: str  # venture_debt or bank_loan
    amount_cents: int
    kind: Literal["take_loan"] = "take_loan"


@dataclass(frozen=True, slots=True)
class RepayLoan:
    """Repay a loan early, in part or in full, with no fee (M10, 20.3): energy 5. None: all."""

    actor_id: int
    loan_id: int
    amount_cents: int | None = None
    kind: Literal["repay_loan"] = "repay_loan"


type FinanceAction = (
    RaiseSafe | StartRound | AcceptTermSheet | AcceptBridge | NameNominee | TakeLoan | RepayLoan
)


def _founder_company(state: GameState, actor_id: int) -> int:
    company = acting_company(state, actor_id)
    founder = state.founder_of(company)
    if founder is None or founder.id != actor_id:
        raise FinanceRuleError("only the founder can raise money")
    return company


def _cents(value: int, what: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FinanceRuleError(f"{what} must be a positive amount in cents")


# --- Actions --------------------------------------------------------------------------------


def raise_safe(state: GameState, action: RaiseSafe, balance: Balance) -> Outcome:
    """$25,000 to $2,000,000 at a post-money cap; one open at a time (14.4)."""
    company = _founder_company(state, action.actor_id)
    sb = balance.finance.safe
    _cents(action.amount_cents, "a SAFE amount")
    _cents(action.cap_cents, "a valuation cap")
    if not sb.min_cents <= action.amount_cents <= sb.max_cents:
        raise FinanceRuleError(
            f"a SAFE raises ${sb.min_cents // 100:,} to ${sb.max_cents // 100:,}"
        )
    if any(s.status == "pending" for s in state.company_safes(company)):
        raise FinanceRuleError("a SAFE raise is already open; investors answer at Continue")
    claimed = safe_fraction(state, company) + Fraction(action.amount_cents, action.cap_cents)
    if claimed >= Fraction(sb.max_fraction).limit_denominator():
        raise FinanceRuleError(
            "the cap is too low: outstanding SAFEs would claim "
            f"{float(claimed) * 100:.0f}% of the company"
        )
    state = spend_energy(state, action.actor_id, "raise_safe", balance)
    safe_id, ids = state.next_ids.take("safe")
    safe = Safe(
        id=safe_id,
        company_id=company,
        kind="safe",
        amount_cents=action.amount_cents,
        cap_cents=action.cap_cents,
        status="pending",
        raised_turn=state.turn,
    )
    return Outcome(with_safe(replace(state, next_ids=ids), safe))


def start_round(state: GameState, action: StartRound, balance: Balance) -> Outcome:
    """The next series once its gate is met; open for open_turns turns (14.5)."""
    company = _founder_company(state, action.actor_id)
    if action.series not in SERIES:
        raise FinanceRuleError(f"unknown series {action.series!r}; one of {list(SERIES)}")
    _cents(action.target_cents, "a round target")
    if open_round(state, company) is not None:
        raise FinanceRuleError("a priced round is already open")
    problem = series_problem(state, company, action.series, balance)
    if problem is not None:
        raise FinanceRuleError(problem)
    state = spend_energy(state, action.actor_id, "start_round", balance)
    round_id, ids = state.next_ids.take("round")
    rnd = FundingRound(
        id=round_id,
        company_id=company,
        series=action.series,  # type: ignore[arg-type]
        status="open",
        target_cents=action.target_cents,
        opened_turn=state.turn,
        expires_turn=state.turn + balance.finance.round.open_turns - 1,
    )
    return Outcome(with_round(replace(state, next_ids=ids), rnd))


def accept_term_sheet(state: GameState, action: AcceptTermSheet, balance: Balance) -> Outcome:
    """The round closes at the next Continue (phase 1); the other term sheets lapse."""
    company = _founder_company(state, action.actor_id)
    sheet = state.term_sheet(action.sheet_id)
    rnd = state.funding_round(sheet.round_id) if sheet is not None else None
    if sheet is None or rnd is None or rnd.company_id != company:
        raise UnknownTermSheetError(f"no term sheet {action.sheet_id}")
    if rnd.status != "open" or sheet.status != "offered" or state.turn > sheet.expires_turn:
        raise FinanceRuleError("that term sheet is no longer open")
    nominee = None
    if adds_common_seat(state, company, rnd.series, balance):
        nominee = action.nominee_id
        if nominee is None:
            nominee = default_nominee(state, company)
        elif (problem := nominee_problem(state, company, nominee)) is not None:
            raise FinanceRuleError(f"cannot nominate them to the board: {problem}")
    elif action.nominee_id is not None:
        raise FinanceRuleError("this round adds no common seat to name a nominee for")
    state = spend_energy(state, action.actor_id, "accept_term_sheet", balance)
    for other in state.sheets_of(rnd.id):
        status: SheetStatus = "accepted" if other.id == sheet.id else "lapsed"
        if other.status == "offered":
            state = with_term_sheet(state, replace(other, status=status))
    state = with_round(
        state, replace(rnd, status="accepted", accepted_sheet_id=sheet.id, nominee_id=nominee)
    )
    return Outcome(state)


def name_nominee(state: GameState, action: NameNominee, balance: Balance) -> Outcome:
    """Fill an empty common seat with an employee (14.6, M4c)."""
    company = _founder_company(state, action.actor_id)
    seat = next((s for s in state.board(company) if s.id == action.seat_id), None)
    if seat is None or seat.kind != "common" or not seat.vacant:
        raise FinanceRuleError(f"seat {action.seat_id} is not an empty common seat")
    problem = nominee_problem(state, company, action.person_id)
    if problem is not None:
        raise FinanceRuleError(f"cannot nominate them to the board: {problem}")
    state = spend_energy(state, action.actor_id, "name_nominee", balance)
    seat = replace(seat, person_id=action.person_id, seated_turn=state.turn)
    return Outcome(with_seat(state, seat))


def accept_bridge(
    state: GameState,
    action: AcceptBridge,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
) -> Outcome:
    """The bridge's money arrives in phase 7 of this turn (14.7), sized now: three months of
    this month's projected burn plus today's deficit (M4b)."""
    company = _founder_company(state, action.actor_id)
    safe = state.safe(action.safe_id)
    if safe is None or safe.company_id != company or safe.kind != "bridge":
        raise UnknownSafeError(f"no bridge offer {action.safe_id}")
    if safe.status != "offered" or (
        safe.expires_turn is not None and state.turn > safe.expires_turn
    ):
        raise FinanceRuleError("that bridge offer is no longer open")
    state = spend_energy(state, action.actor_id, "accept_bridge", balance)
    cash = account_balance(ledger_balances, company, CASH)
    amount = bridge_amount(state, company, cash, balance, data)
    return Outcome(with_safe(state, replace(safe, status="accepted", amount_cents=amount)))


def take_loan(state: GameState, action: TakeLoan, balance: Balance, data: GameData) -> Outcome:
    company = _founder_company(state, action.actor_id)
    if action.instrument not in INSTRUMENTS:
        raise FinanceRuleError(
            f"unknown instrument {action.instrument!r}; one of {list(INSTRUMENTS)}"
        )
    instrument: Instrument = action.instrument
    _cents(action.amount_cents, "a loan amount")
    problem = debt.amount_problem(state, company, instrument, action.amount_cents, balance, data)
    if problem is not None:
        raise FinanceRuleError(problem)
    state = spend_energy(
        state, action.actor_id, "take_loan", balance, cost=balance.debt.take_energy
    )
    state, loan, entries = debt.sign(state, company, instrument, action.amount_cents, balance, data)
    log = inbox_item(
        state.turn,
        company,
        "loan_signed",
        link_kind="finance",
        instrument=debt.INSTRUMENT_LABELS[instrument],
        lender=debt.lender_name(loan, data),
        amount_cents=loan.principal_cents,
        rate=f"{loan.rate_bp / 100:.2f}%",
        term=loan.term_months,
    )
    return Outcome(state, entries, (log,))


def repay_loan(
    state: GameState,
    action: RepayLoan,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
) -> Outcome:
    company = _founder_company(state, action.actor_id)
    loan = state.loan(action.loan_id)
    if loan is None or loan.company_id != company:
        raise FinanceRuleError(f"no loan {action.loan_id}")
    if not loan.active:
        raise FinanceRuleError("that loan is no longer outstanding")
    amount = loan.balance_cents if action.amount_cents is None else action.amount_cents
    _cents(amount, "a repayment")
    if amount > loan.balance_cents:
        raise FinanceRuleError(f"the balance is {format_money(loan.balance_cents)}")
    if amount > account_balance(ledger_balances, company, CASH):
        raise FinanceRuleError("there is not enough cash to repay that much")
    state = spend_energy(
        state, action.actor_id, "repay_loan", balance, cost=balance.debt.repay_energy
    )
    name = debt.lender_name(loan, data)
    state, loan, entries = debt.repay(state, loan, amount, f"Early repayment: {name}")
    logs = (
        (
            inbox_item(
                state.turn,
                company,
                "loan_repaid",
                link_kind="finance",
                lender=name,
                amount_cents=loan.principal_cents,
            ),
        )
        if not loan.active
        else ()
    )
    return Outcome(state, entries, logs)


def apply_finance(
    state: GameState,
    action: FinanceAction,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
) -> Outcome:
    match action:
        case RaiseSafe():
            return raise_safe(state, action, balance)
        case StartRound():
            return start_round(state, action, balance)
        case AcceptTermSheet():
            return accept_term_sheet(state, action, balance)
        case AcceptBridge():
            return accept_bridge(state, action, balance, data, ledger_balances)
        case NameNominee():
            return name_nominee(state, action, balance)
        case TakeLoan():
            return take_loan(state, action, balance, data)
        case RepayLoan():
            return repay_loan(state, action, balance, data, ledger_balances)
