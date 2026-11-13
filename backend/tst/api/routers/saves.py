"""Save-scoped routes. Each request opens the save file it names (ADR-0009)."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Response, status

from tst.api import breakdowns, finance_views, interruptions, org_views, scaleup_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.schemas.common import ErrorOut, OverviewBreakdownsOut
from tst.api.schemas.saves import (
    BackupOut,
    CostLineOut,
    CreateSaveIn,
    OverviewOut,
    SaveNameIn,
    SaveOut,
    SnapshotPointOut,
    StageReachedOut,
    TeamOut,
)
from tst.db import inbox, repository
from tst.db import saves as saves_db
from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.errors import InvalidModeError
from tst.sim.finance.options import pool_left_bp
from tst.sim.geo.offices import employee_office_cents
from tst.sim.hiring.formulas import benefits_cents, monthly_salary_cents
from tst.sim.hiring.phases import employment_monthly_cost_cents, monthly_costs
from tst.sim.modes.world import ModeSpec
from tst.sim.org.rules import is_remote
from tst.sim.products.phases import projected_revenue
from tst.sim.setup import DEFAULT_FOUNDER
from tst.sim.state import GameState, company_cash, stage_since

router = APIRouter(prefix="/api/saves", tags=["saves"])

HISTORY_TURNS = 12  # Overview chart window
LATEST_INBOX = 5  # newest inbox items on the Overview
SEED_BITS = 63  # fits SQLite's signed 64-bit INTEGER

ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorOut},
    404: {"model": ErrorOut},
    409: {"model": ErrorOut},
    422: {"model": ErrorOut},
}


def _save_out(save: saves_db.SaveFile) -> SaveOut:
    return SaveOut(
        save_id=save.slug,
        display_name=save.display_name,
        company_name=save.company_name,
        scenario_id=save.scenario_id,
        difficulty=save.difficulty,
        turn=save.current_turn,
        date_label=format_turn(save.current_turn),
        game_state=save.game_state,
        last_played=save.last_played,
        size_bytes=save.size_bytes,
        ironman=save.difficulty == saves_db.IRONMAN,
        busy=save.busy,
        mod_name=save.mod_name,
        mode=save.mode,
        score=save.score,
    )


def _overview(save_id: str, settings: SettingsDep, data: DataDep) -> OverviewOut:
    path = repository.existing_save_path(settings.resolved_save_dir(), save_id)
    with repository.read_session(path) as session:
        ov = repository.player_overview(session, history=HISTORY_TURNS, data=data)
        state = repository.read_state(session)
        player = state.player
        latest = ov.history[-1][1] if ov.history else None
        costs = repository.costs_for_turn(session, player.id, state.turn - 1)
        paid = repository.expenses_by_memo(session, player.id, state.turn)
        unread = inbox.unread_count(session, player.id)
        balances = repository.current_balances(session, state.turn)
        newest = inbox.list_inbox(session, player.id, limit=LATEST_INBOX, archived=False)
    staff = state.staff(player.id)
    employees = [e for e in staff if not state.person(e.person_id).is_founder]
    morale = [m for e in employees if (m := state.person_state(e.person_id).morale) is not None]
    projected = [
        CostLineOut(account=account, label=label, amount_cents=amount)
        for label, account, amount in monthly_costs(state, player.id, data.balance, data.game_data)
        if amount
    ]
    month_paid = [
        CostLineOut(account=code, label=label, amount_cents=amount) for label, code, amount in paid
    ]
    runway = ov.runway_months  # at this month's projected phase-6 costs (M1c decision)
    since = stage_since(player)
    runway_warn = data.balance.morale.runway_warn_months
    month_total = sum(c.amount_cents for c in projected) + sum(c.amount_cents for c in month_paid)
    month_revenue = projected_revenue(state, player.id)
    from tst.api.founder_views import stress_out
    from tst.api.modes_views import score_out

    return OverviewOut(
        score=score_out(state, player.id, balances, data),  # M15b (30.1)
        stress=stress_out(state, data),  # M24 (32.1)
        deals_due=sum(
            1
            for d in state.deals
            if d.acquirer_id == player.id and d.status in ("accepted", "review", "blocked")
        ),
        active_effects=views.active_effects(state),
        save_id=save_id,
        company_name=ov.company_name,
        turn=ov.turn,
        date_label=ov.date_label,
        cash_cents=ov.cash_cents,
        monthly_burn_cents=ov.monthly_burn_cents,
        runway_months=runway,
        history=[
            SnapshotPointOut(
                turn=turn,
                date_label=format_turn(turn),
                cash_cents=snap.cash_cents,
                monthly_burn_cents=snap.monthly_burn_cents,
                payroll_cents=snap.payroll_cents,
                headcount=snap.headcount,
                avg_morale=snap.avg_morale,
                mrr_cents=snap.mrr_cents,
                arr_cents=snap.arr_cents,
                founder_bp=snap.founder_bp,
                board_confidence=snap.board_confidence,
            )
            for turn, snap in ov.history
        ],
        stage=player.stage,
        stage_label=views.STAGE_LABELS.get(player.stage, f"Stage {player.stage}"),
        runway_low=runway is not None and runway < runway_warn,
        mission=list(player.mission),
        headcount=len(state.staff(player.id)),
        payroll_cents=latest.payroll_cents if latest else 0,
        avg_morale=latest.avg_morale if latest else None,
        energy=views.energy(state, data),
        unread_inbox=unread,
        costs_last_month=[
            CostLineOut(account=code, label=name, amount_cents=amount)
            for code, name, amount in costs
        ],
        latest_inbox=[views.inbox_item(m) for m in newest],
        team=TeamOut(
            headcount=len(staff),
            on_notice=sum(1 for e in staff if e.status == "notice"),
            people_cost_cents=sum(
                employment_monthly_cost_cents(
                    e,
                    data.balance,
                    remote=is_remote(state, e),
                    office_cents=employee_office_cents(state, e, data.balance, data.game_data),
                )
                for e in staff
            ),
            payroll_cents=sum(
                (s := monthly_salary_cents(e.salary_cents))
                + benefits_cents(s, data.balance.payroll)
                for e in staff
            ),
            avg_morale=sum(morale) / len(morale) if morale else None,
        ),
        month_costs=projected,
        month_paid=month_paid,
        month_total_cents=month_total,
        month_net_burn_cents=max(month_total - month_revenue, 0),
        option_pool_left_bp=pool_left_bp(state, player.id),
        network_bonus_candidates=network_bonus(state, player.id, data),
        org=org_views.org_tile(state, player.id, data),
        support=scaleup_views.support_tile(state, data),
        mrr_cents=latest.mrr_cents if latest else 0,
        arr_cents=latest.arr_cents if latest else 0,
        month_revenue_cents=month_revenue,
        game_state=state.save_meta.game_state,
        ended_turn=state.save_meta.ended_turn,
        stage_since_turn=since,
        stage_since_label=format_turn(since) if since is not None else None,
        stage_history=[
            StageReachedOut(
                stage=stage,
                stage_label=views.STAGE_LABELS.get(stage, f"Stage {stage}"),
                turn=turn,
                date_label=format_turn(turn),
            )
            for stage, turn in player.stage_history
        ],
        funding=finance_views.funding_tile(state, data),
    )


def network_bonus(state: GameState, company_id: int, data: DataDep) -> int:
    """Extra candidates a founder-opened network search brings (formulas.md 7)."""
    founder = state.founder_of(company_id)
    channel = data.balance.hiring.channel["network"]
    sociable = founder is not None and (
        founder.personality["sociability"] >= channel.sociability_threshold
    )
    return channel.sociability_bonus if sociable else 0


@router.get("", response_model=list[SaveOut], operation_id="listSaves")
def list_saves(settings: SettingsDep) -> list[SaveOut]:
    """Every save, most recently played first (M7b: the Saves screen)."""
    return [_save_out(s) for s in saves_db.list_files(settings.resolved_save_dir())]


@router.post(
    "",
    response_model=SaveOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="createSave",
)
def create_save(body: CreateSaveIn, settings: SettingsDep, data: DataDep) -> SaveOut:
    # The sim never generates seeds; the API does when the player leaves it blank.
    seed = body.seed if body.seed is not None else secrets.randbits(SEED_BITS)
    if body.mod:  # M25: the base files with the mod merged in, validated like them
        from tst.mods.store import read_mod, validate

        data = validate(settings.data_dir, read_mod(settings.resolved_save_dir(), body.mod))
    path = repository.create_save(
        body.name,
        seed,
        body.scenario,
        company_name=body.company_name,
        difficulty=body.difficulty,
        founder=body.founder.to_spec() if body.founder else DEFAULT_FOUNDER,
        mission=None if body.mission is None else tuple(body.mission),
        hq_city=body.hq_city,
        data=data,
        save_dir=settings.resolved_save_dir(),
        mode=_mode_spec(body, data),
    )
    return _save_out(saves_db.describe(path))


def _mode_spec(body: CreateSaveIn, data: LoadedData) -> ModeSpec | None:
    """A Sandbox or historical scenario start (M15b, 30.2-30.3), else None (a campaign)."""
    from tst.sim.modes.scenarios import scenario_spec

    if body.sandbox is not None and body.historical is not None:
        raise InvalidModeError("choose a Sandbox or a scenario, not both")
    if body.historical is not None:
        return scenario_spec(body.historical, data.game_data)
    if body.sandbox is None:
        return None
    sb = body.sandbox
    cash = None if sb.cash_dollars is None else sb.cash_dollars * 100
    return ModeSpec("sandbox", sb.start_year, cash, sb.rivals, sb.eras)


def _existing(settings: SettingsDep, save_id: str) -> Path:
    return repository.existing_save_path(settings.resolved_save_dir(), save_id)


@router.get("/{save_id}", response_model=SaveOut, responses=ERRORS, operation_id="getSave")
def get_save(save_id: str, settings: SettingsDep) -> SaveOut:
    return _save_out(saves_db.describe(_existing(settings, save_id)))


@router.post(
    "/{save_id}/rename", response_model=SaveOut, responses=ERRORS, operation_id="renameSave"
)
def rename_save(save_id: str, body: SaveNameIn, settings: SettingsDep) -> SaveOut:
    """Change the save's display name; the company name and the save's id stay (M7b)."""
    return _save_out(saves_db.rename(_existing(settings, save_id), body.name))


@router.post(
    "/{save_id}/duplicate",
    response_model=SaveOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="duplicateSave",
)
def duplicate_save(save_id: str, body: SaveNameIn, settings: SettingsDep) -> SaveOut:
    """Save as: a copy under a new name and id. 409 for an Ironman or busy save."""
    return _save_out(saves_db.duplicate(_existing(settings, save_id), body.name))


@router.delete(
    "/{save_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
    operation_id="deleteSave",
)
def delete_save(save_id: str, settings: SettingsDep) -> Response:
    """Delete the save and its backups. 409 while it is busy."""
    saves_db.delete(_existing(settings, save_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{save_id}/backups",
    response_model=list[BackupOut],
    responses=ERRORS,
    operation_id="listBackups",
)
def list_backups(save_id: str, settings: SettingsDep) -> list[BackupOut]:
    """Periodic and pre-upgrade backups, newest first."""
    return [
        BackupOut(
            backup_id=b.backup_id,
            kind=b.kind,
            turn=b.turn,
            date_label=format_turn(b.turn),
            created=b.created,
            size_bytes=b.size_bytes,
        )
        for b in saves_db.backups(_existing(settings, save_id))
    ]


@router.post(
    "/{save_id}/backups",
    response_model=BackupOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="backUpSave",
)
def back_up_save(save_id: str, settings: SettingsDep) -> BackupOut:
    """Back up now (M29): a copy kept with the save's backups. 409 for an Ironman or busy
    save."""
    b = saves_db.back_up(_existing(settings, save_id))
    return BackupOut(
        backup_id=b.backup_id,
        kind=b.kind,
        turn=b.turn,
        date_label=format_turn(b.turn),
        created=b.created,
        size_bytes=b.size_bytes,
    )


@router.post(
    "/{save_id}/backups/{backup_id}/restore",
    response_model=SaveOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    operation_id="restoreBackup",
)
def restore_backup(save_id: str, backup_id: str, settings: SettingsDep) -> SaveOut:
    """Restore a backup as a new save, "Company (restored, Mar 2013)"; the original is
    never changed. 409 for an Ironman or busy save."""
    return _save_out(saves_db.restore(_existing(settings, save_id), backup_id))


@router.get(
    "/{save_id}/overview",
    response_model=OverviewOut,
    responses=ERRORS,
    operation_id="getOverview",
)
def get_overview(save_id: str, settings: SettingsDep, data: DataDep) -> OverviewOut:
    return _overview(save_id, settings, data)


@router.post(
    "/{save_id}/advance",
    response_model=OverviewOut,
    responses=ERRORS,
    operation_id="advanceTurn",
)
def advance(save_id: str, settings: SettingsDep, data: DataDep) -> OverviewOut:
    path = repository.existing_save_path(settings.resolved_save_dir(), save_id)
    # M29 (42.4): with Interruptions at critical only, open major events take their first
    # choice first, as on a holiday; otherwise they block (23.1).
    interruptions.answer_waived(path, data, interruptions.stop_on(settings.resolved_save_dir()))
    repository.run_turn(path, data, block_major=True)  # the player at the controls (23.1)
    return _overview(save_id, settings, data)


@router.get(
    "/{save_id}/overview/breakdowns",
    response_model=OverviewBreakdownsOut,
    responses=ERRORS,
    operation_id="getOverviewBreakdowns",
)
def get_overview_breakdowns(
    save_id: str, settings: SettingsDep, data: DataDep
) -> OverviewBreakdownsOut:
    """What drives the top bar's and Overview's numbers (M7b tooltips): fetched when a
    tooltip first opens, so Continue does not pay for them."""
    with repository.read_session(_existing(settings, save_id)) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
        return OverviewBreakdownsOut(
            cash=breakdowns.cash_change(session, state),
            runway=breakdowns.runway(state, cash, data),
            mrr=breakdowns.revenue_by_product(session, state, annual=False),
            arr=breakdowns.revenue_by_product(session, state, annual=True),
            burn=breakdowns.burn(session, state),
            headcount=breakdowns.headcount_by_unit(state),
            avg_morale=breakdowns.average_morale(state, data, cash),
        )
