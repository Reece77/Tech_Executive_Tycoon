"""Save-scoped routes for the group (M16, formulas.md 31): the Group screen and the founder's
actions as Chair. Actions run through `repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import group_story_views, group_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.group import (
    CapitalHistoryOut,
    GroupActionOut,
    GroupOut,
    MandateIn,
    PitchAnswerIn,
    SpinOffIn,
    StakeIn,
    SubsidiaryUpdatesOut,
    TransferPriceIn,
    VentureIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.group.actions import (
    AnswerGroupPitch,
    BuyOutMinorities,
    BuyStake,
    CarveOut,
    FormHolding,
    GroupAction,
    ReplaceSubsidiaryCeo,
    SellStake,
    SetMandate,
    SetTransferPrice,
    SpinOff,
    VentureInvest,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["group"])


def _group(path: Path, data: LoadedData) -> GroupOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return group_views.group_out(state, balances, data)


def _act(path: Path, data: LoadedData, action: GroupAction) -> GroupActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return GroupActionOut(
        group=_group(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/group", response_model=GroupOut, responses=ERRORS, operation_id="getGroup")
def get_group(save_id: str, settings: SettingsDep, data: DataDep) -> GroupOut:
    """The entity tree with stakes, treatments and each company's numbers; the holding
    company's gate before it is formed (31.2, 31.10)."""
    return _group(_path(settings, save_id), data)


@router.get(
    "/group/history",
    response_model=CapitalHistoryOut,
    responses=ERRORS,
    operation_id="getCapitalHistory",
)
def get_capital_history(save_id: str, settings: SettingsDep, data: DataDep) -> CapitalHistoryOut:
    """Every stake sale, carve-out, spin-off and buyout: date, proceeds, ownership before and
    after, NCI and the value created (31.5; M23c). Read from the posted entries."""
    from sqlalchemy import select

    from tst.db.models import LedgerEntryRow

    memos = [prefix for prefix, _ in group_story_views.MEMOS]
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
        found = session.scalars(
            select(LedgerEntryRow)
            .order_by(LedgerEntryRow.id)
            .where(
                LedgerEntryRow.memo.startswith(memos[0])
                | LedgerEntryRow.memo.startswith(memos[1])
                | LedgerEntryRow.memo.startswith(memos[2])
                | LedgerEntryRow.memo.startswith(memos[3])
            )
        ).all()
        rows = [
            (
                e.turn,
                e.company_id,
                e.memo,
                {line.account_code: line.amount_cents for line in e.lines},
            )
            for e in found
        ]
    return CapitalHistoryOut(actions=group_story_views.capital_history(state, rows, balances, data))


@router.get(
    "/group/updates",
    response_model=SubsidiaryUpdatesOut,
    responses=ERRORS,
    operation_id="getSubsidiaryUpdates",
)
def get_subsidiary_updates(
    save_id: str, settings: SettingsDep, data: DataDep
) -> SubsidiaryUpdatesOut:
    """Each subsidiary CEO's quarterly update, ending with a question for the Chair (M23c)."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        balances = repository.ledger_balances(session)
    return SubsidiaryUpdatesOut(updates=group_story_views.subsidiary_updates(state, balances, data))


@router.post(
    "/group/form", response_model=GroupActionOut, responses=ERRORS, operation_id="formHolding"
)
def form_holding(save_id: str, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Form the holding company: it takes the listing, the cap table and the board; the
    company and its brands become its subsidiaries (31.2)."""
    path = _path(settings, save_id)
    return _act(path, data, FormHolding(_founder_id(_state(path))))


@router.post(
    "/group/mandate", response_model=GroupActionOut, responses=ERRORS, operation_id="setMandate"
)
def set_mandate(
    save_id: str, body: MandateIn, settings: SettingsDep, data: DataDep
) -> GroupActionOut:
    """Set a subsidiary's mandate: grow, margin or return cash (31.4)."""
    path = _path(settings, save_id)
    action = SetMandate(
        _founder_id(_state(path)),
        body.company_id,
        body.mandate,  # type: ignore[arg-type]
        body.capex_limit_cents,
        tuple(body.categories),
        tuple(body.regions),
    )
    return _act(path, data, action)


