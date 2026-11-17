"""Save-scoped routes for the campaign's length (M37, formulas.md 52.1): what it is, and the
choice to continue in dynasty mode (before or at December 2039) or end the campaign there."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api import campaign_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _founder_id, _path, _state
from tst.api.routers.saves import ERRORS
from tst.api.schemas.campaign import CampaignActionOut, CampaignOut
from tst.db import repository
from tst.sim.dynasty.mode import ContinueDynasty, EndCampaign

router = APIRouter(prefix="/api/saves/{save_id}", tags=["campaign"])


@router.get("/campaign", response_model=CampaignOut, responses=ERRORS, operation_id="getCampaign")
def get_campaign(save_id: str, settings: SettingsDep, data: DataDep) -> CampaignOut:
    """The campaign's length and end, and dynasty years' eras, successions and deaths."""
    return campaign_views.campaign_out(_state(_path(settings, save_id)), data)


@router.post(
    "/campaign/continue",
    response_model=CampaignActionOut,
    responses=ERRORS,
    operation_id="continueDynasty",
)
def continue_dynasty(save_id: str, settings: SettingsDep, data: DataDep) -> CampaignActionOut:
    """Continue in dynasty mode, to December 2069 (a one-off; 409 once the game is over)."""
    path = _path(settings, save_id)
    state = repository.run_action(path, data, ContinueDynasty(_founder_id(_state(path))))
    return CampaignActionOut(campaign=campaign_views.campaign_out(state.new_state, data))


@router.post(
    "/campaign/end", response_model=CampaignActionOut, responses=ERRORS, operation_id="endCampaign"
)
def end_campaign(save_id: str, settings: SettingsDep, data: DataDep) -> CampaignActionOut:
    """At December 2039: end the standard campaign with its summary."""
    path = _path(settings, save_id)
    state = repository.run_action(path, data, EndCampaign(_founder_id(_state(path))))
    return CampaignActionOut(campaign=campaign_views.campaign_out(state.new_state, data))
