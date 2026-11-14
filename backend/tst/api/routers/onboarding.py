"""Onboarding and navigation (docs/formulas.md 42; M29): unlocks, Getting started, What next,
the command palette's index, and their settings. Read-only except opening an opt-in system
early, dismissing the checklist and the settings, none of which changes the game."""

from __future__ import annotations

from fastapi import APIRouter, Path

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.onboarding import (
    GettingStartedOut,
    OnboardingSettings,
    PaletteEntryOut,
    PaletteOut,
    StepOut,
    SystemOut,
    UnlocksOut,
    WhatNextItemOut,
    WhatNextOut,
)
from tst.db import repository
from tst.db import unlocks as unlocks_db
from tst.loader import LoadedData
from tst.sim import unlocks
from tst.sim.calendar import format_turn
from tst.sim.coo import coo_of
from tst.sim.errors import NotFoundError
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.state import GameState, company_cash
from tst.sim.whatnext import what_next
from tst.ui_settings import Onboarding, dismiss_checklist, load_ui, save_onboarding

router = APIRouter(prefix="/api/saves/{save_id}", tags=["onboarding"])
settings_router = APIRouter(prefix="/api/settings/ui", tags=["settings"])


class UnknownSystemError(NotFoundError):
    code = "unknown_system"


def _unlocks(
    state: GameState, seen: dict[str, unlocks_db.Announced], data: LoadedData, show_all: bool
) -> UnlocksOut:
    now = unlocks.conditions(state, data.balance, data.game_data)
    systems = []
    for s in unlocks.SYSTEMS:
        a = seen.get(s.key)
        reason = now.get(s.key) or ("announced" if a is not None else None)
        systems.append(
            SystemOut(
                key=s.key,
                label=s.label,
                group=s.group,
                unlocked=show_all or reason is not None,
                reason=None if reason == "always" else reason,
                since_label=format_turn(a.turn) if a is not None else None,
                item_id=a.item_id if a is not None else None,
                opt_in=s.key in unlocks.OPT_IN,
            )
        )
    fresh = [k for k, a in seen.items() if a.turn == state.turn]
    return UnlocksOut(show_everything=show_all, systems=systems, fresh=fresh)


@router.get("/unlocks", response_model=UnlocksOut, responses=ERRORS, operation_id="getUnlocks")
def get_unlocks(save_id: str, settings: SettingsDep, data: DataDep) -> UnlocksOut:
    """Which screens the side bar shows and why (42.1)."""
    show_all = load_ui(settings.resolved_save_dir()).onboarding.show_everything
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        return _unlocks(state, unlocks_db.announced(session, state.player.id), data, show_all)


@router.post(
    "/unlocks/{key}/open", response_model=UnlocksOut, responses=ERRORS, operation_id="openSystem"
)
def open_system(
    save_id: str,
    settings: SettingsDep,
    data: DataDep,
    key: str = Path(pattern=r"^[a-z_]{1,32}$"),
) -> UnlocksOut:
    """Open an opt-in system before its condition holds ("Explore for minerals" from Markets,
    42.1): writes its unlock item once. No game effect."""
    if key not in unlocks.OPT_IN:
        raise UnknownSystemError(f"{key!r} cannot be opened early")
    show_all = load_ui(settings.resolved_save_dir()).onboarding.show_everything
    path = _path(settings, save_id)
    with repository.write_session(path) as session:
        state = repository.load_state(session)
        unlocks_db.open_early(session, state, key)
        session.flush()
        return _unlocks(state, unlocks_db.announced(session, state.player.id), data, show_all)


def _speaker(state: GameState) -> str:
    pid = coo_of(state)
    if pid is None:
        return "Your notes"
    p = state.person(pid)
    return f"{p.first_name} {p.last_name}, chief of staff"


@router.get(
    "/getting-started",
    response_model=GettingStartedOut,
    responses=ERRORS,
    operation_id="getGettingStarted",
)
def get_getting_started(save_id: str, settings: SettingsDep, data: DataDep) -> GettingStartedOut:
    """The first year's checklist, ticked from state alone (42.2)."""
    ob = load_ui(settings.resolved_save_dir()).onboarding
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    steps = unlocks.getting_started(state, data.balance, data.game_data)
    months_left = max(0, unlocks.FIRST_YEAR_MONTHS - (state.turn - state.player.founded_turn))
    visible = (
        ob.guided_first_year
        and save_id not in ob.dismissed_checklists
        and unlocks.first_year(state)
        and state.save_meta.game_state == "active"
    )
    return GettingStartedOut(
        visible=visible,
        months_left=months_left,
        speaker=_speaker(state),
        steps=[
            StepOut(key=s.key, label=s.label, note=s.note, screen=s.screen, done=s.done)
            for s in steps
        ],
    )


