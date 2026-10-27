"""Finance actions (ADR-0014, docs/formulas.md 14.4, 14.5, 14.7): raise on a SAFE, start a
priced round, accept a term sheet, accept a bridge. They take effect at once and spend the
founder's energy; investors answer at the next Continue.

Every rule an action could break raises `FinanceRuleError`, changing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import SERIES, Balance, GameData
from tst.sim.errors import FinanceRuleError, UnknownSafeError, UnknownTermSheetError
from tst.sim.finance.captable import open_round
from tst.sim.finance.fundraising import safe_fraction, series_problem
from tst.sim.finance.models import FundingRound, Safe, SheetStatus
from tst.sim.state import GameState, with_round, with_safe, with_term_sheet

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
    kind: Literal["accept_term_sheet"] = "accept_term_sheet"


@dataclass(frozen=True, slots=True)
class AcceptBridge:
    actor_id: int
    safe_id: int
    kind: Literal["accept_bridge"] = "accept_bridge"


type FinanceAction = RaiseSafe | StartRound | AcceptTermSheet | AcceptBridge


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
    state = spend_energy(state, action.actor_id, "accept_term_sheet", balance)
    for other in state.sheets_of(rnd.id):
        status: SheetStatus = "accepted" if other.id == sheet.id else "lapsed"
        if other.status == "offered":
            state = with_term_sheet(state, replace(other, status=status))
    state = with_round(state, replace(rnd, status="accepted", accepted_sheet_id=sheet.id))
    return Outcome(state)


def accept_bridge(state: GameState, action: AcceptBridge, balance: Balance) -> Outcome:
    """The bridge's money arrives in phase 7 of this turn (14.7)."""
    company = _founder_company(state, action.actor_id)
    safe = state.safe(action.safe_id)
    if safe is None or safe.company_id != company or safe.kind != "bridge":
        raise UnknownSafeError(f"no bridge offer {action.safe_id}")
    if safe.status != "offered" or (
        safe.expires_turn is not None and state.turn > safe.expires_turn
    ):
        raise FinanceRuleError("that bridge offer is no longer open")
    state = spend_energy(state, action.actor_id, "accept_bridge", balance)
    return Outcome(with_safe(state, replace(safe, status="accepted")))


def apply_finance(
    state: GameState, action: FinanceAction, balance: Balance, data: GameData
) -> Outcome:
    match action:
        case RaiseSafe():
            return raise_safe(state, action, balance)
        case StartRound():
            return start_round(state, action, balance)
        case AcceptTermSheet():
            return accept_term_sheet(state, action, balance)
        case AcceptBridge():
            return accept_bridge(state, action, balance)
