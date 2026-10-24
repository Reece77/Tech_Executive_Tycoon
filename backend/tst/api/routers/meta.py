from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep
from tst.api.schemas.meta import (
    BackgroundOut,
    FounderPreviewOut,
    FounderRulesOut,
    FounderSkillOut,
    LabelOut,
    NewGameMetaOut,
    PresetOut,
    ScenarioOut,
    SkillMetaOut,
)
from tst.api.schemas.saves import FounderIn
from tst.sim.data_models import DEFAULT_DIFFICULTY, DIFFICULTY_LEVELS
from tst.sim.people.founder import preview_founder
from tst.sim.setup import MISSION_SIZE, starting_cash_cents

router = APIRouter(prefix="/api/meta", tags=["meta"])


def _scenarios(data: DataDep) -> list[ScenarioOut]:
    return [
        ScenarioOut(
            id=s.id,
            name=s.name,
            description=s.description,
            available_in=s.available_in,
            selectable=s.selectable,
            starting_cash_cents=starting_cash_cents(data.balance, s.id, DEFAULT_DIFFICULTY),
        )
        for s in data.game_data.scenarios
    ]


@router.get("/scenarios", response_model=list[ScenarioOut], operation_id="listScenarios")
def list_scenarios(data: DataDep) -> list[ScenarioOut]:
    return _scenarios(data)


@router.get("/new-game", response_model=NewGameMetaOut, operation_id="getNewGameMeta")
def new_game_meta(data: DataDep) -> NewGameMetaOut:
    """Everything the new-game setup screen needs (M1c)."""
    game, founder = data.game_data, data.balance.founder
    return NewGameMetaOut(
        scenarios=[s for s in _scenarios(data) if s.selectable],
        difficulties=list(DIFFICULTY_LEVELS),
        backgrounds=[
            BackgroundOut(
                key=b.key,
                label=b.label,
                description=b.description,
                available_in=b.available_in,
                selectable=b.selectable,
                bonuses=dict(b.bonuses),
                default_allocation=dict(b.default_allocation),
            )
            for b in game.backgrounds
        ],
        personality_presets=[
            PresetOut(key=p.key, label=p.label, values=dict(p.values))
            for p in game.personality_presets
        ],
        skills=[SkillMetaOut(key=s.key, label=s.label, group=s.group) for s in game.skills],
        interests=[LabelOut(key=i.key, label=i.label) for i in game.interests],
        work_styles=[LabelOut(key=w.key, label=w.label) for w in game.work_styles],
        regions=[LabelOut(key=r.key, label=r.label) for r in game.regions],
        roles=[LabelOut(key=r.key, label=r.label) for r in game.roles],
        founder_rules=FounderRulesOut(
            skill_base=founder.skill_base,
            skill_points=founder.skill_points,
            skill_cap=founder.skill_cap,
            age_min=int(founder.age_range.lo),
            age_max=int(founder.age_range.hi),
            default_age=founder.default_age,
            default_region=founder.default_region,
            mission_size=MISSION_SIZE,
        ),
    )


@router.post("/founder-preview", response_model=FounderPreviewOut, operation_id="previewFounder")
def founder_preview(body: FounderIn, data: DataDep) -> FounderPreviewOut:
    """Skill values, points left and every rule broken. Never current ability."""
    preview = preview_founder(body.to_spec(), data.game_data, data.balance)
    return FounderPreviewOut(
        skills=[
            FounderSkillOut(key=s.key, label=s.label, group=s.group, value=preview.skills[s.key])
            for s in data.game_data.skills
        ],
        points_spent=preview.points_spent,
        points_remaining=preview.points_remaining,
        errors=list(preview.problems),
    )
