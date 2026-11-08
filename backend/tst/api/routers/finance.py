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
from sqlalchemy import select

from tst.api import capital_views, finance_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _act, _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.capital import LoanIn, LoanPreviewOut, LoansOut, MacroOut, RepayIn
from tst.api.schemas.finance import (
    AcceptSheetIn,
    BoardOut,
    CapTableOut,
    FinanceActionOut,
    FinanceSummaryOut,
    GameOverOut,
    NomineeIn,
    RoundIn,
    RoundPreviewOut,
    RoundsOut,
    SafeHintOut,
    SafeIn,
    SafesOut,
    StatementsOut,
)
from tst.db import inbox, repository
from tst.db.events import written_text
from tst.db.models import MacroMonthRow
from tst.db.state_io import macro_from_row
from tst.sim.actions import (
    AcceptBridge,
    AcceptTermSheet,
    NameNominee,
    RaiseSafe,
    RepayLoan,
    StartRound,
    TakeLoan,
)
from tst.sim.errors import UnknownTermSheetError
from tst.sim.state import company_cash, group_members

router = APIRouter(prefix="/api/saves/{save_id}", tags=["finance"])

NEWS_LIMIT = 60  # finance inbox items read for the game over timeline (six months is fewer)


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
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        lines = repository.ledger_lines(session, state.player.id)
        # M16 (31.1): every company inside the group, at any depth, over its periods there
        members = group_members(state, state.player.id)
        books = {m.company_id: repository.ledger_lines(session, m.company_id) for m in members}
    return finance_views.statements_out(
        state, lines, period, data, [(m, books[m.company_id]) for m in members]
    )


@router.get(
    "/finance/summary",
    response_model=FinanceSummaryOut,
    responses=ERRORS,
    operation_id="getFinanceSummary",
)
def get_summary(save_id: str, settings: SettingsDep, data: DataDep) -> FinanceSummaryOut:
    """Cash, the projected net burn and runway ("profitable" when null), insolvency and the
    game state (ADR-0018)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    return finance_views.summary_out(state, cash, data)


@router.get(
    "/finance/captable", response_model=CapTableOut, responses=ERRORS, operation_id="getCapTable"
)
def get_captable(save_id: str, settings: SettingsDep, data: DataDep) -> CapTableOut:
    """Holders, classes, shares and percentages; every grant with vested and unvested."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        names = repository.person_names(session, [g.person_id for g in state.grants])
    return finance_views.captable_out(state, names, data)


@router.get("/finance/board", response_model=BoardOut, responses=ERRORS, operation_id="getBoard")
def get_board(save_id: str, settings: SettingsDep, data: DataDep) -> BoardOut:
    """Seats, each director's confidence and trend, and the last quarterly meeting (14.6)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        player = state.player.id
        meetings = inbox.list_inbox(session, player, kinds=["board_meeting"], limit=2)
        warnings = inbox.list_inbox(session, player, kinds=["board_warning"], limit=1)
        minutes = written_text(session, "minutes", meetings[0].turn) if meetings else None
    out = finance_views.board_out(state, data, meetings, warnings)
    if out.last_meeting is not None and minutes:
        out.last_meeting.minutes = minutes
    return out


@router.get(
    "/finance/game-over", response_model=GameOverOut, responses=ERRORS, operation_id="getGameOver"
)
def get_game_over(save_id: str, settings: SettingsDep, data: DataDep) -> GameOverOut:
    """How the game ended: the reason, the turn, the last numbers and the last six months'
    finance news (ADR-0018). Works on an active save too (game_state "active")."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        player = state.player.id
        cash = company_cash(repository.ledger_balances(session), player)
        snaps = repository.recent_snapshots(session, player, max(state.turn, 1))
        news = inbox.list_inbox(
            session, player, kinds=list(finance_views.FINANCE_TEMPLATES), limit=NEWS_LIMIT
        )
    return finance_views.game_over_out(state, cash, snaps, news, data)


# --- SAFEs -----------------------------------------------------------------------------------


