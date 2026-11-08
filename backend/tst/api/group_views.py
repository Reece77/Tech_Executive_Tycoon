"""The Group screen (M16, formulas.md 31.10): the entity tree, from the player's listed entity
(the holding company once formed) down, with each company's stake, treatment and public
numbers."""

from __future__ import annotations

from tst.api.schemas.group import GroupEntityOut, GroupOut
from tst.loader import LoadedData
from tst.sim.group import formulas as gf
from tst.sim.group.models import FULL_STAKE_BP
from tst.sim.group.holding import form_fee_cents, gate
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.mna import valuation
from tst.sim.state import GameState, group_members, holding_of, listed_id, owner_at

MONTHS_A_YEAR = 12


def _numbers(state: GameState, company_id: int) -> tuple[int, float | None]:
    company = state.company(company_id)
    revenue = sum(company.mrr_history[-MONTHS_A_YEAR:])
    ops = company.op_history[-MONTHS_A_YEAR:]
    margin = sum(ops) / revenue if revenue > 0 and ops else None
    return revenue, margin


def _entity(
    state: GameState,
    company_id: int,
    parent_id: int | None,
    depth: int,
    balances: LedgerBalances,
    data: LoadedData,
) -> GroupEntityOut:
    held = holding_of(state)
    if held is not None and company_id == held.company_id:
        role = "holding"
    elif company_id == state.player.id:
        role = "operating"
    elif parent_id is not None:
        role = "subsidiary"
    else:
        role = "company"
    owned = owner_at(state, company_id) if parent_id is not None else None
    stake = owned.stake_bp if owned is not None else FULL_STAKE_BP
    treatment = "root" if parent_id is None else gf.treatment(stake, data.balance)
    revenue, margin = _numbers(state, company_id)
    cap = valuation.market_cap_cents(state, company_id, balances, data.balance, data.game_data)
    low = high = None
    if cap is None and role != "holding":
        low, high = valuation.value_range_cents(
            state, company_id, balances, data.balance, data.game_data
        )
    return GroupEntityOut(
        company_id=company_id,
        name=state.company(company_id).name,
        parent_id=parent_id,
        depth=depth,
        role=role,
        stake_bp=stake,
        treatment=treatment,
        listed=cap is not None,
        revenue_cents=revenue,
        operating_margin=margin,
        cash_cents=account_balance(balances, company_id, CASH),
        market_cap_cents=cap,
        value_low_cents=low,
        value_high_cents=high,
    )


def group_out(state: GameState, balances: LedgerBalances, data: LoadedData) -> GroupOut:
    root = listed_id(state)
    held = holding_of(state)
    reasons = gate(state, data.balance)
    entities = [_entity(state, root, None, 0, balances, data)]
    for m in group_members(state, root):
        if m.end is None and state.company(m.company_id).alive:
            entities.append(_entity(state, m.company_id, m.parent_id, m.depth, balances, data))
    return GroupOut(
        formed=held is not None,
        holding_id=held.company_id if held is not None else None,
        can_form=not reasons,
        reasons=reasons,
        form_energy=data.balance.group.form_energy,
        form_fee_cents=form_fee_cents(state, data.balance) if held is None else 0,
        office_monthly_cents=data.balance.group.office_monthly_cents,
        entities=entities,
    )
