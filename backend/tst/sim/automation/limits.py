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
from tst.sim.errors import SimError
from tst.sim.hiring.formulas import market_mid_cents
from tst.sim.ledger import LedgerBalances
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


def commitment(
    state: GameState,
    action: Action,
    b: Balance,
    data: GameData,
    balances: LedgerBalances | None = None,
) -> int:
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
    return chain_commitment(state, action, b, data, balances)


def chain_commitment(
    state: GameState,
    action: Action,
    b: Balance,
    data: GameData,
    balances: LedgerBalances | None = None,
) -> int:
    """M27b (40.12's additions): the chain's actions, from the quotes the player sees. A
    contract commits its take-or-pay over its term (the share of unused volume it charges);
    exploration its stage's, licence's or programme's cost; lobbying its increase x 12; a
    diligence its fee; a bid its price and a mine its estimate. Staffing, safety, routing,
    sales contracts and licence applications commit nothing."""
    from tst.sim.contracts import termination as ct

    kind = action.kind
    try:
        match kind:
            case "sign_manufacturing_contract":
                from tst.sim.actions.hardware import manufacturing_fee_cents

                product = state.product(_int(action, "product_id"))
                if product is None:
                    return 0
                maker, city = str(_field(action, "manufacturer")), str(_field(action, "city"))
                fee = ct.offered(
                    state, maker, manufacturing_fee_cents(b, product.category, maker, city), b
                )
                share = b.hardware.contract.take_or_pay
                return round(_int(action, "units") * fee * share * _int(action, "months"))
            case "sign_wafer_contract":
                from tst.sim.chips import chips

                product = state.product(_int(action, "product_id"))
                if product is None:
                    return 0
                foundry = str(_field(action, "foundry"))
                chip_type = data.category(product.category).chip_type or ""
                node = _field(action, "node")
                price = chips.index_wafer_cents(
                    state, chip_type, b, data, foundry, str(node) if node else None
                )
                price = ct.offered(state, foundry, price, b)
                share = b.chips.contract.take_or_pay
                return round(_int(action, "wafers") * price * share * _int(action, "months"))
            case "sign_commodity_contract" | "sign_offtake":
                from tst.sim.commodities.offtake import spot_price, value_cents

                good = str(_field(action, "good"))
                volume = float(_field(action, "volume_year") or 0.0)  # type: ignore[arg-type]
                if kind == "sign_commodity_contract":
                    years = _int(action, "months") / MONTHS_PER_YEAR
                    price = ct.offered(
                        state, f"traders:{good}", spot_price(state, good, data, b), b
                    )
                    share = b.commodity.contract_take_or_pay
                    return round(value_cents(volume * years, price, good, data) * share)
                supplier = str(_field(action, "supplier"))
                price = ct.offered(state, supplier, spot_price(state, good, data, b), b)
                prepay = float(_field(action, "prepay") or 0.0)  # type: ignore[arg-type]
                year = value_cents(volume, price, good, data)
                share = b.offtake.take_or_pay
                return round(year * _int(action, "years") * share + year * prepay)
            case "start_desk_study":
                return b.exploration.desk.cost_cents
            case "take_licence":
                assert data.geology is not None
                return data.geology.regions[str(_field(action, "region"))].licence_fee_cents
            case "renew_licence" | "start_stage" | "order_drilling":
                from tst.sim.exploration import pipeline
                from tst.sim.exploration.geology import block_of

                project = next(
                    (p for p in state.projects if p.id == _int(action, "project_id")), None
                )
                if project is None:
                    return 0
                if kind == "renew_licence":
                    assert data.geology is not None
                    return data.geology.regions[project.region].licence_fee_cents
                if kind == "start_stage":
                    stage = str(_field(action, "stage"))
                    return pipeline.stage_cost_cents(project, stage, b, data)[0]
                block = block_of(state, project.region, project.block)
                if block is None:
                    return 0
                return _int(action, "holes") * pipeline.hole_cost_cents(project, block, b, data)
            case "set_lobbying":
                from tst.sim.state import influence_of

                e = state.employment_of(action.actor_id)
                company = e.company_id if e is not None else state.player.id
                record = influence_of(state, company, str(_field(action, "region")))
                now = record.spend_cents if record is not None else 0
                new = _int(action, "monthly_dollars") * 100  # tunable-exempt: cents a dollar
                return max(0, new - now) * b.automation.commitment_months
            case "start_diligence":
                from tst.sim.mna import deals
                from tst.sim.mna import formulas as mf

                if balances is None:
                    return b.mna.diligence.min_cents
                e = state.employment_of(action.actor_id)
                company = e.company_id if e is not None else state.player.id
                estimate = deals.estimate_cents(
                    state, company, _int(action, "target_id"), balances, b, data
                )
                return mf.diligence_cost_cents(estimate, b.mna)
            case "bid_for_company":
                return _int(action, "price_cents")
    except (SimError, KeyError, AssertionError, AttributeError):
        return 0
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
