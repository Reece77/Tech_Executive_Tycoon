"""Public-company actions (docs/formulas.md 25, M13): hire the banks, set guidance, buy
back shares, declare a dividend, run a secondary offering, and the Chair's CEO actions.
Immediate actions (ADR-0014); only the founder (as Chair) may take them."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from tst.sim.actions.hiring import Outcome, acting_company, spend_energy
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import FinanceRuleError, InvalidActionError, OrgRuleError
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.log import inbox_item
from tst.sim.markets_public import capital, ipo
from tst.sim.markets_public.config import CEO_SCOPES
from tst.sim.markets_public.formulas import PCT
from tst.sim.markets_public.models import Guidance
from tst.sim.markets_public.public import consensus, guidance_problem, outstanding_shares
from tst.sim.org import ceo_rules
from tst.sim.state import GameState, ceo_of, with_ceo, with_guidance


@dataclass(frozen=True, slots=True)
class HireBanks:
    actor_id: int
    bank: str  # banks.yaml key
    kind: Literal["hire_banks"] = "hire_banks"


@dataclass(frozen=True, slots=True)
class SetGuidance:
    actor_id: int
    revenue_cents: int  # the quarter's revenue
    margin_bp: int  # operating margin, basis points (may be negative)
    kind: Literal["set_guidance"] = "set_guidance"


@dataclass(frozen=True, slots=True)
class Buyback:
    actor_id: int
    amount_cents: int
    kind: Literal["buyback"] = "buyback"


@dataclass(frozen=True, slots=True)
class DeclareDividend:
    actor_id: int
    per_share_cents: int
    kind: Literal["declare_dividend"] = "declare_dividend"


@dataclass(frozen=True, slots=True)
class SecondaryOffering:
    actor_id: int
    shares: int
    kind: Literal["secondary_offering"] = "secondary_offering"


@dataclass(frozen=True, slots=True)
class AppointCeo:
    actor_id: int
    person_id: int
    kind: Literal["appoint_ceo"] = "appoint_ceo"


@dataclass(frozen=True, slots=True)
class SetCeoAuthority:
    actor_id: int
    scopes: tuple[str, ...]  # config.CEO_SCOPES the CEO may run
    kind: Literal["set_ceo_authority"] = "set_ceo_authority"


@dataclass(frozen=True, slots=True)
class DismissCeo:
    actor_id: int
    kind: Literal["dismiss_ceo"] = "dismiss_ceo"


@dataclass(frozen=True, slots=True)
class OverrideCeo:
    """Reverse one CEO decision (25.6). Applied by apply_action, which runs the undo."""

    actor_id: int
    decision_id: int
    kind: Literal["override_ceo"] = "override_ceo"


type PublicAction = (
    HireBanks
    | SetGuidance
    | Buyback
    | DeclareDividend
    | SecondaryOffering
    | AppointCeo
    | SetCeoAuthority
    | DismissCeo
    | OverrideCeo
)


def _spend(state: GameState, action: PublicAction, cost: int, balance: Balance) -> GameState:
    return spend_energy(state, action.actor_id, action.kind, balance, cost=cost)


def chair_company(state: GameState, actor_id: int) -> int:
    company = acting_company(state, actor_id)
    founder = state.founder_of(company)
    if founder is None or founder.id != actor_id:
        raise FinanceRuleError("only the founder, as Chair, can do that")
    return company


def apply_public(
    state: GameState,
    action: PublicAction,
    balance: Balance,
    data: GameData,
    ledger_balances: LedgerBalances,
) -> Outcome:
    company = chair_company(state, action.actor_id)
    cash = account_balance(ledger_balances, company, CASH)
    turn = state.turn
    match action:
        case HireBanks():
            problem = ipo.eligibility_problem(state, company, balance)
            if problem:
                raise FinanceRuleError(problem)
            try:
                bank = data.bank(action.bank)
            except KeyError:
                raise InvalidActionError(f"unknown bank {action.bank!r}") from None
            state = _spend(state, action, balance.ipo.hire_energy, balance)
            state = ipo.hire_banks(state, company, bank.key, balance, data)
            log = inbox_item(turn, company, "banks_hired", bank=bank.name, fee=f"{bank.fee:.1%}")
            return Outcome(state, (), (log,))
        case SetGuidance():
            problem = guidance_problem(state, company, action.revenue_cents, balance)
            if problem:
                raise FinanceRuleError(problem)
            if not -PCT * PCT <= action.margin_bp <= PCT * PCT:
                raise InvalidActionError("margin guidance is in basis points, -10000 to 10000")
            eb = balance.public.earnings
            state = _spend(state, action, eb.guidance_energy, balance)
            rev, margin = consensus(state, company)
            g = Guidance(company, turn, action.revenue_cents, action.margin_bp, rev, margin, True)
            state = with_guidance(state, g)
            log = inbox_item(
                turn,
                company,
                "guidance_set",
                revenue_cents=action.revenue_cents,
                margin=f"{action.margin_bp / PCT:.1f}%",
                consensus_cents=rev,
            )
            return Outcome(state, (), (log,))
        case Buyback():
            cb = balance.public.capital
            state = _spend(state, action, cb.buyback_energy, balance)
            state, entry, shares, cost = capital.buyback(
                state, company, action.amount_cents, cash, balance
            )
            log = inbox_item(turn, company, "buyback_done", shares=shares, amount_cents=cost)
            return Outcome(state, (entry,), (log,))
        case DeclareDividend():
            cb = balance.public.capital
            outstanding = outstanding_shares(state, company)
            state = capital.declare_dividend(
                state, company, action.per_share_cents, cash, outstanding
            )
            state = _spend(state, action, cb.dividend_energy, balance)
            log = inbox_item(
                turn,
                company,
                "dividend_declared",
                per_share_cents=action.per_share_cents,
                amount_cents=action.per_share_cents * outstanding,
            )
            return Outcome(state, (), (log,))
        case SecondaryOffering():
            cb = balance.public.capital
            state, entry, net = capital.secondary(state, company, action.shares, balance)
            state = _spend(state, action, cb.secondary_energy, balance)
            log = inbox_item(turn, company, "secondary_done", shares=action.shares, net_cents=net)
            return Outcome(state, (entry,), (log,))
        case AppointCeo():
            state = ceo_rules.appoint(state, company, action.person_id, balance, data)
            state = _spend(state, action, balance.ceo.appoint_energy, balance)
            person = state.person(action.person_id)
            log = inbox_item(
                turn,
                company,
                "ceo_appointed",
                link_kind="person",
                link_id=person.id,
                name=f"{person.first_name} {person.last_name}",
            )
            return Outcome(state, (), (log,))
        case SetCeoAuthority():
            current = ceo_of(state, company)
            if current is None:
                raise OrgRuleError("there is no CEO")
            unknown = sorted(set(action.scopes) - set(CEO_SCOPES))
            if unknown:
                raise InvalidActionError(f"unknown CEO scopes {unknown}")
            state = spend_energy(
                state,
                action.actor_id,
                "set_ceo_authority",
                balance,
                cost=balance.exec_authority.change_energy,
            )
            scopes = tuple(s for s in CEO_SCOPES if s in action.scopes)
            return Outcome(with_ceo(state, replace(current, scopes=scopes)))
        case DismissCeo():
            current = ceo_of(state, company)
            if current is None:
                raise OrgRuleError("there is no CEO")
            state = _spend(state, action, balance.ceo.appoint_energy, balance)
            state = with_ceo(state, replace(current, ended_turn=turn, end_reason="dismissed"))
            person = state.person(current.person_id)
            log = inbox_item(
                turn, company, "ceo_left", name=f"{person.first_name} {person.last_name}"
            )
            return Outcome(state, (), (log,))
        case OverrideCeo():  # handled in apply_action, which applies the undo
            raise InvalidActionError("override_ceo is applied by apply_action")


def override_target(
    state: GameState, actor_id: int, decision_id: int, balance: Balance
) -> tuple[int, ceo_rules.Undo]:
    """The company and the undo of a CEO decision the Chair may override (25.6)."""
    company = chair_company(state, actor_id)
    decision = next((d for d in state.ceo_decisions if d.id == decision_id), None)
    if decision is None or decision.company_id != company:
        raise InvalidActionError(f"no CEO decision {decision_id}")
    if decision.overridden_turn is not None:
        raise OrgRuleError("that decision was already overridden")
    if not decision.undo:
        raise OrgRuleError("that decision cannot be undone")
    ps = state.person_state(actor_id)
    if ps.energy is not None and ps.energy < balance.ceo.override_energy:
        raise OrgRuleError(f"an override needs {balance.ceo.override_energy} energy")
    return company, decision.undo


def mark_overridden(
    state: GameState, decision_id: int, actor_id: int, energy_before: int | None, balance: Balance
) -> GameState:
    """The decision is overridden, the CEO's price anchor follows, and the Chair pays exactly
    ceo.override_energy (the inner action's own cost is refunded)."""
    from tst.sim.state import with_ceo_decision, with_person_state

    decision = next(d for d in state.ceo_decisions if d.id == decision_id)
    state = with_ceo_decision(state, replace(decision, overridden_turn=state.turn))
    state = ceo_rules.follow_chair_price(state, decision.company_id, decision.undo)
    ps = state.person_state(actor_id)
    if energy_before is not None:
        state = with_person_state(
            state, replace(ps, energy=energy_before - balance.ceo.override_energy)
        )
    return state