@router.post(
    "/getting-started/dismiss",
    response_model=GettingStartedOut,
    responses=ERRORS,
    operation_id="dismissGettingStarted",
)
def dismiss_getting_started(
    save_id: str, settings: SettingsDep, data: DataDep
) -> GettingStartedOut:
    _path(settings, save_id)  # 404 for an unknown save
    dismiss_checklist(settings.resolved_save_dir(), save_id)
    return get_getting_started(save_id, settings, data)


@router.get("/what-next", response_model=WhatNextOut, responses=ERRORS, operation_id="getWhatNext")
def get_what_next(save_id: str, settings: SettingsDep, data: DataDep) -> WhatNextOut:
    """Up to five things to do now (42.3). Read-only, no energy."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
        cash = company_cash(repository.current_balances(session, state.turn), state.player.id)
        seen = unlocks_db.announced(session, state.player.id)
    fresh = [unlocks.BY_KEY[k] for k, a in seen.items() if a.turn == state.turn]
    items = what_next(state, cash, data.balance, data.game_data, fresh)
    return WhatNextOut(
        items=[
            WhatNextItemOut(
                key=i.key,
                text=i.text,
                link_kind=i.link_kind,
                link_id=i.link_id,
                link_key=i.link_key,
            )
            for i in items
        ]
    )


@router.get("/palette", response_model=PaletteOut, responses=ERRORS, operation_id="getPalette")
def get_palette(save_id: str, settings: SettingsDep, data: DataDep) -> PaletteOut:
    """Everything the command palette jumps to by name (42.4): the player's people, the
    group's products, facilities and mines, and rivals."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    return PaletteOut(entries=palette(state, data))


def palette(state: GameState, data: LoadedData) -> list[PaletteEntryOut]:
    d, b = data.game_data, data.balance
    ids = unlocks.group_ids(state)
    out: list[PaletteEntryOut] = []
    roles = {r.key: r.label for r in d.roles}
    for e in state.staff(state.player.id):
        if e.status not in ("active", "notice"):
            continue
        p = state.person(e.person_id)
        out.append(
            PaletteEntryOut(
                kind="person",
                id=p.id,
                label=f"{p.first_name} {p.last_name}",
                detail="Founder" if p.is_founder else roles.get(e.role, e.role),
                path=f"people/{p.id}",
            )
        )
    for prod in state.products:
        if prod.company_id in ids:
            out.append(
                PaletteEntryOut(
                    kind="product",
                    id=prod.id,
                    label=prod.name,
                    detail=d.category(prod.category).label,
                    path=f"products/{prod.id}",
                )
            )
    fabs = {f.facility_id for f in state.fabs}
    refineries = {r.facility_id for r in state.refineries}
    for f in state.facilities:
        if f.company_id not in ids:
            continue
        if f.id in fabs:
            where = "products/fabs"
        elif f.id in refineries:
            where = "products/refineries"
        elif f.kind.startswith("assembly"):
            where = "products/hardware"
        else:
            where = "products/infrastructure"
        out.append(
            PaletteEntryOut(
                kind="facility",
                id=f.id,
                label=facility_name(f, b, d),
                detail=d.region(f.region).label,
                path=where,
            )
        )
    for m in state.mines:
        if m.company_id in ids:
            out.append(
                PaletteEntryOut(
                    kind="facility",
                    id=m.id,
                    label=f"{m.commodity.replace('_', ' ').capitalize()} mine",
                    detail=d.region(m.region).label,
                    path=f"products/mines?mine={m.id}",
                )
            )
    for c in state.companies:
        if c.is_rival and c.alive and c.id not in ids:
            out.append(
                PaletteEntryOut(
                    kind="rival", id=c.id, label=c.name, detail="Rival", path=f"competitors/{c.id}"
                )
            )
    return out


@settings_router.get(
    "/onboarding", response_model=OnboardingSettings, operation_id="getOnboardingSettings"
)
def get_onboarding_settings(settings: SettingsDep) -> OnboardingSettings:
    """Show everything, Getting started and Interruptions (42.1, 42.2, 42.4), for every save."""
    ob = load_ui(settings.resolved_save_dir()).onboarding
    return OnboardingSettings(
        show_everything=ob.show_everything,
        guided_first_year=ob.guided_first_year,
        stop_on=ob.stop_on,
        stop_for_approvals=ob.stop_for_approvals,
    )


@settings_router.put(
    "/onboarding", response_model=OnboardingSettings, operation_id="updateOnboardingSettings"
)
def update_onboarding_settings(
    body: OnboardingSettings, settings: SettingsDep
) -> OnboardingSettings:
    save_onboarding(
        settings.resolved_save_dir(),
        Onboarding(
            show_everything=body.show_everything,
            guided_first_year=body.guided_first_year,
            stop_on=body.stop_on,
            stop_for_approvals=body.stop_for_approvals,
        ),
    )
    return get_onboarding_settings(settings)