@router.post(
    "/group/companies/{company_id}/replace-ceo",
    response_model=GroupActionOut,
    responses=ERRORS,
    operation_id="replaceSubsidiaryCeo",
)
def replace_ceo(
    save_id: str, company_id: int, settings: SettingsDep, data: DataDep
) -> GroupActionOut:
    """Accept the board's proposal for a new CEO (31.4)."""
    path = _path(settings, save_id)
    return _act(path, data, ReplaceSubsidiaryCeo(_founder_id(_state(path)), company_id))


@router.post(
    "/group/pitches/{pitch_id}",
    response_model=GroupActionOut,
    responses=ERRORS,
    operation_id="answerGroupPitch",
)
def answer_pitch(
    save_id: str, pitch_id: int, body: PitchAnswerIn, settings: SettingsDep, data: DataDep
) -> GroupActionOut:
    """Approve or decline a subsidiary CEO's request for capital (31.4)."""
    path = _path(settings, save_id)
    return _act(path, data, AnswerGroupPitch(_founder_id(_state(path)), pitch_id, body.approve))


def _founder(path: Path) -> int:
    return _founder_id(_state(path))


@router.post(
    "/group/sell-stake", response_model=GroupActionOut, responses=ERRORS, operation_id="sellStake"
)
def sell_stake(save_id: str, body: StakeIn, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Sell part of a subsidiary to investors; the group keeps control (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, SellStake(_founder(path), body.company_id, body.stake_bp))


@router.post(
    "/group/companies/{company_id}/buy-out",
    response_model=GroupActionOut,
    responses=ERRORS,
    operation_id="buyOutMinorities",
)
def buy_out(save_id: str, company_id: int, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Buy out a subsidiary's minorities at the premium (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, BuyOutMinorities(_founder(path), company_id))


@router.post(
    "/group/carve-out", response_model=GroupActionOut, responses=ERRORS, operation_id="carveOut"
)
def carve_out(save_id: str, body: StakeIn, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """List 10-40% of a subsidiary; the group keeps control (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, CarveOut(_founder(path), body.company_id, body.stake_bp))


@router.post(
    "/group/spin-off", response_model=GroupActionOut, responses=ERRORS, operation_id="spinOff"
)
def spin_off(save_id: str, body: SpinOffIn, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Give a subsidiary's shares to the holding company's shareholders (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, SpinOff(_founder(path), body.company_id, body.keep_bp))


@router.post(
    "/group/stake", response_model=GroupActionOut, responses=ERRORS, operation_id="buyStake"
)
def buy_stake(save_id: str, body: StakeIn, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Buy a listed rival's shares on the market up to `stake_bp` (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, BuyStake(_founder(path), body.company_id, body.stake_bp))


@router.post(
    "/group/venture", response_model=GroupActionOut, responses=ERRORS, operation_id="ventureInvest"
)
def venture(save_id: str, body: VentureIn, settings: SettingsDep, data: DataDep) -> GroupActionOut:
    """Invest in a startup's round for 5-25% (31.5)."""
    path = _path(settings, save_id)
    return _act(path, data, VentureInvest(_founder(path), body.company_id, body.cents))


@router.post(
    "/group/transfer-price",
    response_model=GroupActionOut,
    responses=ERRORS,
    operation_id="setTransferPrice",
)
def transfer_price(
    save_id: str, body: TransferPriceIn, settings: SettingsDep, data: DataDep
) -> GroupActionOut:
    """Set the price one group company supplies another at: cost, cost plus or market (31.6)."""
    path = _path(settings, save_id)
    action = SetTransferPrice(
        _founder(path), body.seller_id, body.buyer_id, body.good, body.price_kind, body.margin
    )
    return _act(path, data, action)
