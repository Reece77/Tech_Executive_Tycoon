"""Save-scoped routes for breaking contracts (M23a; playtest 5's Terminate button): the quoted
fee before confirming, and the termination. Any contract or offtake of the player's group:
commodity, refining, production (contract manufacturing and foundry wafers), mine sales and a
fab's foundry contracts."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api import views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.contracts import ContractActionOut, TerminateIn, TerminationQuoteOut
from tst.db import inbox, repository
from tst.sim.contracts import termination as ct

router = APIRouter(prefix="/api/saves/{save_id}", tags=["contracts"])


@router.get(
    "/contracts/{contract}/{contract_id}/quote",
    response_model=TerminationQuoteOut,
    responses=ERRORS,
    operation_id="quoteTermination",
)
def quote_termination(
    save_id: str, contract: str, contract_id: int, settings: SettingsDep, data: DataDep
) -> TerminationQuoteOut:
    """What breaking a contract would cost now (fee = the remaining months' take-or-pay minimum
    discounted at the base rate, plus contracts.break_penalty), before confirming."""
    state = _state(_path(settings, save_id))
    q = ct.quote(state, contract, contract_id, data.balance, data.game_data)  # type: ignore[arg-type]
    return TerminationQuoteOut(
        contract=q.contract,
        contract_id=q.contract_id,
        company_id=q.company_id,
        counterparty=q.counterparty,
        months_left=q.months_left,
        monthly_minimum_cents=q.monthly_minimum_cents,
        discounted_cents=q.discounted_cents,
        penalty_cents=q.penalty_cents,
        prepaid_cents=q.prepaid_cents,
        fee_cents=q.fee_cents,
        cash_cents=q.cash_cents,
        relationship=float(ct.score(state, q.counterparty, data.balance)),
        energy=data.balance.contracts.terminate_energy,
    )


@router.post(
    "/contracts/terminate",
    response_model=ContractActionOut,
    responses=ERRORS,
    operation_id="terminateContract",
)
def terminate_contract(
    save_id: str, body: TerminateIn, settings: SettingsDep, data: DataDep
) -> ContractActionOut:
    path = _path(settings, save_id)
    actor = _founder_id(_state(path))
    action = ct.TerminateContract(actor, body.contract, body.contract_id)  # type: ignore[arg-type]
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return ContractActionOut(energy=views.energy(state, data), unread_inbox=unread)
