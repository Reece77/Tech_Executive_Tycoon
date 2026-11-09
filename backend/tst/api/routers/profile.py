"""Achievements routes (M25 section 2). Reading or marking toasts seen never touches a game."""

from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep, SettingsDep
from tst.api.routers.game import _path
from tst.api.routers.saves import ERRORS
from tst.api.schemas.profile import AchievementOut, AchievementsOut, SeenIn
from tst.db import repository
from tst.loader import LoadedData
from tst.profile import store
from tst.profile.check import mod_of, why_none

router = APIRouter(tags=["profile"])

HIDDEN = "???"


def achievements_out(
    profile: store.Profile, data: LoadedData, save: str | None = None
) -> AchievementsOut:
    items = []
    for a in data.achievements:
        got = profile.earned.get(a.key)
        secret = a.hidden and got is None
        items.append(
            AchievementOut(
                key=a.key,
                title=HIDDEN if secret else a.title,
                description=HIDDEN if secret else a.description,
                hidden=a.hidden,
                earned=got is not None,
                save=got.get("save") if got else None,
                company=got.get("company") if got else None,
                date_label=got.get("date_label") if got else None,
                seen=bool(got.get("seen", True)) if got else True,
            )
        )
    unseen = [i for i in items if i.earned and not i.seen and (save is None or i.save == save)]
    return AchievementsOut(
        profile=profile.name,
        earned=sum(1 for i in items if i.earned),
        total=len(items),
        achievements=items,
        unseen=unseen,
    )


@router.get(
    "/api/profile/achievements",
    response_model=AchievementsOut,
    operation_id="getAchievements",
)
def get_achievements(settings: SettingsDep, data: DataDep) -> AchievementsOut:
    """Every achievement: earned (with the save and date), locked, or hidden as "???"."""
    return achievements_out(store.load(settings.resolved_save_dir()), data)


@router.get(
    "/api/saves/{save_id}/achievements",
    response_model=AchievementsOut,
    responses=ERRORS,
    operation_id="getSaveAchievements",
)
def get_save_achievements(save_id: str, settings: SettingsDep, data: DataDep) -> AchievementsOut:
    """The profile's achievements as seen from one save: its new ones (for the toast), and
    whether it can earn any (Sandbox and modded games cannot)."""
    path = _path(settings, save_id)
    with repository.read_session(path) as session:
        reason = why_none(repository.read_state(session), mod_of(session))
    out = achievements_out(store.load(settings.resolved_save_dir()), data, save_id)
    return out.model_copy(update={"eligible": reason is None, "reason": reason})


@router.post(
    "/api/profile/achievements/seen",
    response_model=AchievementsOut,
    operation_id="markAchievementsSeen",
)
def mark_seen(body: SeenIn, settings: SettingsDep, data: DataDep) -> AchievementsOut:
    """The toasts for these achievements have been shown."""
    return achievements_out(store.mark_seen(settings.resolved_save_dir(), body.keys), data)
