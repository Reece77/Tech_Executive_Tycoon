"""The money limit and one-offs (docs/formulas.md 40.2).

A decision's commitment is its cash cost over the next automation.commitment_months plus every
fixed obligation it creates. Under the owner's limit it goes ahead; at or above it, or if it
is a one-off, it becomes a proposal. Commitments are computed from what the company can see:
salary bands, its own budgets, quoted costs.
"""

from __future__ import annotations

import math

from tst.sim.actions import Action
from tst.sim.automation.config import CONTRACT_ACTIONS, LAYOFF_ACTIONS, ONE_OFF_ACTIONS
from tst.sim.data_models import Balance, GameData
from tst.sim.hiring.formulas import market_mid_cents
from tst.sim.research import levels
from tst.sim.state import GameState

MONTHS_PER_YEAR = 12  # tunable-exempt: calendar
PLAN_LEVEL = "mid"  # tunable-exempt: a plan's hires are costed at the band's mid level


def salary_month(role: str, b: Balance, data: GameData) -> int:
    """A hire's monthly salary at the role's mid band in the home region (13.10's offers)."""
    mid = data.role(role).salary_band_mid_cents[PLAN_LEVEL]
    bp = data.region(b.founder.default_region).salary_multiplier_bp
    return round(market_mid_cents(mid, bp) / MONTHS_PER_YEAR)


def _field(action: Action, name: str, default: object = None) -> object:
    return getattr(action, name, default)


def _int(action: Action, name: str) -> int:
    value = getattr(action, name, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def commitment(state: GameState, action: Action, b: Balance, data: GameData) -> int:
    """Cents committed by one action (40.2): 12 months' cash cost plus fixed obligations."""
    months = b.automation.commitment_months
    kind = action.kind
    if kind == "create_plan":
        role = str(_field(action, "role"))
        target = _int(action, "target")
        return target * salary_month(role, b, data) * months
    if kind == "set_marketing":
        product = state.product(_int(action, "product_id"))
        now = product.marketing_budget_cents if product is not None else 0
        new = _int(action, "budget_cents")
        return max(0, new - now) * months
    if kind == "repay_loan":
        amount = _field(action, "amount_cents")
        loan = next(
            (x for x in state.loans if x.id == _field(action, "loan_id")),
            None,
        )
        if amount is None:
            return loan.balance_cents if loan is not None else 0
        return _int(action, "amount_cents")
    if kind == "start_project":
        domain = str(_field(action, "domain"))
        budget = _field(action, "budget_cents")
        monthly = (
            _int(action, "budget_cents")
            if budget is not None
            else levels.domain_def(data, domain).budget_cents
        )
        return monthly * months
    if kind == "set_project_budget":
        budget = _field(action, "budget_cents")
        return 0 if budget is None else _int(action, "budget_cents") * months
    if kind == "sign_contract":
        return 0  # a contract's take-or-pay is costed when M27b's supply rule signs one
    return 0


def is_one_off(
    state: GameState,
    company_id: int,
    action: Action,
    b: Balance,
    *,
    fired_this_month: int = 0,
) -> bool:
    """40.2's list: always a proposal, whoever owns the area, on Holiday or not."""
    kind = action.kind
    if kind in ONE_OFF_ACTIONS:
        return True
    if kind in LAYOFF_ACTIONS:
        e = state.employment_of(_int(action, "person_id"))
        unit = e.unit_id if e is not None else None
        size = sum(1 for x in state.staff(company_id) if x.unit_id == unit)
        return fired_this_month + 1 >= math.ceil(b.automation.layoff_share * max(size, 1))
    if kind in CONTRACT_ACTIONS:
        return _int(action, "months") > b.automation.long_contract_months
    return False