@router.get("/finance/safes", response_model=SafesOut, responses=ERRORS, operation_id="listSafes")
def list_safes(save_id: str, settings: SettingsDep, data: DataDep) -> SafesOut:
    """Every SAFE and bridge; an open bridge offer shows today's amount (14.7)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    return finance_views.safes_out(state, cash, data)


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
    save_id: str,
    sheet_id: int,
    settings: SettingsDep,
    data: DataDep,
    body: AcceptSheetIn | None = None,
) -> FinanceActionOut:
    """The round closes at the next Continue; the other term sheets lapse. Where the round
    adds a common seat, `nominee_id` names the founder's nominee (default: the most senior
    employee; M4c)."""
    path = _path(settings, save_id)
    nominee = body.nominee_id if body is not None else None
    action = AcceptTermSheet(_founder_id(_state(path)), sheet_id, nominee)
    _, out = _act(path, data, action)
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


@router.post(
    "/finance/board/seats/{seat_id}/nominee",
    response_model=FinanceActionOut,
    responses=ERRORS,
    operation_id="nameNominee",
)
def name_nominee(
    save_id: str, seat_id: int, body: NomineeIn, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """Name an employee to an empty common seat (14.6, M4c; energy 2)."""
    path = _path(settings, save_id)
    _, out = _act(path, data, NameNominee(_founder_id(_state(path)), seat_id, body.person_id))
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


# --- Debt and macro (M10, formulas.md 20.3-20.4) ----------------------------------------------


@router.get("/finance/macro", response_model=MacroOut, responses=ERRORS, operation_id="getMacro")
def get_macro(save_id: str, settings: SettingsDep, data: DataDep) -> MacroOut:
    """The four macro indicators for the month the player is in and the 24 months before,
    and whether a downturn is under way (20.4). Never a month ahead."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        stored = {
            r.turn: macro_from_row(r)
            for r in session.scalars(select(MacroMonthRow).where(MacroMonthRow.turn <= state.turn))
        }
    return capital_views.macro_out(state, stored, data)


@router.get("/finance/loans", response_model=LoansOut, responses=ERRORS, operation_id="listLoans")
def list_loans(save_id: str, settings: SettingsDep, data: DataDep) -> LoansOut:
    """Every loan with its schedule and covenant headroom, and what each lender offers now."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.ledger_balances(session), state.player.id)
    return capital_views.loans_out(state, cash, data)


@router.post(
    "/finance/loans/preview",
    response_model=LoanPreviewOut,
    responses=ERRORS,
    operation_id="previewLoan",
)
def preview_loan(
    save_id: str, body: LoanIn, settings: SettingsDep, data: DataDep
) -> LoanPreviewOut:
    """The first month's payment and the warrants for this amount. Nothing is saved."""
    state = _state(_path(settings, save_id))
    return capital_views.loan_preview_out(state, body.instrument, body.amount_cents, data)


@router.post(
    "/finance/loans",
    response_model=FinanceActionOut,
    status_code=201,
    responses=ERRORS,
    operation_id="takeLoan",
)
def take_loan(save_id: str, body: LoanIn, settings: SettingsDep, data: DataDep) -> FinanceActionOut:
    """Sign venture debt or a bank loan at once (energy 10); the money is in the bank now."""
    path = _path(settings, save_id)
    action = TakeLoan(_founder_id(_state(path)), body.instrument, body.amount_cents)
    _, out = _act(path, data, action)
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)


@router.post(
    "/finance/loans/{loan_id}/repay",
    response_model=FinanceActionOut,
    responses=ERRORS,
    operation_id="repayLoan",
)
def repay_loan(
    save_id: str, loan_id: int, body: RepayIn, settings: SettingsDep, data: DataDep
) -> FinanceActionOut:
    """Repay early, in part or in full, with no fee (energy 5)."""
    path = _path(settings, save_id)
    action = RepayLoan(_founder_id(_state(path)), loan_id, body.amount_cents)
    _, out = _act(path, data, action)
    return FinanceActionOut(energy=out.energy, unread_inbox=out.unread_inbox)
