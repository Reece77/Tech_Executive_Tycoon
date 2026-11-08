"""The Group screen (M16, formulas.md 31.10): the entity tree, from the player's listed entity
(the holding company once formed) down, with each company's stake, treatment and public
numbers."""

from __future__ import annotations

from tst.api.schemas.group import (
    GroupEntityOut,
    GroupOut,
    GroupPitchOut,
    PersonalStakeOut,
    StakeOut,
)
from tst.api.views import person_name
from tst.loader import LoadedData
from tst.sim.group import formulas as gf
from tst.sim.group.holding import form_fee_cents, gate
from tst.sim.group.models import FULL_STAKE_BP
from tst.sim.group.subsidiaries import board_seats, is_subsidiary
from tst.sim.ledger import CASH, LedgerBalances, account_balance
from tst.sim.mna import valuation
from tst.sim.press.names import rival_ceo_id
from tst.sim.state import GameState, group_members, holding_of, listed_id, mandate_of, owner_at

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
    stake = owned.stake_at() if owned is not None else FULL_STAKE_BP
    treatment = "root" if parent_id is None else gf.treatment(stake, data.balance)
    revenue, margin = _numbers(state, company_id)
    cap = valuation.market_cap_cents(state, company_id, balances, data.balance, data.game_data)
    low = high = None
    if cap is None and role != "holding":
        low, high = valuation.value_range_cents(
            state, company_id, balances, data.balance, data.game_data
        )
    mandate = mandate_of(state, company_id)
    sub = is_subsidiary(state, company_id)
    ceo = rival_ceo_id(state, company_id) if sub else None
    return GroupEntityOut(
        ceo=person_name(state.person(ceo)) if ceo is not None else None,
        mandate=mandate.kind if mandate is not None else None,
        capex_limit_cents=mandate.capex_limit_cents if mandate is not None else 0,
        review=mandate.last_result if mandate is not None else "",
        misses=mandate.misses if mandate is not None else 0,
        replacement_proposed=bool(mandate and mandate.proposal),
        board_seats=list(board_seats(state, company_id, data.balance)) if sub else [],
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
        pitches=[
            GroupPitchOut(
                id=p.id,
                company_id=p.company_id,
                company=state.company(p.company_id).name,
                ceo=person_name(state.person(p.person_id)),
                turn=p.turn,
                amount_cents=p.amount_cents,
                fits_mandate=p.fits_mandate,
                status=p.status,
            )
            for p in state.group_pitches
            if p.status == "pending"
        ],
        mandate_energy=data.balance.group.mandate.energy,
        stakes=[
            StakeOut(
                company_id=x.company_id,
                company=state.company(x.company_id).name,
                stake_bp=x.stake_bp,
                treatment=gf.treatment(x.stake_bp, data.balance),
                kind=x.kind,
                carrying_cents=x.carrying_cents,
                cost_cents=x.cost_cents,
            )
            for x in state.stakes
            if x.is_open
        ],
        personal_stakes=[
            PersonalStakeOut(
                company_id=x.company_id,
                company=state.company(x.company_id).name,
                stake_bp=x.stake_bp,
            )
            for x in state.personal_stakes
        ],
    )
