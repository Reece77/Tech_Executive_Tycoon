"""Save-scoped routes for pharmaceuticals (M42, docs/formulas.md 55): the Pharma screen, and
the founder's actions on it (programmes, trials, filings, prices, plants, contract
manufacturers and licences). Actions run through `repository.run_action` with the founder as
actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import pharma_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.pharma import (
    PharmaActionOut,
    PharmaOut,
    RxCmoIn,
    RxFileIn,
    RxLicenseInIn,
    RxLicenseOutIn,
    RxPlantIn,
    RxPlantQualityIn,
    RxPlatformIn,
    RxPriceIn,
    RxProgrammeIn,
    RxStartIn,
    RxTrialIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.pharma.actions import (
    BuildPharmaPlant,
    ChooseCmo,
    FileDrug,
    LicenseAsset,
    LicensePlatform,
    OutLicense,
    SetDrugPrice,
    SetPharmaPlantQuality,
    StartProgramme,
    StartTrial,
    StopProgramme,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["pharma"])


def _pharma(path: Path, data: LoadedData) -> PharmaOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return pharma_views.pharma_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> PharmaActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return PharmaActionOut(
        pharma=_pharma(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/pharma", response_model=PharmaOut, responses=ERRORS, operation_id="getPharma")
def get_pharma(save_id: str, settings: SettingsDep, data: DataDep) -> PharmaOut:
    """Programmes by stage with readouts, ranges, filings, approvals, exclusivity and Explain;
    drugs with prices and revenue; plants, CMOs, assets, deals and rivals (55.7)."""
    return _pharma(_path(settings, save_id), data)


@router.post(
    "/pharma/start", response_model=PharmaActionOut, responses=ERRORS, operation_id="startProgramme"
)
def start_programme(
    save_id: str, body: RxStartIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(
        path, data, StartProgramme(founder, body.name, body.indication, body.modality, body.ai)
    )


@router.post(
    "/pharma/trial", response_model=PharmaActionOut, responses=ERRORS, operation_id="startTrial"
)
def start_trial(
    save_id: str, body: RxTrialIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, StartTrial(founder, body.programme_id, body.design))


@router.post(
    "/pharma/stop", response_model=PharmaActionOut, responses=ERRORS, operation_id="stopProgramme"
)
def stop_programme(
    save_id: str, body: RxProgrammeIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, StopProgramme(founder, body.programme_id))


@router.post(
    "/pharma/file", response_model=PharmaActionOut, responses=ERRORS, operation_id="fileDrug"
)
def file_drug(
    save_id: str, body: RxFileIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, FileDrug(founder, body.programme_id, body.regulator))


@router.post(
    "/pharma/price", response_model=PharmaActionOut, responses=ERRORS, operation_id="setDrugPrice"
)
def set_drug_price(
    save_id: str, body: RxPriceIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, SetDrugPrice(founder, body.programme_id, body.list_cents, body.support))


@router.post(
    "/pharma/plant",
    response_model=PharmaActionOut,
    responses=ERRORS,
    operation_id="buildPharmaPlant",
)
def build_pharma_plant(
    save_id: str, body: RxPlantIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, BuildPharmaPlant(founder, body.kind, body.region))


@router.post(
    "/pharma/plant-quality",
    response_model=PharmaActionOut,
    responses=ERRORS,
    operation_id="setPharmaPlantQuality",
)
def set_pharma_plant_quality(
    save_id: str, body: RxPlantQualityIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, SetPharmaPlantQuality(founder, body.plant_id, body.level))


@router.post(
    "/pharma/cmo", response_model=PharmaActionOut, responses=ERRORS, operation_id="chooseCmo"
)
def choose_cmo(
    save_id: str, body: RxCmoIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, ChooseCmo(founder, body.kind, body.cmo))


@router.post(
    "/pharma/license-in",
    response_model=PharmaActionOut,
    responses=ERRORS,
    operation_id="licenseAsset",
)
def license_asset(
    save_id: str, body: RxLicenseInIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, LicenseAsset(founder, body.asset_id, body.acquire))


@router.post(
    "/pharma/license-out",
    response_model=PharmaActionOut,
    responses=ERRORS,
    operation_id="outLicense",
)
def out_license(
    save_id: str, body: RxLicenseOutIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, OutLicense(founder, body.programme_id, body.rival_id, body.co_develop))


@router.post(
    "/pharma/platform",
    response_model=PharmaActionOut,
    responses=ERRORS,
    operation_id="licensePlatform",
)
def license_platform(
    save_id: str, body: RxPlatformIn, settings: SettingsDep, data: DataDep
) -> PharmaActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, LicensePlatform(founder, body.rival_id))
