"""Save-scoped finance routes (M4a): statements, the cap table, SAFEs and their hint band,
priced rounds and term sheets with a dilution preview, the board, the runway and the game
state, and the finance actions.

Actions run through `repository.run_action` with the founder as actor (ADR-0014); once the
game has ended they are refused with 409 (`game_over`), and every read still works.
Responses never carry V_base, a firm's bias or noise, or the SAFE probability (14.9).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from tst.api import finance_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _act, _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.finance import (
    BoardOut,
    CapTableOut,
    FinanceActionOut,
    FinanceSummaryOut,
    RoundIn,
    RoundPreviewOut,
    RoundsOut,
    SafeHintOut,
    SafeIn,
    SafesOut,
    StatementsOut,
)
from tst.db import repository
from tst.sim.actions import AcceptBridge, AcceptTermSheet, RaiseSafe, StartRound
from tst.sim.errors import UnknownTermSheetError
from tst.sim.state import company_cash

router = APIRouter(prefix="/api/saves/{save_id}", tags=["finance"])


@router.get(
    "/finance/statements",
    response_model=StatementsOut,
    responses=ERRORS,
    operation_id="getStatements",
)
def get_statements(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    period: Annotated[Literal["month", "quarter", "year"], Query()] = "month",
) -> StatementsOut:
    """P&L, balance sheet and cash flow for every closed month, quarter or year (14.1)."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
        lines = repository.ledger_lines(session, state.player.id)
    return finance_views.statements_out(state, lines, period, data)


@router.get(
    "/finance/summary",
    response_model=FinanceSummaryOut,
    responses=ERRORS,
    operation_id="getFinanceSummary",
)
def get_summary(save_id: str, settings: SettingsDep, data: DataDep) -> FinanceSummaryOut:
    """Cash, the projected net burn and runway ("profitable" when null), insolvency and the
    game state (ADR-0018)."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    return finance_views.summary_out(state, cash, data)


@router.get(
    "/finance/captable", response_model=CapTableOut, responses=ERRORS, operation_id="getCapTable"
)
def get_captable(save_id: str, settings: SettingsDep, data: DataDep) -> CapTableOut:
    """Holders, classes, shares and percentages; every grant with vested and unvested."""
    with repository.open_session(_path(settings, save_id)) as session:
        state = repository.load_state(session)
        names = repository.person_names(session, [g.person_id for g in state.grants])
    return finance_views.captable_out(state, names, data)


@router.get("/finance/board", response_model=BoardOut, responses=ERRORS, operation_id="getBoard")
def get_board(save_id: str, settings: SettingsDep, data: DataDep) -> BoardOut:
    return finance_views.board_out(_state(_path(settings, save_id)), data)


# --- SAFEs -----------------------------------------------------------------------------------


@router.get("/finance/safes", response_model=SafesOut, responses=ERRORS, operation_id="listSafes")
def list_safes(save_id: str, settings: SettingsDep, data: DataDep) -> SafesOut:
    return finance_views.safes_out(_state(_path(settings, save_id)), data)


@router.post(
    "/finance/safes/hint",
    response_model=SafeHintOut,
    responses=ERRORS,
    operation_id="previewSafe",
)
def preview_safe(save_id: str, body: SafeIn, settings: SettingsDep, data: DataDep) -> SafeHintOut:
    """The hint band (likely, uncertain, unlikely) and the rule checks. Nothing is saved."""
    state = _state(_path(settings, save_id))
    return finance_views.safe_hint_out(state, body.amount_cents, body.cap_cents, data)


@router.post(
    "/finance/safes",
    response_model=FinanceActionOut,
    status_code=201,
    responses=ERRORS,
    operation_id="raiseSafe",
)
def raise_safe(
    save_id: str, body: SafeIn, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """Investors answer at the next Continue, all or nothing (14.4)."""
    path = _path(settings, save_id)
    action = RaiseSafe(_founder_id(_state(path)), body.amount_cents, body.cap_cents)
    _, out = _act(path, data, action)
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


@router.post(
    "/finance/bridges/{safe_id}/accept",
    response_model=FinanceActionOut,
    responses=ERRORS,
    operation_id="acceptBridge",
)
def accept_bridge(
    save_id: str, safe_id: int, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """The bridge's money arrives at this month's Continue (14.7)."""
    path = _path(settings, save_id)
    _, out = _act(path, data, AcceptBridge(_founder_id(_state(path)), safe_id))
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


# --- Priced rounds ---------------------------------------------------------------------------


@router.get(
    "/finance/rounds", response_model=RoundsOut, responses=ERRORS, operation_id="listRounds"
)
def list_rounds(save_id: str, settings: SettingsDep, data: DataDep) -> RoundsOut:
    """Every round with its term sheets, and whether the next series is allowed (14.5)."""
    return finance_views.rounds_out(_state(_path(settings, save_id)), data)


@router.post(
    "/finance/rounds",
    response_model=FinanceActionOut,
    status_code=201,
    responses=ERRORS,
    operation_id="startRound",
)
def start_round(
    save_id: str, body: RoundIn, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """Term sheets arrive at the next Continue."""
    path = _path(settings, save_id)
    action = StartRound(_founder_id(_state(path)), body.series, body.target_cents)
    _, out = _act(path, data, action)
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


@router.get(
    "/finance/term-sheets/{sheet_id}/preview",
    response_model=RoundPreviewOut,
    responses=ERRORS,
    operation_id="previewTermSheet",
)
def preview_term_sheet(
    save_id: str, sheet_id: int, settings: SettingsDep, data: DataDep
) -> RoundPreviewOut:
    """Every holder before and after accepting: the pool top-up, SAFE conversion and the
    new preferred, computed with the closing function. Nothing is saved."""
    state = _state(_path(settings, save_id))
    sheet = state.term_sheet(sheet_id)
    rnd = state.funding_round(sheet.round_id) if sheet is not None else None
    if sheet is None or rnd is None or rnd.company_id != state.player.id:
        raise UnknownTermSheetError(f"no term sheet {sheet_id}")
    return finance_views.round_preview_out(state, sheet, data)


@router.post(
    "/finance/term-sheets/{sheet_id}/accept",
    response_model=FinanceActionOut,
    responses=ERRORS,
    operation_id="acceptTermSheet",
)
def accept_term_sheet(
    save_id: str, sheet_id: int, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """The round closes at the next Continue; the other term sheets lapse."""
    path = _path(settings, save_id)
    _, out = _act(path, data, AcceptTermSheet(_founder_id(_state(path)), sheet_id))
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)
