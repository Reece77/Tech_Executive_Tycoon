"""Save-scoped M15b routes (formulas.md 30): rankings, scores and continue-until."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api import modes_views
from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.modes import ContinueUntilOut, ExitChoiceOut, FoundAgainIn, RankingsOut
from tst.db import repository

router = APIRouter(prefix="/api/saves/{save_id}", tags=["modes"])


@router.get("/rankings", response_model=RankingsOut, responses=ERRORS, operation_id="getRankings")
def get_rankings(
    save_id: str, settings: SettingsDep, data: DataDep, year: int | None = None
) -> RankingsOut:
    """The industry rankings of `year` (default the latest January's), 30.4."""
    with repository.read_session(_path(settings, save_id)) as session:
        state = repository.read_state(session)
    return modes_views.rankings_out(state, year)


@router.post(
    "/continue-until",
    response_model=ContinueUntilOut,
    responses=ERRORS,
    operation_id="continueUntil",
)
def continue_until(save_id: str, settings: SettingsDep, data: DataDep) -> ContinueUntilOut:
    """Play months as Continue does until something needs the player, up to a year (30.5).
    It decides nothing: what it stops for waits in the inbox."""
    from tst.sim.calendar import format_turn
    from tst.sim.modes.continue_until import LABELS

    path = _path(settings, save_id)
    played, why = repository.continue_until(path, data)
    with repository.read_session(path) as session:
        turn = repository.read_state(session).turn
    return ContinueUntilOut(
        months_played=played,
        stopped_for=why,
        stopped_label=LABELS[why],
        turn=turn,
        date_label=format_turn(turn),
    )


def _exit_choice(
    save_id: str, settings: SettingsDep, data: DataDep, keep: FoundAgainIn | None
) -> ExitChoiceOut:
    from tst.sim.modes.serial import FoundAgain, Retire

    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        state = repository.read_state(session)
    founder = state.founder_of(state.player.id)
    actor = founder.id if founder is not None else 0
    action = (
        Retire(actor) if keep is None else FoundAgain(actor, keep.company_name, keep.keep_cents)
    )
    after = repository.run_action(path, data, action).new_state
    return ExitChoiceOut(
        game_state=after.save_meta.game_state,
        company_id=after.player.id,
        company_name=after.player.name,
    )


@router.post(
    "/exit/found-again",
    response_model=ExitChoiceOut,
    responses=ERRORS,
    operation_id="foundAgain",
)
def found_again(
    save_id: str, body: FoundAgainIn, settings: SettingsDep, data: DataDep
) -> ExitChoiceOut:
    """After an exit: found a new company in the same world and month (M15b addendum 10)."""
    return _exit_choice(save_id, settings, data, body)


@router.post("/exit/retire", response_model=ExitChoiceOut, responses=ERRORS, operation_id="retire")
def retire(save_id: str, settings: SettingsDep, data: DataDep) -> ExitChoiceOut:
    """After an exit: retire, which ends the game (M15b addendum 10)."""
    return _exit_choice(save_id, settings, data, None)
