from __future__ import annotations

from fastapi import APIRouter

from tst.api.deps import DataDep
from tst.api.schemas.meta import (
    BackgroundOut,
    ChannelOut,
    FounderPreviewOut,
    FounderRulesOut,
    FounderSkillOut,
    HiringMetaOut,
    LabelOut,
    NewGameMetaOut,
    PresetOut,
    RoleOut,
    ScenarioOut,
    SkillMetaOut,
)
from tst.api.schemas.saves import FounderIn
from tst.sim.data_models import DEFAULT_DIFFICULTY, DIFFICULTY_LEVELS
from tst.sim.hiring.formulas import energy_cost
from tst.sim.hiring.phases import ONE_BATCH
from tst.sim.people.founder import preview_founder
from tst.sim.setup import MISSION_SIZE, starting_cash_cents

router = APIRouter(prefix="/api/meta", tags=["meta"])

CHANNEL_LABELS = {"network": "Network", "job_post": "Job post", "recruiter": "Recruiter"}


def _scenarios(data: DataDep) -> list[ScenarioOut]:
    return [
        ScenarioOut(
            id=s.id,
            name=s.name,
            description=s.description,
            available_in=s.available_in,
            selectable=s.selectable,
            starting_cash_cents=starting_cash_cents(data.balance, s.id, DEFAULT_DIFFICULTY),
            starting_cash_by_difficulty={
                d: starting_cash_cents(data.balance, s.id, d) for d in DIFFICULTY_LEVELS
            },
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
            PresetOut(key=p.key, label=p.label, description=p.description, values=dict(p.values))
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


@router.get("/hiring", response_model=HiringMetaOut, operation_id="getHiringMeta")
def hiring_meta(data: DataDep) -> HiringMetaOut:
    """Channel costs, energy and offer limits for the Recruitment screen (M1c)."""
    hiring = data.balance.hiring
    channels = []
    for key, label in CHANNEL_LABELS.items():
        cfg = hiring.channel[key]
        channels.append(
            ChannelOut(
                key=key,
                label=label,
                energy=energy_cost(key, data.balance),
                monthly_cost_cents=hiring.job_post_cost_cents if key == "job_post" else 0,
                hire_fee_bp=hiring.recruiter_fee_bp if key == "recruiter" else 0,
                batch_min=int(cfg.size.lo),
                batch_max=int(cfg.size.hi),
                repeats=key not in ONE_BATCH,
                level_mix={k: int(v) for k, v in cfg.level_mix.items()},
            )
        )
    morale = data.balance.morale
    return HiringMetaOut(
        channels=channels,
        roles=[
            RoleOut(
                key=r.key,
                label=r.label,
                primary_skills=list(r.primary),
                secondary_skills=list(r.secondary),
            )
            for r in data.game_data.roles
        ],
        interview_energy=energy_cost("interview", data.balance),
        reference_check_energy=energy_cost("reference_check", data.balance),
        offer_energy=energy_cost("offer", data.balance),
        max_offer_equity_bp=hiring.max_offer_equity_bp,
        option_pool_bp=hiring.option_pool_bp,
        lowball_ratio=hiring.lowball_ratio,
        candidate_shelf_turns=hiring.candidate_shelf_turns,
        fire_morale_penalty_min=int(
            min(abs(morale.fire_penalty), abs(morale.fire_penalty_culture_carrier))
        ),
        energy_per_month=data.balance.founder.energy_per_month,
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
