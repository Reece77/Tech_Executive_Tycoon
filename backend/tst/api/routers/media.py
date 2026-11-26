"""Save-scoped routes for media (M55, docs/formulas.md 65): the Studio, Streaming, Games and Social
screens (one view) and the founder's media actions. Video, music and social lines are created,
priced and launched through the product routes; titles are green-lit here."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import media_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.media import (
    CutIn,
    GreenlightIn,
    LicenceIn,
    LiveServiceIn,
    MediaActionOut,
    MediaLineIn,
    MediaScreenOut,
    MoveIn,
    SignIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.media.actions import (
    CancelTitle,
    CutBudget,
    DivestRegion,
    GreenlightTitle,
    LicenseTitles,
    MoveRelease,
    OverruleLead,
    SetLiveService,
    SetMediaLine,
    SignLead,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["media"])


def _media(path: Path, data: LoadedData) -> MediaScreenOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return media_views.media_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> MediaActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return MediaActionOut(
        media=_media(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/media", response_model=MediaScreenOut, responses=ERRORS, operation_id="getMedia")
def get_media(save_id: str, settings: SettingsDep, data: DataDep) -> MediaScreenOut:
    """The Studio, Streaming, Games and Social screens: titles, leads, services, games, networks."""
    return _media(_path(settings, save_id), data)


@router.post(
    "/media/titles", response_model=MediaActionOut, responses=ERRORS, operation_id="greenlightTitle"
)
def greenlight_title(
    save_id: str, body: GreenlightIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    action = GreenlightTitle(
        _founder_id(_state(path)),
        body.name,
        body.kind,
        body.budget_cents,
        genre=body.genre,
        lead_person_id=body.lead_person_id,
        unit_id=body.unit_id,
        sequel_of=body.sequel_of,
        platforms=tuple(body.platforms),
        monetisation=body.monetisation,
        live_service=body.live_service,
        store=body.store,
        window=body.window,
        service_product_id=body.service_product_id,
    )
    return _act(path, data, action)


@router.post(
    "/media/titles/{title_id}/cancel",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="cancelTitle",
)
def cancel_title(
    save_id: str, title_id: int, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, CancelTitle(_founder_id(_state(path)), title_id))


@router.post(
    "/media/titles/{title_id}/overrule",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="overruleLead",
)
def overrule_lead(
    save_id: str, title_id: int, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, OverruleLead(_founder_id(_state(path)), title_id))


@router.post(
    "/media/titles/{title_id}/budget",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="cutTitleBudget",
)
def cut_budget(
    save_id: str, title_id: int, body: CutIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, CutBudget(_founder_id(_state(path)), title_id, body.budget_cents))


@router.post(
    "/media/titles/{title_id}/move",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="moveTitleRelease",
)
def move_release(
    save_id: str, title_id: int, body: MoveIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, MoveRelease(_founder_id(_state(path)), title_id, body.months))


@router.post(
    "/media/titles/{title_id}/live-service",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="setLiveService",
)
def set_live_service(
    save_id: str, title_id: int, body: LiveServiceIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SetLiveService(_founder_id(_state(path)), title_id, body.on))


@router.post(
    "/media/leads", response_model=MediaActionOut, responses=ERRORS, operation_id="signLead"
)
def sign_lead(save_id: str, body: SignIn, settings: SettingsDep, data: DataDep) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, SignLead(_founder_id(_state(path)), body.year, body.n, body.years))


@router.post(
    "/media/licences", response_model=MediaActionOut, responses=ERRORS, operation_id="licenseTitles"
)
def license_titles(
    save_id: str, body: LicenceIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    action = LicenseTitles(_founder_id(_state(path)), body.product_id, body.fee_cents, body.years)
    return _act(path, data, action)


@router.post(
    "/media/lines/{product_id}",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="setMediaLine",
)
def set_media_line(
    save_id: str, product_id: int, body: MediaLineIn, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    action = SetMediaLine(
        _founder_id(_state(path)),
        product_id,
        ad_tier=body.ad_tier,
        ad_load=body.ad_load,
        format=body.format,
        moderation=body.moderation,
        ad_pricing=body.ad_pricing,
    )
    return _act(path, data, action)


@router.post(
    "/media/laws/{law_id}/divest",
    response_model=MediaActionOut,
    responses=ERRORS,
    operation_id="divestRegion",
)
def divest_region(
    save_id: str, law_id: int, settings: SettingsDep, data: DataDep
) -> MediaActionOut:
    path = _path(settings, save_id)
    return _act(path, data, DivestRegion(_founder_id(_state(path)), law_id))
