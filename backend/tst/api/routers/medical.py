"""Save-scoped routes for medical devices (M41, docs/formulas.md 50): the Medical screen, and
the founder's actions on it (a device's intended use, filings, studies, coverage requests,
clinical education and surveillance, and plants' quality systems). Actions run through
`repository.run_action` with the founder as actor."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from tst.api import medical_views, views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.medical import (
    CoverageIn,
    DesignIn,
    MedicalActionOut,
    MedicalOut,
    PlantQualityIn,
    StudyIn,
    SubmitIn,
    SupportIn,
)
from tst.db import inbox, repository
from tst.loader import LoadedData
from tst.sim.actions import Action
from tst.sim.medical.actions import (
    DesignDevice,
    RequestCoverage,
    SetMedicalSupport,
    SetPlantQuality,
    StartStudy,
    SubmitDevice,
)

router = APIRouter(prefix="/api/saves/{save_id}", tags=["medical"])


def _medical(path: Path, data: LoadedData) -> MedicalOut:
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    return medical_views.medical_out(state, data)


def _act(path: Path, data: LoadedData, action: Action) -> MedicalActionOut:
    state = repository.run_action(path, data, action).new_state
    with repository.open_session(path) as session:
        unread = inbox.unread_count(session, state.player.id)
    return MedicalActionOut(
        medical=_medical(path, data), energy=views.energy(state, data), unread_inbox=unread
    )


@router.get("/medical", response_model=MedicalOut, responses=ERRORS, operation_id="getMedical")
def get_medical(save_id: str, settings: SettingsDep, data: DataDep) -> MedicalOut:
    """Devices with their class, route and evidence, submissions by regulator, studies,
    coverage, adoption, inspections, recalls, plants' quality and rivals (50.7)."""
    return _medical(_path(settings, save_id), data)


@router.post(
    "/medical/design",
    response_model=MedicalActionOut,
    responses=ERRORS,
    operation_id="designDevice",
)
def design_device(
    save_id: str, body: DesignIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, DesignDevice(founder, body.product_id, body.use, body.pccp))


@router.post(
    "/medical/submit",
    response_model=MedicalActionOut,
    responses=ERRORS,
    operation_id="submitDevice",
)
def submit_device(
    save_id: str, body: SubmitIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, SubmitDevice(founder, body.product_id, body.regulator))


@router.post(
    "/medical/study", response_model=MedicalActionOut, responses=ERRORS, operation_id="startStudy"
)
def start_study(
    save_id: str, body: StudyIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, StartStudy(founder, body.product_id, body.kind, body.patients))


@router.post(
    "/medical/coverage",
    response_model=MedicalActionOut,
    responses=ERRORS,
    operation_id="requestCoverage",
)
def request_coverage(
    save_id: str, body: CoverageIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, RequestCoverage(founder, body.product_id, body.region))


@router.post(
    "/medical/support",
    response_model=MedicalActionOut,
    responses=ERRORS,
    operation_id="setMedicalSupport",
)
def set_support(
    save_id: str, body: SupportIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    action = SetMedicalSupport(founder, body.product_id, body.training_cents, body.surveillance)
    return _act(path, data, action)


@router.post(
    "/medical/plant-quality",
    response_model=MedicalActionOut,
    responses=ERRORS,
    operation_id="setPlantQuality",
)
def set_plant_quality(
    save_id: str, body: PlantQualityIn, settings: SettingsDep, data: DataDep
) -> MedicalActionOut:
    path = _path(settings, save_id)
    founder = _founder_id(_state(path))
    return _act(path, data, SetPlantQuality(founder, body.facility_id, body.level))
